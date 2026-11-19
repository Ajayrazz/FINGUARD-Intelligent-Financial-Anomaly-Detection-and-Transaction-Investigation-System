import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api/client'
import type { CaseAccountRow, CaseDetail, CaseEventRow, CaseEvidenceRow, CaseNoteRow, CaseOutcome, CaseStatus, CaseTransactionRow } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { SeverityBadge } from '../components/alerts/SeverityBadge'
import { CaseStatusBadge, OUTCOME_LABEL, PriorityBadge, STATUS_LABEL } from '../components/cases/CaseBadges'
import { Button } from '../components/ui/Button'
import { ErrorState, LoadingState } from '../components/ui/states'
import { useToast } from '../components/ui/Toast'
import { formatAmount, formatDateTime } from '../lib/format'

const move: Record<CaseStatus, string> = { new: 'New', under_review: 'Take for review', investigation: 'Start investigation', escalated: 'Escalate', resolved: 'Resolve', closed: 'Close case' }

function Actions({ c, onDone }: { c: CaseDetail; onDone: () => void }) {
  const toast = useToast()
  const [reason, setReason] = useState('')
  const [outcome, setOutcome] = useState<CaseOutcome>('inconclusive')
  const [summary, setSummary] = useState('')
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) => api.post(`/cases/${c.id}/${path}/`, body),
    onSuccess: onDone,
    onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Action failed'),
  })
  const t = c.allowed_transitions
  if (t.length === 0) return <p className="text-sm text-slate-600">{c.status === 'closed' ? 'No further actions: the case is closed.' : 'You cannot move this case further with your permissions.'}</p>
  return (
    <div className="flex flex-wrap items-end gap-3 text-sm">
      {t.includes('under_review') && <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'transition', body: { to_status: 'under_review' } })}>{move.under_review}</Button>}
      {t.includes('investigation') && <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'transition', body: { to_status: 'investigation' } })}>{c.status === 'escalated' ? 'Return to investigation' : move.investigation}</Button>}
      {t.includes('escalated') && (
        <label>Escalation reason <input className="w-56 rounded border border-slate-300 p-1" value={reason} onChange={(e) => setReason(e.target.value)} />{' '}
          <Button variant="secondary" disabled={!reason.trim() || act.isPending} onClick={() => act.mutate({ path: 'escalate', body: { reason } })}>Escalate</Button></label>
      )}
      {t.includes('resolved') && (
        <span className="flex flex-wrap items-end gap-2"><label>Outcome <select className="rounded border border-slate-300 p-1" value={outcome} onChange={(e) => setOutcome(e.target.value as CaseOutcome)}>{(Object.keys(OUTCOME_LABEL) as CaseOutcome[]).map((o) => <option key={o} value={o}>{OUTCOME_LABEL[o]}</option>)}</select></label>
          <label>Resolution summary <input className="w-64 rounded border border-slate-300 p-1" value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
          <Button variant="secondary" disabled={!summary.trim() || act.isPending} onClick={() => act.mutate({ path: 'resolve', body: { outcome, summary } })}>Resolve</Button></span>
      )}
      {t.includes('closed') && <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'close', body: {} })}>{move.closed}</Button>}
    </div>
  )
}

