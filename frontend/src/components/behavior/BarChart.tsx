/** Minimal accessible bar chart; every bar carries its value as a title and the whole chart has a text label. */
export function BarChart({ values, labels, label }: { values: number[]; labels: string[]; label: string }) {
  const max = Math.max(...values, 1)
  return (
    <div role="img" aria-label={label} className="flex h-28 items-end gap-px">
      {values.map((v, i) => (
        <div
          key={i}
          title={`${labels[i]}: ${v.toLocaleString()}`}
          className="min-w-px flex-1 bg-slate-600"
          style={{ height: `${v > 0 ? Math.max((v / max) * 100, 2) : 0}%` }}
        />
      ))}
    </div>
  )
}
