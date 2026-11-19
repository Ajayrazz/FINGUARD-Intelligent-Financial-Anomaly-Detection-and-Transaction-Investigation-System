import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { TransactionBehavior } from '../../api/types'
import { ErrorState, LoadingState } from '../ui/states'

const LABELS: Record<string, string> = {
  amount: 'Amount vs usual',
  burst: 'Burst of transactions',
  spend_jump: 'Weekly spend jump',
  new_counterparty: 'New counterparty',
  hour: 'Unusual hour',
}

function describe(name: string, c: TransactionBehavior['components'][string]): string {
  const d = (c.detail ?? {}) as Record<string, number | boolean | string>
  switch (name) {
    case 'amount': return `${Number(d.amount).toLocaleString()} vs median ${Number(d.median).toLocaleString()}`
    case 'burst': return `${d.transactions_in_window} transaction(s) in ${d.window_minutes} min`
    case 'spend_jump': return `${Number(d.ratio).toFixed(1)}× the usual weekly spend`
    case 'new_counterparty': return d.seen_before ? 'receiver seen before' : 'first payment to this receiver'
    case 'hour': return `hour ${d.hour_utc} UTC, ${d.prior_in_hour} earlier in that hour`
    default: return ''
  }
}

/** Behavioral deviation of one transaction against its sender's earlier history, with the reason for every part. */
export function BehaviorPanel({ transactionId }: { transactionId: number }) {
  const q = useQuery({
    queryKey: ['tx-behavior', transactionId],
    queryFn: ({ signal }) => api.get<TransactionBehavior>(`/transactions/${transactionId}/behavior/`, signal),
  })
  if (q.isPending) return <LoadingState />
  if (q.isError) return <ErrorState message={q.error.message} onRetry={() => void q.refetch()} />
  const b = q.data
  return (
    <div>
      <h2 className="text-lg font-semibold">Behavioral deviation</h2>
      {b.status === 'unavailable_cold_start' ? (
        <p role="status" className="mt-2 rounded border border-slate-300 bg-slate-50 p-3 text-sm text-slate-700">
          Not available: the sender has only {b.history_count} earlier transaction(s) in the last 90 days, too few for a baseline.
          This is shown instead of a score of 0.
        </p>
      ) : (
        <>
          <p className="mt-2 text-sm">
            <span className="text-3xl font-semibold tabular-nums">{b.deviation_score?.toFixed(1)}</span>
            <span className="text-slate-600"> / 100 · based on {b.history_count} earlier transactions · signal coverage {(b.coverage * 100).toFixed(0)}%</span>
          </p>
          <table className="mt-2 w-full text-left text-sm">
            <caption className="sr-only">Components of the behavioral deviation score</caption>
            <thead className="border-b border-slate-300 text-slate-600">
              <tr><th className="py-1">Signal</th><th className="text-right">Score</th><th className="pl-4">Evidence</th></tr>
            </thead>
            <tbody>
              {Object.entries(b.components).map(([name, c]) => (
                <tr key={name} className="border-b border-slate-100">
                  <td className="py-1">{LABELS[name] ?? name}</td>
                  {c.available && c.score !== null ? (
                    <>
                      <td className="text-right tabular-nums">{c.score.toFixed(0)}</td>
                      <td className="pl-4 text-slate-700">{describe(name, c)}</td>
                    </>
                  ) : (
                    <td colSpan={2} className="pl-4 text-slate-500">Unavailable — {c.reason}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
