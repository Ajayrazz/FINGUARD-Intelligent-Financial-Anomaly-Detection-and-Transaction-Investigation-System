import { Tilt } from "../fx/Tilt";

const STAGES = [
  { key: "new", label: "New", color: "#22d3ee" },
  { key: "under_review", label: "Under review", color: "#38bdf8" },
  { key: "investigation", label: "Investigation", color: "#818cf8" },
  { key: "escalated", label: "Escalated", color: "#d946ef" },
  { key: "resolved", label: "Resolved", color: "#fbbf24" },
  { key: "closed", label: "Closed", color: "#34d399" },
] as const;

/**
 * Case workflow as a pipeline of stages. Every stage is always shown (a stage with no cases is simply dim), so the
 * picture stays readable however uneven the counts are; each ring shows that stage's share of all cases.
 */
export function CasePipeline({
  byStatus,
}: {
  byStatus: Partial<Record<string, number>>;
}) {
  const total = STAGES.reduce((n, s) => n + (byStatus[s.key] ?? 0), 0);
  const r = 26;
  const c = 2 * Math.PI * r;
  return (
    <div>
      <ol
        aria-label="Cases by status"
        className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6"
      >
        {STAGES.map((s, i) => {
          const n = byStatus[s.key] ?? 0;
          const frac = total ? n / total : 0;
          return (
            <li key={s.key} className="relative">
              <Tilt max={8}>
                <div
                  className="flex flex-col items-center rounded-2xl border bg-white/[0.04] px-2 py-3 text-center"
                  style={{
                    borderColor: n ? `${s.color}66` : "rgba(129,140,248,0.15)",
                    opacity: n ? 1 : 0.55,
                    boxShadow: n ? `0 0 22px -8px ${s.color}` : undefined,
                  }}
                >
                  <div className="relative h-[4.5rem] w-[4.5rem]">
                    <svg
                      viewBox="0 0 64 64"
                      className="h-full w-full -rotate-90"
                      aria-hidden="true"
                    >
                      <circle
                        cx="32"
                        cy="32"
                        r={r}
                        fill="none"
                        stroke="rgba(129,140,248,0.18)"
                        strokeWidth="6"
                      />
                      <circle
                        cx="32"
                        cy="32"
                        r={r}
                        fill="none"
                        stroke={s.color}
                        strokeWidth="6"
                        strokeLinecap="round"
                        strokeDasharray={`${Math.max(frac, n ? 0.04 : 0) * c} ${c}`}
                        style={{
                          filter: `drop-shadow(0 0 5px ${s.color})`,
                          transition: "stroke-dasharray 0.9s ease",
                        }}
                      />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-xl font-semibold tabular-nums text-slate-800">
                      {n}
                    </span>
                  </div>
                  <span className="mt-1 text-xs font-medium text-slate-700">
                    {s.label}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {total
                      ? `${(frac * 100).toFixed(frac && frac < 0.01 ? 2 : 0)}%`
                      : "—"}
                  </span>
                </div>
              </Tilt>
              {i < STAGES.length - 1 && (
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute -right-3 top-1/3 hidden text-indigo-300 xl:block"
                >
                  ›
                </span>
              )}
            </li>
          );
        })}
      </ol>
      <p className="mt-2 text-center text-xs text-slate-500">
        {total.toLocaleString("en-IN")} {total === 1 ? "case" : "cases"} in
        total
      </p>
    </div>
  );
}
