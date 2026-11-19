import type { AttributionRow } from '../../api/types'

/** Horizontal contribution bars: right/amber = raises the score, left/blue = lowers it. Values are always printed. */
export function AttributionChart({ rows, max = 8 }: { rows: AttributionRow[]; max?: number }) {
  const shown = rows.slice(0, max)
  const peak = Math.max(...shown.map((r) => Math.abs(r.contribution)), 1e-9)
  return (
    <ul aria-label="Feature contributions" className="space-y-1 text-sm">
      {shown.map((r) => {
        const pct = (Math.abs(r.contribution) / peak) * 50
        const up = r.contribution >= 0
        return (
          <li key={r.name} className="grid grid-cols-[minmax(0,14rem)_1fr_5rem] items-center gap-2">
            <span title={r.rule || undefined}>{r.label}<span className="text-slate-500"> = {r.display}</span></span>
            <span className="relative h-3 rounded bg-slate-100" aria-hidden>
              <span className="absolute inset-y-0 left-1/2 w-px bg-slate-400" />
              <span className={`absolute inset-y-0 rounded ${up ? 'bg-amber-500' : 'bg-sky-600'}`} style={up ? { left: '50%', width: `${pct}%` } : { right: '50%', width: `${pct}%` }} />
            </span>
            <span className="text-right tabular-nums">{up ? 'raises' : 'lowers'} {r.contribution >= 0 ? '+' : ''}{r.contribution.toFixed(3)}</span>
          </li>
        )
      })}
    </ul>
  )
}
