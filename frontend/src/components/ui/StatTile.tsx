import { useCountUp } from "../../lib/useCountUp";
import { Tilt } from "../fx/Tilt";

/** Big animated number on a tilting glass card. Replaces "label: value" rows. */
export function StatTile({
  label,
  value,
  hint,
  tone = "indigo",
}: {
  label: string;
  value: number;
  hint?: string;
  tone?: "indigo" | "violet" | "cyan" | "pink" | "amber" | "green";
}) {
  const shown = useCountUp(value);
  const glow = {
    indigo: "from-indigo-500/30",
    violet: "from-violet-500/30",
    cyan: "from-cyan-400/25",
    pink: "from-pink-500/25",
    amber: "from-amber-400/25",
    green: "from-emerald-400/25",
  }[tone];
  return (
    <Tilt>
      <div
        className={`relative overflow-hidden rounded-2xl border border-indigo-400/20 bg-gradient-to-br ${glow} to-transparent p-4`}
      >
        <p className="text-xs font-medium uppercase tracking-widest text-slate-600">
          {label}
        </p>
        <p className="mt-2 text-3xl font-semibold tabular-nums text-slate-800">
          {shown.toLocaleString("en-IN")}
        </p>
        {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      </div>
    </Tilt>
  );
}
