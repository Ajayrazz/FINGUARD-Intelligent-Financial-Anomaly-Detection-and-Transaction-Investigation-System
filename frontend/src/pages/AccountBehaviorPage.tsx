import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { BehaviorProfile } from '../api/types'
import { BarChart } from '../components/behavior/BarChart'
import { ErrorState, LoadingState } from '../components/ui/states'
import { formatAmount } from '../lib/format'

const money = (x: number | null) => (x === null ? '—' : formatAmount(String(x)))
const GRANULARITIES = ['daily', 'weekly', 'monthly'] as const

export default function AccountBehaviorPage() {
  const { id = '' } = useParams()
  const [direction, setDirection] = useState<'out' | 'in'>('out')
  const [windowDays, setWindowDays] = useState(90)
  const [gran, setGran] = useState<(typeof GRANULARITIES)[number]>('daily')
  const q = useQuery({
    queryKey: ['behavior-profile', id, direction, windowDays],
    queryFn: ({ signal }) => api.get<BehaviorProfile>(`/accounts/${id}/behavior/profile/?direction=${direction}&window_days=${windowDays}`, signal),
  })
  if (q.isPending) return <LoadingState />
  if (q.isError) return <ErrorState message={q.error.message} onRetry={() => void q.refetch()} />
  const p = q.data
  const series = p.aggregates[gran]
  const recentAvg = p.recent_7d.avg
  return (
    <section className="space-y-5">
      <div>
        <Link to={`/accounts/${id}`} className="text-sm text-blue-700 hover:underline">← Account</Link>
        <h1 className="mt-1 text-2xl font-semibold">Behavior · <span className="font-mono">{p.account_ref}</span></h1>
        <p className="text-sm text-slate-600">
          {direction === 'out' ? 'Outgoing spending' : 'Incoming payments'} in the {windowDays} days before now · profile {p.profile_version}
        </p>
      </div>
      <div className="flex flex-wrap gap-4 text-sm">
        <label>Direction{' '}
          <select className="rounded border border-slate-300 p-1" value={direction} onChange={(e) => setDirection(e.target.value as 'out' | 'in')}>
            <option value="out">Outgoing (spending)</option><option value="in">Incoming</option>
          </select>
        </label>
        <label>Window{' '}
          <select className="rounded border border-slate-300 p-1" value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))}>
            {[30, 90, 180, 365].map((d) => <option key={d} value={d}>{d} days</option>)}
          </select>
        </label>
      </div>
      {p.tx_count === 0 && (
        <p role="status" className="rounded border border-slate-300 bg-slate-50 p-3 text-sm">No transactions in this window, so there is no profile to show.</p>
      )}
      {p.tx_count > 0 && !p.sufficient_history && (
        <p role="status" className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          Only {p.tx_count} transaction(s): too little history for deviation scoring. Figures below are descriptive only.
        </p>
      )}
      {p.tx_count > 0 && (
        <>
          <dl className="grid grid-cols-2 gap-4 rounded-lg border border-slate-200 p-4 sm:grid-cols-4">
            <div><dt className="text-xs text-slate-500">Transactions</dt><dd className="tabular-nums">{p.tx_count.toLocaleString()}</dd></div>
            <div><dt className="text-xs text-slate-500">Average / median</dt><dd className="tabular-nums">{money(p.avg_amount)} / {money(p.median_amount)}</dd></div>
            <div><dt className="text-xs text-slate-500">95th percentile</dt><dd className="tabular-nums">{money(p.p95_amount)}</dd></div>
            <div><dt className="text-xs text-slate-500">Per day · counterparties</dt><dd className="tabular-nums">{p.tx_per_day.toFixed(2)} · {p.unique_counterparties}</dd></div>
          </dl>
          <div>
            <h2 className="text-lg font-semibold">Current vs historical</h2>
            <table className="mt-2 text-sm">
              <thead className="text-left text-slate-600"><tr><th className="pr-6">Period</th><th className="pr-6 text-right">Transactions</th><th className="pr-6 text-right">Total</th><th className="text-right">Average</th></tr></thead>
              <tbody>
                <tr><td className="pr-6">Last 7 days</td><td className="pr-6 text-right tabular-nums">{p.recent_7d.count}</td><td className="pr-6 text-right tabular-nums">{money(p.recent_7d.total)}</td><td className="text-right tabular-nums">{money(recentAvg)}</td></tr>
                <tr><td className="pr-6">Whole window ({windowDays} d)</td><td className="pr-6 text-right tabular-nums">{p.tx_count}</td><td className="pr-6 text-right tabular-nums">{money((p.avg_amount ?? 0) * p.tx_count)}</td><td className="text-right tabular-nums">{money(p.avg_amount)}</td></tr>
              </tbody>
            </table>
          </div>
          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Spending trend</h2>
              <div role="tablist" className="flex gap-2">
                {GRANULARITIES.map((g) => (
                  <button key={g} role="tab" aria-selected={gran === g} onClick={() => setGran(g)}
                    className={`rounded-md px-3 py-1 text-sm capitalize ${gran === g ? 'bg-slate-900 text-white' : 'border border-slate-300'}`}>{g}</button>
                ))}
              </div>
            </div>
            <BarChart values={series.map((s) => s.total)} labels={series.map((s) => s.period)} label={`${gran} total amount, ${series.length} periods`} />
            <p className="mt-1 text-xs text-slate-600">{series.length ? `${series[0]!.period} → ${series.at(-1)!.period}` : 'no data'} · bar height = total amount per period</p>
          </div>
          <div>
            <h2 className="text-lg font-semibold">Time of day (UTC)</h2>
            <BarChart values={p.hour_histogram} labels={p.hour_histogram.map((_, h) => `${h}:00`)} label="Transactions by hour of day, 24 bars" />
            <p className="mt-1 text-xs text-slate-600">0:00 → 23:00</p>
          </div>
          <p className="text-sm text-slate-600">
            Merchant categories: {p.merchant_category_dist ? Object.entries(p.merchant_category_dist).map(([k, v]) => `${k} (${v})`).join(', ') : 'not available in this dataset'}
          </p>
        </>
      )}
    </section>
  )
}