function Notes({ c, canWrite }: { c: CaseDetail; canWrite: boolean }) {
  const { can, user } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [kind, setKind] = useState<'comment' | 'note'>('comment')
  const [body, setBody] = useState('')
  const [editing, setEditing] = useState<number | null>(null)
  const [draft, setDraft] = useState('')
  const [history, setHistory] = useState<{ revision: number; body: string; edited_by: string }[] | null>(null)
  const notes = useQuery({ queryKey: ['case-notes', c.id], queryFn: ({ signal }) => api.get<CaseNoteRow[]>(`/cases/${c.id}/notes/`, signal) })
  const refresh = () => { void qc.invalidateQueries({ queryKey: ['case-notes', c.id] }); void qc.invalidateQueries({ queryKey: ['case-events', c.id] }) }
  const add = useMutation({ mutationFn: () => api.post(`/cases/${c.id}/notes/`, { kind, body }), onSuccess: () => { setBody(''); refresh() }, onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Failed') })
  const edit = useMutation({ mutationFn: (id: number) => api.patch(`/cases/${c.id}/notes/${id}/`, { body: draft }), onSuccess: () => { setEditing(null); refresh() }, onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Failed') })
  return (
    <div>
      <h2 className="text-lg font-semibold">Comments and notes</h2>
      <ul className="mt-1 space-y-2 text-sm">
        {(notes.data ?? []).map((n) => (
          <li key={n.id} className="rounded border border-slate-200 p-2">
            <p className="text-xs text-slate-500"><span className="capitalize">{n.kind}</span> · {n.author_email} · {formatDateTime(n.created_at)}{n.edited && ` · edited (${n.revision_count} versions)`}</p>
            {editing === n.id ? (
              <div className="mt-1 flex gap-2"><input aria-label="Edit text" className="w-full rounded border border-slate-300 p-1" value={draft} onChange={(e) => setDraft(e.target.value)} /><Button disabled={edit.isPending} onClick={() => edit.mutate(n.id)}>Save</Button></div>
            ) : <p className="whitespace-pre-wrap">{n.body}</p>}
            <p className="mt-1 text-xs">
              {n.edited && <button className="mr-3 text-blue-700 hover:underline" onClick={() => void api.get<{ revision: number; body: string; edited_by: string }[]>(`/cases/${c.id}/notes/${n.id}/`).then(setHistory)}>Show earlier versions</button>}
              {canWrite && user?.id === n.author && editing !== n.id && <button className="text-blue-700 hover:underline" onClick={() => { setEditing(n.id); setDraft(n.body) }}>Edit</button>}
            </p>
          </li>
        ))}
      </ul>
      {history && <div role="region" aria-label="Earlier versions" className="mt-2 rounded border border-slate-300 p-2 text-sm"><p className="font-semibold">Versions</p><ol>{history.map((h) => <li key={h.revision}>v{h.revision} ({h.edited_by}): {h.body}</li>)}</ol><button className="text-xs text-blue-700" onClick={() => setHistory(null)}>Hide</button></div>}
      {canWrite && (
        <div className="mt-2 flex flex-wrap items-end gap-2 text-sm">
          {can('cases.note') && <label>Type <select className="rounded border border-slate-300 p-1" value={kind} onChange={(e) => setKind(e.target.value as 'comment' | 'note')}><option value="comment">Comment</option><option value="note">Investigation note</option></select></label>}
          <label className="flex-1">Add <input className="w-full min-w-48 rounded border border-slate-300 p-1.5" value={body} onChange={(e) => setBody(e.target.value)} /></label>
          <Button disabled={!body.trim() || add.isPending} onClick={() => add.mutate()}>Post</Button>
        </div>
      )}
    </div>
  )
}

function Evidence({ c, canUpload }: { c: CaseDetail; canUpload: boolean }) {
  const { can } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const ev = useQuery({ queryKey: ['case-evidence', c.id], queryFn: ({ signal }) => api.get<CaseEvidenceRow[]>(`/cases/${c.id}/evidence/`, signal) })
  const upload = useMutation({
    mutationFn: (file: File) => { const fd = new FormData(); fd.append('file', file); return api.post(`/cases/${c.id}/evidence/`, fd) },
    onSuccess: () => { toast('success', 'Evidence stored'); void qc.invalidateQueries({ queryKey: ['case-evidence', c.id] }); void qc.invalidateQueries({ queryKey: ['case-events', c.id] }) },
    onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Upload failed'),
  })
  return (
    <div>
      <h2 className="text-lg font-semibold">Evidence</h2>
      {canUpload && <label className="mt-1 block text-sm"><span className="font-medium">Add evidence (PDF, PNG, JPEG or text, up to 20 MB)</span><input className="mt-1 block" type="file" accept="application/pdf,image/png,image/jpeg,text/plain,text/csv" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = '' }} /></label>}
      <ul className="mt-1 text-sm">
        {(ev.data ?? []).map((e) => (
          <li key={e.id} className="border-b border-slate-100 py-1">{e.original_name} <span className="text-slate-500">· {(e.size / 1024).toFixed(1)} KB · {e.uploaded_by_email} · {formatDateTime(e.created_at)}</span>
            <br /><span className="font-mono text-xs text-slate-500" title={e.sha256}>SHA-256 {e.sha256.slice(0, 16)}…</span>
            {can('cases.evidence') && <> <button className="text-blue-700 hover:underline" onClick={() => void downloadFile(`/cases/${c.id}/evidence/${e.id}/download/`, e.original_name).catch((err: unknown) => toast('error', err instanceof ApiError ? err.message : 'Download failed'))}>Download</button></>}</li>
        ))}
        {ev.data?.length === 0 && <li className="text-slate-600">No evidence attached.</li>}
      </ul>
    </div>
  )
}

export default function CaseDetailPage() {
  const { id = '' } = useParams()
  const { can, user } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [txId, setTxId] = useState('')
  const [assignee, setAssignee] = useState('')
  const caseQ = useQuery({ queryKey: ['case', id], queryFn: ({ signal }) => api.get<CaseDetail>(`/cases/${id}/`, signal) })
  const events = useQuery({ queryKey: ['case-events', id], queryFn: ({ signal }) => api.get<CaseEventRow[]>(`/cases/${id}/events/`, signal) })
  const txs = useQuery({ queryKey: ['case-txs', id], queryFn: ({ signal }) => api.get<CaseTransactionRow[]>(`/cases/${id}/transactions/`, signal) })
  const accts = useQuery({ queryKey: ['case-accounts', id], queryFn: ({ signal }) => api.get<CaseAccountRow[]>(`/cases/${id}/accounts/`, signal) })
  const people = useQuery({ queryKey: ['case-assignees'], enabled: can('cases.assign'), queryFn: ({ signal }) => api.get<{ id: number; email: string; full_name: string }[]>('/cases/assignees/', signal) })
  const refresh = () => { for (const k of ['case', 'case-events', 'case-txs', 'case-accounts']) void qc.invalidateQueries({ queryKey: [k, id] }); void qc.invalidateQueries({ queryKey: ['cases'] }) }
  const assign = useMutation({ mutationFn: (who: number) => api.post(`/cases/${id}/assign/`, { assignee: who }), onSuccess: refresh, onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Failed') })
  const addTx = useMutation({ mutationFn: () => api.post(`/cases/${id}/transactions/`, { transaction: Number(txId) }), onSuccess: () => { setTxId(''); refresh() }, onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Failed') })
  if (caseQ.isPending) return <LoadingState />
  if (caseQ.isError) return <ErrorState message={caseQ.error.message} onRetry={() => void caseQ.refetch()} />
  const c = caseQ.data
  const closed = c.status === 'closed'
  return (
    <section className="space-y-5">
      <p className="text-sm"><Link className="text-blue-700 hover:underline" to="/cases">← Investigations</Link></p>
      <div>
        <h1 className="text-2xl font-semibold"><span className="font-mono">{c.case_ref}</span> · {c.title}</h1>
        <p className="mt-1 text-sm"><CaseStatusBadge status={c.status} /> <PriorityBadge priority={c.priority} /> · opened {formatDateTime(c.opened_at)}{c.created_by_email ? ` by ${c.created_by_email}` : ' automatically'} · assigned to {c.assignee_email ?? 'nobody'}</p>
        {c.description && <p className="mt-1 text-sm text-slate-700">{c.description}</p>}
      </div>
      {closed && <p role="status" className="rounded border border-slate-300 bg-slate-50 p-2 text-sm">{c.read_only_reason}</p>}
      {c.outcome && <p className="rounded border border-slate-200 p-2 text-sm"><strong>Outcome (set by {c.resolved_by_email ?? 'an investigator'}):</strong> {OUTCOME_LABEL[c.outcome]} — {c.resolution_summary}</p>}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Actions c={c} onDone={refresh} />
        <div className="flex gap-2">
          {can('cases.assign') && !closed && (
            <label className="text-sm">Assign <select className="rounded border border-slate-300 p-1" value={assignee} onChange={(e) => setAssignee(e.target.value)}><option value="">Select…</option>{(people.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name || p.email}</option>)}</select>{' '}
              <Button variant="secondary" disabled={!assignee || assign.isPending} onClick={() => assign.mutate(Number(assignee))}>Assign</Button>{' '}{user && <Button variant="secondary" disabled={assign.isPending} onClick={() => assign.mutate(user.id)}>Assign to me</Button>}</label>
          )}
          <Button variant="secondary" onClick={() => void downloadFile(`/cases/${id}/report/`, `case-${c.case_ref}.pdf`).catch(() => toast('error', 'Download failed'))}>PDF report</Button>
        </div>
      </div>
      <div><h2 className="text-lg font-semibold">Alerts</h2>
        <ul className="text-sm">{c.alerts.map((a) => <li key={a.id}><SeverityBadge severity={a.severity} /> <Link className="text-blue-700 hover:underline" to={`/alerts?open=${a.id}`}>{a.type_label}</Link>: {a.reason}</li>)}{c.alerts.length === 0 && <li className="text-slate-600">No alerts linked.</li>}</ul></div>
      <div><h2 className="text-lg font-semibold">Transactions</h2>
        {txs.data && txs.data.length > 0 && (
          <table className="w-full text-left text-sm"><thead className="border-b border-slate-300 text-slate-600"><tr><th className="py-1">Transaction</th><th>Time</th><th>Type</th><th className="text-right">Amount</th><th>From</th><th>To</th><th>Note</th></tr></thead>
            <tbody>{txs.data.map((t) => <tr key={t.id} className="border-b border-slate-100"><td className="py-1"><Link className="text-blue-700 hover:underline" to={`/transactions/${t.transaction}`}>{t.external_id}</Link></td><td className="whitespace-nowrap">{formatDateTime(t.occurred_at)}</td><td>{t.tx_type}</td><td className="text-right tabular-nums">{formatAmount(t.amount)}</td><td className="font-mono">{t.sender}</td><td className="font-mono">{t.receiver ?? '—'}</td><td>{t.note}</td></tr>)}</tbody></table>
        )}
        {txs.data?.length === 0 && <p className="text-sm text-slate-600">No transactions attached.</p>}
        {can('cases.update') && !closed && <p className="mt-1 text-sm"><label>Add transaction by id <input className="w-24 rounded border border-slate-300 p-1" value={txId} onChange={(e) => setTxId(e.target.value.replace(/\D/g, ''))} /></label> <Button variant="secondary" disabled={!txId || addTx.isPending} onClick={() => addTx.mutate()}>Add</Button></p>}</div>
      <div><h2 className="text-lg font-semibold">Accounts involved</h2>
        <ul className="text-sm">{(accts.data ?? []).map((a) => <li key={a.id}><Link className="font-mono text-blue-700 hover:underline" to={`/accounts/${a.id}`}>{a.account_ref}</Link> <span className="text-slate-500">({a.roles.join(', ')})</span>{can('graph.read') && <> · <Link className="text-blue-700 hover:underline" to={`/accounts/${a.id}/graph`}>network</Link></>}</li>)}{accts.data?.length === 0 && <li className="text-slate-600">No accounts yet.</li>}</ul></div>
      <Notes c={c} canWrite={can('cases.comment') && !closed} />
      <Evidence c={c} canUpload={can('cases.evidence') && !closed} />
      <div><h2 className="text-lg font-semibold">Timeline</h2>
        <ol className="text-sm">{(events.data ?? []).map((e) => <li key={e.id}><span className="text-slate-500">{formatDateTime(e.created_at)}</span> {e.event_type.replace(/_/g, ' ')}{e.to_status && ` (${STATUS_LABEL[e.from_status as CaseStatus] ?? 'start'} → ${STATUS_LABEL[e.to_status as CaseStatus]})`} · {e.actor_email ?? 'automatic'}</li>)}</ol></div>
      <p role="note" className="text-xs text-slate-600">Alerts, scores and model outputs are automated indicators for prioritising review, not proof of wrongdoing. The outcome above is the investigator’s determination.</p>
    </section>
  )
}
