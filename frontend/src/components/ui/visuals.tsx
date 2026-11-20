/* Small decorative data visuals used inside cards. They repeat information that is also shown as text,
   so they are hidden from assistive technology. */

const SEG = ["#818cf8", "#a78bfa", "#22d3ee", "#f472b6", "#fbbf24", "#34d399"];

/** One bar split into proportional, animated segments (e.g. risk-weight mix). */
export function StackBar({
  parts,
}: {
  parts: { label: string; value: number }[];
}) {
  return (
    <div
      aria-hidden="true"
      className="flex h-2.5 w-full overflow-hidden rounded-full bg-white/10"
    >
      {parts.map((p, i) => (
        <span
          key={p.label}
          title={`${p.label} ${(p.value * 100).toFixed(0)}%`}
          className="h-full origin-left"
          style={{
            width: `${p.value * 100}%`,
            background: SEG[i % SEG.length],
            animation: `seg-in 0.7s ${i * 0.08}s cubic-bezier(0.2,0.7,0.2,1) backwards`,
          }}
        />
      ))}
    </div>
  );
}

/** 0–100 scale with the medium/high/critical cut-offs marked on a green→red gradient. */
export function ThresholdBar({
  medium,
  high,
  critical,
}: {
  medium: number;
  high: number;
  critical: number;
}) {
  return (
    <div
      aria-hidden="true"
      className="relative mt-3 h-2 rounded-full"
      style={{
        background: "linear-gradient(90deg,#34d399,#fbbf24 55%,#f43f5e)",
      }}
    >
      {[medium, high, critical].map((v) => (
        <span
          key={v}
          className="absolute -top-1 h-4 w-0.5 rounded bg-white/80"
          style={{ left: `${Math.min(100, v)}%` }}
        />
      ))}
    </div>
  );
}

/** Tiny column chart for several 0–100 values; null = unavailable (drawn as a dashed stub, never as 0). */
export function MiniBars({
  items,
}: {
  items: { label: string; value: number | null }[];
}) {
  return (
    <div aria-hidden="true" className="flex h-14 items-end gap-1.5">
      {items.map((it, i) => (
        <div
          key={it.label}
          className="flex flex-1 flex-col items-center gap-1"
          title={`${it.label}: ${it.value === null ? "unavailable" : it.value.toFixed(0)}`}
        >
          {it.value === null ? (
            <span className="h-3 w-full rounded-sm border border-dashed border-slate-400/60" />
          ) : (
            <span
              className="w-full origin-bottom rounded-t-sm"
              style={{
                height: `${Math.max(6, it.value)}%`,
                minHeight: 4,
                background: `linear-gradient(to top, ${SEG[i % SEG.length]}, #fff3)`,
                animation: `bar-in 0.7s ${i * 0.07}s cubic-bezier(0.2,0.7,0.2,1) backwards`,
              }}
            />
          )}
          <span className="text-[9px] text-slate-500">{it.label}</span>
        </div>
      ))}
    </div>
  );
}

/** A small document sheet. `tone` tints it; `delay` offsets the float so two sheets bob out of step. */
export function DocTile({
  label,
  tone = "indigo",
  delay = 0,
}: {
  label: string;
  tone?: "indigo" | "amber" | "pink" | "green";
  delay?: number;
}) {
  const c = {
    indigo: "border-indigo-300/40 bg-indigo-500/15",
    amber: "border-amber-300/40 bg-amber-400/15",
    pink: "border-pink-300/40 bg-pink-500/15",
    green: "border-emerald-300/40 bg-emerald-400/15",
  }[tone];
  return (
    <div
      className={`animate-float w-[4.5rem] shrink-0 rounded-lg border ${c} p-2`}
      style={{ animationDelay: `${delay}s` }}
    >
      <span className="block h-1.5 w-8 rounded bg-white/50" />
      <span className="mt-1.5 block h-1 w-full rounded bg-white/20" />
      <span className="mt-1 block h-1 w-10 rounded bg-white/20" />
      <p className="mt-2 font-mono text-xs text-slate-800">{label}</p>
    </div>
  );
}

/** Animated dashed connector between two sheets. */
export function FlowLine() {
  return (
    <svg
      viewBox="0 0 40 8"
      className="h-2 min-w-6 flex-1 text-indigo-300"
      aria-hidden="true"
      preserveAspectRatio="none"
    >
      <path
        d="M0 4h40"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        className="flow-dash"
      />
    </svg>
  );
}
