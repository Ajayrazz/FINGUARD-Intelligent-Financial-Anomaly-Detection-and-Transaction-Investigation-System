import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { AlertDetail, AlertEventRow, AlertPolicy, AlertRow, AlertSummary, Dataset, NotificationRow, Paginated } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { AlertStatusBadge, SeverityBadge } from '../components/alerts/SeverityBadge'
import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/states'
import { useToast } from '../components/ui/Toast'
import { formatDateTime } from '../lib/format'

const TYPES = ['high_risk', 'multiple_transactions', 'unusual_activity', 'suspicious_beneficiary', 'failed_transactions', 'high_value', 'rapid_fund_movement', 'behavior_change', 'duplicate_record']
const OUTCOMES = [['true_positive', 'Confirmed (true positive)'], ['false_positive', 'False positive'], ['duplicate_of_other_alert', 'Duplicate of another alert'], ['other', 'Other']]

function AlertPanel({ id, onChanged }: { id: number; onChanged: () => void }) {
  const { can, user } = useAuth()
  const toast = useToast()
  const nav = useNavigate()
  const [reason, setReason] = useState('')
  const [outcome, setOutcome] = useState('false_positive')
  const [notes, setNotes] = useState('')
  const [assignee, setAssignee] = useState('')
  const q = useQuery({ queryKey: ['alert', id], queryFn: ({ signal }) => api.get<AlertDetail>(`/alerts/${id}/`, signal) })
  const events = useQuery({ queryKey: ['alert-events', id], queryFn: ({ signal }) => api.get<AlertEventRow[]>(`/alerts/${id}/events/`, signal) })
  const notifications = useQuery({ queryKey: ['alert-notifications', id], queryFn: ({ signal }) => api.get<NotificationRow[]>(`/alerts/${id}/notifications/`, signal) })
  const people = useQuery({ queryKey: ['alert-assignees'], enabled: can('alerts.assign'), queryFn: ({ signal }) => api.get<{ id: number; email: string; full_name: string }[]>('/alerts/assignees/', signal) })
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => api.post<AlertDetail>(`/alerts/${id}/${path}/`, body ?? {}),
    onSuccess: () => { void q.refetch(); void events.refetch(); onChanged() },
    onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Action failed'),
  })
  const makeCase = useMutation({
    mutationFn: () => api.post<{ id: number; case_ref: string }>(`/alerts/${id}/create-case/`, {}),
    onSuccess: (c) => { toast('success', `Case ${c.case_ref} opened`); onChanged(); nav(`/cases/${c.id}`) },
    onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Could not open a case'),
  })
  if (q.isPending) return <LoadingState />
  if (q.isError) return <ErrorState message={q.error.message} />
  const a = q.data
  const openCase = (a.cases ?? []).find((c) => c.status !== 'closed')
  const open = a.status !== 'closed'
  return (
    <div role="region" aria-label="Alert details" className="mt-4 space-y-3 rounded-md border border-slate-300 p-4">
      <h3 className="font-semibold">{a.type_label} <SeverityBadge severity={a.severity} /> <AlertStatusBadge status={a.status} /></h3>
      <p className="text-sm">{a.reason}</p>
      <p className="text-sm text-slate-600">
        {a.transaction && <>Transaction <Link className="text-blue-700 hover:underline" to={`/transactions/${a.transaction}`}>{a.transaction_external_id}</Link> · </>}
        {a.account && <>Account <Link className="font-mono text-blue-700 hover:underline" to={`/accounts/${a.account}`}>{a.account_ref}</Link> · </>}
        {a.risk_score !== null && <>risk score {a.risk_score.toFixed(1)} · </>}policy v{a.policy_version} · created {formatDateTime(a.created_at)}
        {a.assignee_email && <> · assigned to {a.assignee_email}</>}
      </p>
      <details><summary className="cursor-pointer text-sm font-medium">Evidence at the time the alert was created</summary>
        <pre className="mt-1 max-h-64 overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(a.evidence_snapshot, null, 2)}</pre></details>
      {(a.cases ?? []).length > 0 && <p className="text-sm">In case{(a.cases ?? []).length > 1 ? 's' : ''}: {(a.cases ?? []).map((c) => <Link key={c.id} className="mr-2 font-mono text-blue-700 hover:underline" to={`/cases/${c.id}`}>{c.case_ref} ({c.status.replace('_', ' ')})</Link>)}</p>}
      {open && !openCase && can('cases.create') && <Button variant="secondary" disabled={makeCase.isPending} onClick={() => makeCase.mutate()}>Open a case from this alert</Button>}
      {a.escalation_reason && <p className="text-sm"><strong>Escalated:</strong> {a.escalation_reason}</p>}
      {a.status === 'closed' && <p className="text-sm"><strong>Closed:</strong> {a.outcome.replace(/_/g, ' ')}{a.close_notes ? ` — ${a.close_notes}` : ''}</p>}
      {open && (
        <div className="flex flex-wrap items-end gap-3 text-sm">
          {can('alerts.acknowledge') && a.status === 'new' && <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'acknowledge' })}>Acknowledge</Button>}
          {can('alerts.assign') && (
            <label>Assign to{' '}<select className="rounded border border-slate-300 p-1" value={assignee} onChange={(e) => setAssignee(e.target.value)}><option value="">Select…</option>{(people.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name || p.email}</option>)}</select>{' '}
              <Button variant="secondary" disabled={!assignee || act.isPending} onClick={() => act.mutate({ path: 'assign', body: { assignee: Number(assignee) } })}>Assign</Button>{' '}
              {user && <Button variant="secondary" disabled={act.isPending} onClick={() => act.mutate({ path: 'assign', body: { assignee: user.id } })}>Assign to me</Button>}</label>
          )}
          {can('alerts.escalate') && a.status !== 'escalated' && (
            <label>Escalation reason{' '}<input className="w-56 rounded border border-slate-300 p-1" value={reason} onChange={(e) => setReason(e.target.value)} />{' '}
              <Button variant="secondary" disabled={!reason.trim() || act.isPending} onClick={() => act.mutate({ path: 'escalate', body: { reason } })}>Escalate</Button></label>
          )}
          {can('alerts.close') && (
            <label>Close as{' '}<select className="rounded border border-slate-300 p-1" value={outcome} onChange={(e) => setOutcome(e.target.value)}>{OUTCOMES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>{' '}
              <input aria-label="Closing notes" placeholder="notes" className="w-40 rounded border border-slate-300 p-1" value={notes} onChange={(e) => setNotes(e.target.value)} />{' '}
              <Button variant="secondary" disabled={act.isPending} onClick={() => act.mutate({ path: 'close', body: { outcome, notes } })}>Close alert</Button></label>
          )}
        </div>
      )}
      <div><h4 className="text-sm font-semibold">History</h4>
        <ol className="text-sm">{(events.data ?? []).map((e) => <li key={e.id}><span className="text-slate-500">{formatDateTime(e.created_at)}</span> {e.event_type.replace(/_/g, ' ')}{e.actor_email ? ` by ${e.actor_email}` : ' (automatic)'}</li>)}</ol></div>
      {(notifications.data ?? []).length > 0 && <p className="text-xs text-slate-600">Notifications: {(notifications.data ?? []).map((n) => `${n.channel} ${n.status}`).join(', ')}</p>}
    </div>
  )
}

