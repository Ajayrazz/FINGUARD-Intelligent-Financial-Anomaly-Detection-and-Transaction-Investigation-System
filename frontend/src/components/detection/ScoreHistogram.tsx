import type { ScoreSummary } from "../../api/types";

/** Distribution of all scores in a run. Bars are log-scaled so the rare high-score tail stays visible. */
export function ScoreHistogram({ summary }: { summary: ScoreSummary }) {
  const { counts, edges } = summary.histogram;
  const max = Math.max(...counts.map((c) => Math.log10(c + 1)), 1);
  const thresholdBin = edges.findIndex(
    (e, i) =>
      i < counts.length &&
      summary.threshold >= e &&
      summary.threshold < edges[i + 1]!,
  );
  return (
    <figure>
      <div
        className="flex h-32 items-end gap-0.5"
        role="img"
        aria-label={`Score distribution, ${counts.length} bins from ${edges[0]?.toFixed(3)} to ${edges.at(-1)?.toFixed(3)} (log scale)`}
      >
        {counts.map((c, i) => (
          <div
            key={i}
            title={`${edges[i]!.toFixed(3)}–${edges[i + 1]!.toFixed(3)}: ${c.toLocaleString()} transactions`}
            className={`flex-1 ${i === thresholdBin ? "bg-red-600" : "bg-slate-500"}`}
            style={{
              height: `${Math.max((Math.log10(c + 1) / max) * 100, c > 0 ? 3 : 0)}%`,
            }}
          />
        ))}
      </div>
      <figcaption className="mt-1 flex justify-between text-xs text-slate-600">
        <span>{edges[0]?.toFixed(3)}</span>
        <span>
          Red bar contains the alert threshold ({summary.threshold.toFixed(3)})
          · log scale
        </span>
        <span>{edges.at(-1)?.toFixed(3)}</span>
      </figcaption>
    </figure>
  );
}
