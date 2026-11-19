import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { AccountBrief, TransactionDetail, TransactionEvent, TransactionRow, TxStatus } from '../api/types'
import { PermissionGate } from '../auth/guards'
import { BehaviorPanel } from '../components/behavior/BehaviorPanel'
import { TransactionTable } from '../components/transactions/TransactionTable'
import { StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Dialog } from '../components/ui/Dialog'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/states'
import { useToast } from '../components/ui/Toast'
import { formatAmount, formatDateTime } from '../lib/format'

const STATUSES: TxStatus[] = ['pending', 'completed', 'failed', 'reversed']

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-sm">{value || '—'}</dd>
    </div>
  )
}

function AccountCard({ title, account, before, after }: { title: string; account: AccountBrief | null; before: string | null; after: string | null }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <h3 className="text-sm font-medium text-slate-600">{title}</h3>
      {account ? (
        <>
          <Link className="mt-1 block font-mono text-blue-700 hover:underline" to={`/accounts/${account.id}`}>{account.account_ref}</Link>
          <p className="text-xs text-slate-500 capitalize">{account.account_type}</p>
          <dl className="mt-2 grid grid-cols-2 gap-2">
            <Field label="Balance before" value={before && formatAmount(before)} />
            <Field label="Balance after" value={after && formatAmount(after)} />
          </dl>
        </>
      ) : (
        <p className="mt-1 text-sm text-slate-500">Not recorded for this transaction</p>
      )}
    </div>
  )
}

export default function TransactionDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const toast = useToast()
  const [changing, setChanging] = useState(false)
  const [newStatus, setNewStatus] = useState<TxStatus>('completed')
  const [reason, setReason] = useState('')

  const tx = useQuery({ queryKey: ['transaction', id], queryFn: ({ signal }) => api.get<TransactionDetail>(`/transactions/${id}/`, signal) })
  const related = useQuery({ queryKey: ['transaction', id, 'related'], queryFn: ({ signal }) => api.get<TransactionRow[]>(`/transactions/${id}/related/`, signal) })
  const events = useQuery({ queryKey: ['transaction', id, 'events'], queryFn: ({ signal }) => api.get<TransactionEvent[]>(`/transactions/${id}/events/`, signal) })

  const change = useMutation({
    mutationFn: () => api.patch<TransactionDetail>(`/transactions/${id}/status/`, { status: newStatus, reason }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['transaction', id] })
      void qc.invalidateQueries({ queryKey: ['transactions'] })
      toast('success', 'Status updated')
      setChanging(false)
      setReason('')
    },
    onError: (e) => toast('error', e instanceof ApiError ? Object.values(e.details).flat().join(' ') || e.message : 'Update failed'),
  })

  if (tx.isPending) return <LoadingState />
  if (tx.isError) return <ErrorState message={tx.error.message} onRetry={() => void tx.refetch()} />
  const t = tx.data

  return (
    <section className="space-y-6">
      <div>
        <Link to="/transactions" className="text-sm text-blue-700 hover:underline">← Transactions</Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-2xl font-semibold">{t.transaction_id}</h1>
          <StatusBadge status={t.status} />
          <PermissionGate permission="transactions.update_status">
            <Button variant="secondary" onClick={() => { setNewStatus(t.status); setChanging(true) }}>Change status</Button>
          </PermissionGate>
        </div>
        <p className="text-sm text-slate-600">{t.dataset_name}</p>
      </div>

      <dl className="grid grid-cols-2 gap-4 rounded-lg border border-slate-200 p-4 sm:grid-cols-4">
        <Field label="Amount" value={<span className="tabular-nums">{formatAmount(t.amount, t.currency)}</span>} />
        <Field label="Type" value={t.tx_type} />
        <Field label="Occurred" value={formatDateTime(t.occurred_at)} />
        <Field label="Dataset step" value={t.step} />
        <Field label="Merchant" value={t.merchant_name} />
        <Field label="Merchant category" value={t.merchant_category} />
        <Field label="Imported" value={formatDateTime(t.created_at)} />
      </dl>

      <div className="grid gap-4 sm:grid-cols-2">
        <AccountCard title="Sender" account={t.sender} before={t.sender_balance_before} after={t.sender_balance_after} />
        <AccountCard title="Receiver" account={t.receiver} before={t.receiver_balance_before} after={t.receiver_balance_after} />
      </div>

      <PermissionGate permission="behavior.read">
        <BehaviorPanel transactionId={t.id} />
      </PermissionGate>

      <div>
        <h2 className="text-lg font-semibold">Related transactions</h2>
        <p className="text-sm text-slate-600">Other transfers between these two accounts, in either direction.</p>
        <div className="mt-2">
          {related.isPending && <LoadingState />}
          {related.isError && <ErrorState message={related.error.message} onRetry={() => void related.refetch()} />}
          {related.data && related.data.length === 0 && <EmptyState title="No other transactions between these accounts" />}
          {related.data && related.data.length > 0 && <TransactionTable rows={related.data} />}
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold">Activity</h2>
        <div className="mt-2">
          {events.isPending && <LoadingState />}
          {events.isError && <ErrorState message={events.error.message} onRetry={() => void events.refetch()} />}
          {events.data && events.data.length === 0 && <EmptyState title="No recorded changes to this transaction" />}
          {events.data && events.data.length > 0 && (
            <ol className="space-y-2 border-l-2 border-slate-200 pl-4">
              {events.data.map((e) => (
                <li key={e.id} className="text-sm">
                  <span className="font-mono">{e.event_type}</span> · {formatDateTime(e.created_at)} · {e.actor_email ?? 'system'}
                  <pre className="mt-1 overflow-x-auto text-xs text-slate-600">{JSON.stringify(e.payload)}</pre>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>

      <p className="text-xs text-slate-500">
        Risk assessment, behavior, graph relationships, explanations, alerts and cases are added in later phases.
      </p>

      <Dialog open={changing} title="Change status" onClose={() => setChanging(false)}>
        <label className="block text-sm">New status
          <select className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5" value={newStatus} onChange={(e) => setNewStatus(e.target.value as TxStatus)}>
            {STATUSES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label className="mt-3 block text-sm">Reason (recorded in the audit trail)
          <input className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} />
        </label>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setChanging(false)}>Cancel</Button>
          <Button disabled={change.isPending || newStatus === t.status} onClick={() => change.mutate()}>Save</Button>
        </div>
      </Dialog>
    </section>
  )
}