function PolicyCard({ canConfigure }: { canConfigure: boolean }) {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['alert-policies'], queryFn: ({ signal }) => api.get<AlertPolicy[]>('/alerts/policy/', signal) })
  const active = q.data?.find((p) => p.is_active)
  const [text, setText] = useState<string | null>(null)
  const create = useMutation({
    mutationFn: () => api.post<AlertPolicy>('/alerts/policy/', { config: JSON.parse(text ?? '{}') }),
    onSuccess: () => { toast('success', 'New policy version created (not active yet)'); void qc.invalidateQueries({ queryKey: ['alert-policies'] }) },
    onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Invalid JSON'),
  })
  const activate = useMutation({
    mutationFn: (id: number) => api.post(`/alerts/policy/${id}/activate/`),
    onSuccess: () => { toast('success', 'Policy activated'); void qc.invalidateQueries({ queryKey: ['alert-policies'] }) },
  })
  if (q.isPending || !active) return null
  const cfg = active.config as Record<string, Record<string, unknown> | number | boolean>
  return (
    <details className="rounded-md border border-slate-200 p-3 text-sm">
      <summary className="cursor-pointer font-semibold">Alert policy v{active.version} (active)</summary>
      <p className="mt-1 text-slate-700">Per-rule cap {String(cfg.max_alerts_per_rule ?? 500)} · same event within {String(cfg.dedup_bucket_hours)} h is one alert · email from {String((cfg.email as { min_severity: string }).min_severity)} severity to {((cfg.email as { recipients: string[] }).recipients).length} recipient(s) · automatic evaluation {cfg.auto_evaluate ? 'on' : 'off'}</p>
      {canConfigure && (
        <div className="mt-2 space-y-2">
          <textarea aria-label="Policy JSON" className="h-48 w-full rounded border border-slate-300 p-2 font-mono text-xs" value={text ?? JSON.stringify(active.config, null, 2)} onChange={(e) => setText(e.target.value)} />
          <div className="flex flex-wrap gap-2"><Button disabled={create.isPending} onClick={() => create.mutate()}>Create new version</Button>
            {(q.data ?? []).filter((p) => !p.is_active).slice(0, 3).map((p) => <Button key={p.id} variant="secondary" onClick={() => activate.mutate(p.id)}>Activate v{p.version}</Button>)}</div>
        </div>
      )}
    </details>
  )
}

