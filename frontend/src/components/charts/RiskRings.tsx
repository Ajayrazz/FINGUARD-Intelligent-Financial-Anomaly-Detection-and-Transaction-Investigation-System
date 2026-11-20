import { useEffect, useState } from "react";

const RINGS = [
  { key: "critical", label: "Critical", color: "#ef4444" },
  { key: "high", label: "High", color: "#f97316" },
  { key: "medium", label: "Medium", color: "#f59e0b" },
  { key: "low", label: "Low", color: "#10b981" },
  { key: "unscored", label: "Unscored", color: "#94a3b8" },
] as const;

/**
 * Concentric "activity" rings, one per risk category. Ring length is log-scaled against the largest category, so a
 * category with a handful of transactions stays visible next to one with hundreds of thousands. The exact counts and
 * shares are always listed as text underneath.
 */
export function RiskRings({ counts }: { counts: Record<string, number> }) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShown(true), 60);
    return () => clearTimeout(t);
  }, []);
  const total = RINGS.reduce((n, r) => n + (counts[r.key] ?? 0), 0);
  const max = Math.max(1, ...RINGS.map((r) => counts[r.key] ?? 0));
  const share = (n: number) => (total ? (n / total) * 100 : 0);
  return (
    <div className="flex flex-col items-center gap-4 lg:flex-row lg:justify-center lg:gap-8">
      <div className="relative h-56 w-56 shrink-0">
        <svg
          viewBox="0 0 220 220"
          className="h-full w-full -rotate-90"
          aria-hidden="true"
        >
          {RINGS.map((r, i) => {
            const radius = 98 - i * 17;
            const circ = 2 * Math.PI * radius;
            const n = counts[r.key] ?? 0;
            const frac =
              n > 0
                ? Math.max(0.05, Math.log10(n + 1) / Math.log10(max + 1))
                : 0;
            return (
              <g key={r.key}>
                <circle
                  cx="110"
                  cy="110"
                  r={radius}
                  fill="none"
                  stroke="rgba(129,140,248,0.14)"
                  strokeWidth="11"
                />
                <circle
                  cx="110"
                  cy="110"
                  r={radius}
                  fill="none"
                  stroke={r.color}
                  strokeWidth="11"
                  strokeLinecap="round"
                  strokeDasharray={`${shown ? frac * circ : 0} ${circ}`}
                  style={{
                    filter: `drop-shadow(0 0 6px ${r.color})`,
                    transition: `stroke-dasharray 1.1s cubic-bezier(0.2,0.7,0.2,1) ${i * 0.12}s`,
                  }}
                />
              </g>
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-2xl font-semibold tabular-nums text-slate-800">
            {total.toLocaleString("en-IN")}
          </span>
          <span className="text-xs text-slate-500">scored</span>
        </div>
      </div>
      <ul
        aria-label="Transactions by risk category"
        className="grid w-full max-w-xs gap-2 text-sm"
      >
        {RINGS.map((r) => {
          const n = counts[r.key] ?? 0;
          const p = share(n);
          return (
            <li
              key={r.key}
              className="flex items-center gap-2 rounded-xl border border-indigo-400/15 bg-white/[0.04] px-3 py-1.5"
              style={{ opacity: n ? 1 : 0.55 }}
            >
              <span
                aria-hidden="true"
                className="h-3 w-3 rounded-full"
                style={{ background: r.color, boxShadow: `0 0 8px ${r.color}` }}
              />
              <span className="flex-1">{r.label}</span>
              <span className="font-semibold tabular-nums">
                {n.toLocaleString("en-IN")}
              </span>
              <span className="w-14 text-right text-xs text-slate-500 tabular-nums">
                {n === 0
                  ? "0%"
                  : p < 0.01
                    ? "<0.01%"
                    : `${p.toFixed(p < 1 ? 2 : 1)}%`}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
