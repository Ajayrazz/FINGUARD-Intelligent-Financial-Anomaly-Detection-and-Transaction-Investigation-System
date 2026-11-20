import { useState, type ReactNode } from "react";
import { Tilt } from "../fx/Tilt";

export type ViewMode = "cards" | "table";

/** Remembers Cards/Table per page in this browser (best effort: storage can be blocked). */
export function useViewMode(key: string): [ViewMode, (m: ViewMode) => void] {
  const k = `fg-view-${key}`;
  const [mode, setMode] = useState<ViewMode>(() => {
    try {
      return localStorage.getItem(k) === "table" ? "table" : "cards";
    } catch {
      return "cards";
    }
  });
  return [
    mode,
    (m) => {
      setMode(m);
      try {
        localStorage.setItem(k, m);
      } catch {
        /* ignore */
      }
    },
  ];
}

export function ViewToggle({
  mode,
  onChange,
}: {
  mode: ViewMode;
  onChange: (m: ViewMode) => void;
}) {
  const btn = (m: ViewMode, label: string) => (
    <button
      type="button"
      aria-pressed={mode === m}
      onClick={() => onChange(m)}
      className={`px-3 py-1 text-sm transition ${mode === m ? "btn-glow text-white" : "text-slate-700 hover:bg-white/10"}`}
    >
      {label}
    </button>
  );
  return (
    <div
      role="group"
      aria-label="View"
      className="inline-flex overflow-hidden rounded-lg border border-slate-300"
    >
      {btn("cards", "Cards")}
      {btn("table", "Table view")}
    </div>
  );
}

export function CardGrid({
  children,
  min = "17rem",
}: {
  children: ReactNode;
  min?: string;
}) {
  return (
    <div
      className="stagger grid gap-4"
      style={{
        gridTemplateColumns: `repeat(auto-fill, minmax(min(${min}, 100%), 1fr))`,
      }}
    >
      {children}
    </div>
  );
}

export type Tone =
  "indigo" | "violet" | "cyan" | "pink" | "amber" | "green" | "red" | "slate";
const TONES: Record<Tone, { bar: string; glow: string }> = {
  indigo: { bar: "from-indigo-400 to-indigo-600", glow: "from-indigo-500/15" },
  violet: { bar: "from-violet-400 to-violet-600", glow: "from-violet-500/15" },
  cyan: { bar: "from-cyan-300 to-cyan-500", glow: "from-cyan-400/15" },
  pink: { bar: "from-pink-400 to-pink-600", glow: "from-pink-500/15" },
  amber: { bar: "from-amber-300 to-amber-500", glow: "from-amber-400/15" },
  green: {
    bar: "from-emerald-300 to-emerald-500",
    glow: "from-emerald-400/15",
  },
  red: { bar: "from-red-400 to-red-600", glow: "from-red-500/20" },
  slate: { bar: "from-slate-400 to-slate-500", glow: "from-slate-400/10" },
};

/** A glass card with a coloured edge that tilts toward the pointer. Optional click target. */
export function Card3D({
  tone = "indigo",
  children,
  selected,
  className = "",
}: {
  tone?: Tone;
  children: ReactNode;
  selected?: boolean;
  className?: string;
}) {
  const t = TONES[tone];
  return (
    <Tilt max={5} className="h-full">
      <article
        className={`relative flex h-full flex-col overflow-hidden rounded-2xl border bg-gradient-to-br ${t.glow} to-transparent p-4 pl-5 shadow-lg shadow-black/30 transition-shadow hover:shadow-indigo-500/20 ${selected ? "border-indigo-300 ring-1 ring-indigo-300/60" : "border-indigo-400/20"} ${className}`}
      >
        <span
          aria-hidden="true"
          className={`absolute inset-y-0 left-0 w-1.5 bg-gradient-to-b ${t.bar}`}
        />
        {children}
      </article>
    </Tilt>
  );
}

/** Circular gauge (0..max) drawn in SVG. The number is real text, so it is accessible. */
export function Ring({
  value,
  max = 1,
  label,
  tone = "indigo",
  size = 72,
  decimals = 3,
}: {
  value: number;
  max?: number;
  label?: string;
  tone?: Tone;
  size?: number;
  decimals?: number;
}) {
  const r = 28;
  const c = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, value / max));
  const stroke = {
    indigo: "#818cf8",
    violet: "#a78bfa",
    cyan: "#22d3ee",
    pink: "#f472b6",
    amber: "#fbbf24",
    green: "#34d399",
    red: "#f87171",
    slate: "#94a3b8",
  }[tone];
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg viewBox="0 0 72 72" width={size} height={size} aria-hidden="true">
        <circle
          cx="36"
          cy="36"
          r={r}
          fill="none"
          stroke="rgba(129,140,248,0.18)"
          strokeWidth="7"
        />
        <circle
          cx="36"
          cy="36"
          r={r}
          fill="none"
          stroke={stroke}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${c * frac} ${c}`}
          transform="rotate(-90 36 36)"
          style={{ filter: `drop-shadow(0 0 4px ${stroke})` }}
        />
      </svg>
      <span className="absolute inset-0 flex flex-col items-center justify-center text-sm font-semibold tabular-nums text-slate-800">
        {value.toFixed(decimals)}
        {label && (
          <span className="text-[9px] font-normal text-slate-500">{label}</span>
        )}
      </span>
    </div>
  );
}

export function Chip({
  children,
  tone = "slate",
}: {
  children: ReactNode;
  tone?: Tone;
}) {
  const c: Record<Tone, string> = {
    indigo: "bg-indigo-500/15 text-indigo-200",
    violet: "bg-violet-500/15 text-violet-200",
    cyan: "bg-cyan-400/15 text-cyan-200",
    pink: "bg-pink-500/15 text-pink-200",
    amber: "bg-amber-400/15 text-amber-200",
    green: "bg-emerald-400/15 text-emerald-200",
    red: "bg-red-500/15 text-red-200",
    slate: "bg-white/10 text-slate-700",
  };
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs ${c[tone]}`}
    >
      {children}
    </span>
  );
}

export function Initials({ text }: { text: string }) {
  const s = (text.split("@")[0] ?? text).slice(0, 2).toUpperCase() || "?";
  return (
    <span
      aria-hidden="true"
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 text-xs font-semibold text-white"
    >
      {s}
    </span>
  );
}