export default function AlertsPage() {
  const { can } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [params] = useSearchParams()
  const [status, setStatus] = useState('open')
  const [severity, setSeverity] = useState('')
  const [type, setType] = useState('')
  const [assignee, setAssignee] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<number | null>(params.get('open') ? Number(params.get('open')) : null)
  const [dataset, setDataset] = useState('')
  const qs = `page=${page}${status === 'open' ? '&open=true' : status ? `&status=${status}` : ''}${severity ? `&severity=${severity}` : ''}${type ? `&alert_type=${type}` : ''}${assignee ? `&assignee=${assignee}` : ''}`
  const list = useQuery({ queryKey: ['alerts', qs], queryFn: ({ signal }) => api.get<Paginated<AlertRow>>(`/alerts/?${qs}`, signal) })
  const summary = useQuery({ queryKey: ['alerts-summary'], queryFn: ({ signal }) => api.get<AlertSummary>('/alerts/summary/', signal) })
  const datasets = useQuery({ queryKey: ['datasets'], enabled: can('alerts.run'), queryFn: ({ signal }) => api.get<Dataset[]>('/datasets/', signal) })
  const evaluate = useMutation({
    mutationFn: () => api.post('/alerts/evaluate/', { dataset: Number(dataset) }),
    onSuccess: () => { toast('success', 'Evaluating alert rules…'); setTimeout(() => { void qc.invalidateQueries({ queryKey: ['alerts'] }); void qc.invalidateQueries({ queryKey: ['alerts-summary'] }) }, 4000) },
    onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Could not start'),
  })
  const refresh = () => { void qc.invalidateQueries({ queryKey: ['alerts'] }); void qc.invalidateQueries({ queryKey: ['alerts-summary'] }) }
  const sel = (set: (v: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => { set(e.target.value); setPage(1) }
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Alerts</h1>
      <p className="text-sm text-slate-600">Prioritised queue: open before closed, then severity, then risk score, then newest. The same event never makes a second alert.</p>
      {summary.data && (
        <ul aria-label="Open alerts by severity" className="flex flex-wrap gap-4 text-sm">
          {(['critical', 'high', 'medium', 'low'] as const).map((s) => <li key={s} className="rounded border border-slate-200 px-3 py-1"><SeverityBadge severity={s} /> <span className="tabular-nums">{summary.data.open_by_severity[s]}</span></li>)}
          <li className="rounded border border-slate-200 px-3 py-1">Unassigned open <span className="tabular-nums">{summary.data.unassigned_open}</span></li>
        </ul>
      )}
      <div className="flex flex-wrap items-end gap-4 text-sm">
        <label>Status<select className="ml-1 rounded border border-slate-300 p-1" value={status} onChange={sel(setStatus)}><option value="open">Open</option><option value="">All</option><option value="new">New</option><option value="acknowledged">Acknowledged</option><option value="escalated">Escalated</option><option value="closed">Closed</option></select></label>
        <label>Severity<select className="ml-1 rounded border border-slate-300 p-1" value={severity} onChange={sel(setSeverity)}><option value="">All</option>{['critical', 'high', 'medium', 'low'].map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
        <label>Type<select className="ml-1 rounded border border-slate-300 p-1" value={type} onChange={sel(setType)}><option value="">All</option>{TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}</select></label>
        <label>Assigned<select className="ml-1 rounded border border-slate-300 p-1" value={assignee} onChange={sel(setAssignee)}><option value="">Anyone</option><option value="me">Me</option><option value="none">Unassigned</option></select></label>
        {can('alerts.run') && (
          <span className="ml-auto flex items-end gap-2"><label>Evaluate rules for<select className="ml-1 rounded border border-slate-300 p-1" value={dataset} onChange={(e) => setDataset(e.target.value)}><option value="">dataset…</option>{(datasets.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
            <Button variant="secondary" disabled={!dataset || evaluate.isPending} onClick={() => evaluate.mutate()}>Evaluate</Button></span>
        )}
      </div>
      {list.isPending && <LoadingState />}
      {list.isError && <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />}
      {list.data && list.data.results.length === 0 && <EmptyState title="No alerts match these filters" hint="Alerts appear when risk scoring, behaviour, graph or duplicate results cross the policy thresholds." />}
      {list.data && list.data.results.length > 0 && (
        <>
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-300 text-slate-600"><tr><th className="py-1">#</th><th>Severity</th><th>Type</th><th>Reason</th><th>Status</th><th>Assigned</th><th>Created</th></tr></thead>
            <tbody>
              {list.data.results.map((a) => (
                <tr key={a.id} className={`border-b border-slate-100 align-top ${selected === a.id ? 'bg-slate-100' : ''}`}>
                  <td className="py-1"><button className="text-blue-700 hover:underline" onClick={() => setSelected(a.id)}>{a.id}</button></td>
                  <td><SeverityBadge severity={a.severity} /></td><td>{a.type_label}</td><td className="max-w-md">{a.reason}</td>
                  <td><AlertStatusBadge status={a.status} /></td><td>{a.assignee_email ?? '—'}</td><td className="whitespace-nowrap">{formatDateTime(a.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center gap-3 text-sm">
            <Button variant="secondary" disabled={!list.data.previous} onClick={() => setPage((p) => p - 1)}>Previous</Button>
            <span>Page {page} · {list.data.count.toLocaleString()} alerts</span>
            <Button variant="secondary" disabled={!list.data.next} onClick={() => setPage((p) => p + 1)}>Next</Button>
          </div>
        </>
      )}
      {selected !== null && <AlertPanel key={selected} id={selected} onChanged={refresh} />}
      <PolicyCard canConfigure={can('alerts.configure')} />
    </section>
  )
}
