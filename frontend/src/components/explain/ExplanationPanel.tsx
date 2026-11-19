import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, ApiError, downloadFile } from '../../api/client'
import type { Explanation, ExplanationJob } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Button } from '../ui/Button'
import { ErrorState, LoadingState } from '../ui/states'
import { useToast } from '../ui/Toast'
import { AttributionChart } from './AttributionChart'

const DISCLAIMER = 'This explanation describes why a model, a rule or a risk score prioritised this transaction for review. It is automated evidence, not proof of wrongdoing; only an investigator’s recorded decision is a determination.'

/** Prediction / Indicator / Evidence / Assessment / Outcome for one transaction, tied to the exact model version. */
export function ExplanationPanel({ transactionId }: { transactionId: number }) {
  const { can } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [job, setJob] = useState<number | null>(null)
  const q = useQuery({ queryKey: ['tx-explanations', transactionId], queryFn: ({ signal }) => api.get<Explanation[]>(`/transactions/${transactionId}/explanations/`, signal) })
  const jobQ = useQuery({
    queryKey: ['explanation-job', job],
    enabled: job !== null,
    queryFn: ({ signal }) => api.get<ExplanationJob>(`/explanation-jobs/${job}/`, signal),
    refetchInterval: (query) => (query.state.data && (query.state.data.status === 'pending' || query.state.data.status === 'running') ? 1500 : false),
  })
  const generate = useMutation({
    mutationFn: () => api.post<ExplanationJob>(`/transactions/${transactionId}/explanations/`, {}),
    onSuccess: (j) => { setJob(j.id); toast('success', 'Generating explanation…') },
    onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Could not start'),
  })
  const jobStatus = jobQ.data?.status
  useEffect(() => {
    if (jobStatus === 'succeeded' || jobStatus === 'failed') void qc.invalidateQueries({ queryKey: ['tx-explanations', transactionId] })
  }, [jobStatus, qc, transactionId])
  if (q.isPending) return <LoadingState />
  if (q.isError) return <ErrorState message={q.error.message} onRetry={() => void q.refetch()} />
  const by = Object.fromEntries(q.data.map((e) => [e.method, e])) as Partial<Record<Explanation['method'], Explanation>>
  const stale = q.data.filter((e) => !e.current)
  const model = by.shap ?? by.lime
  const busy = generate.isPending || (jobQ.data !== undefined && (jobQ.data.status === 'pending' || jobQ.data.status === 'running'))
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Explanation</h2>
        <div className="flex gap-2">
          {can('explain.generate') && <Button variant="secondary" disabled={busy} onClick={() => generate.mutate()}>{q.data.length ? 'Regenerate' : 'Generate explanation'}</Button>}
          {q.data.length > 0 && <Button variant="secondary" onClick={() => void downloadFile(`/transactions/${transactionId}/explanations/report/`, `explanation-${transactionId}.pdf`).catch(() => toast('error', 'Download failed'))}>PDF report</Button>}
        </div>
      </div>
      {busy && <LoadingState label="Generating explanation…" />}
      {jobQ.data?.status === 'failed' && <p role="alert" className="text-sm text-red-700">Explanation failed: {jobQ.data.error_message}</p>}
      {jobQ.data?.status === 'succeeded' && Object.keys(jobQ.data.result.skipped).length > 0 && (
        <ul className="text-sm text-slate-600">{Object.entries(jobQ.data.result.skipped).map(([m, why]) => <li key={m}><strong>{m}</strong> not produced: {why}</li>)}</ul>
      )}
      {stale.length > 0 && (
        <p role="alert" className="rounded border border-amber-400 bg-amber-50 p-2 text-sm text-amber-900">
          Out of date: {stale.map((e) => `${e.method} (${e.stale_reason})`).join('; ')}. Regenerate before relying on it.
        </p>
      )}
      {q.data.length === 0 && !busy && <p className="text-sm text-slate-600">No explanation has been generated for this transaction yet.</p>}
      {model && (
        <p className="text-sm text-slate-600">Explains <strong>{model.model_version_name}</strong>, prediction #{model.prediction}, generator {model.generator_version}. {model.current ? 'This is the latest prediction of this model version.' : ''}</p>
      )}
      {model?.note && (
        <p role="status" className="text-sm text-slate-600">{model.note}</p>
      )}
      {by.summary?.payload.sections && (
        <dl className="space-y-2 rounded-md border border-slate-200 p-3 text-sm">
          {by.summary.payload.sections.map((s) => (<div key={s.title}><dt className="font-semibold">{s.title}</dt><dd className="text-slate-800">{s.text}</dd></div>))}
        </dl>
      )}
      {by.shap?.payload.features && (
        <div><h3 className="font-semibold">Why the model scored it this way (SHAP)</h3><p className="text-sm text-slate-700">{by.shap.narrative}</p><AttributionChart rows={by.shap.payload.features} /></div>
      )}
      {by.lime?.payload.features && (
        <div><h3 className="font-semibold">Local approximation (LIME)</h3><p className="text-sm text-slate-700">{by.lime.narrative}</p><AttributionChart rows={by.lime.payload.features} />
          <p className="text-xs text-slate-600">{by.lime.payload.note} Background: {by.lime.payload.background}.</p></div>
      )}
      {(['behavioral', 'graph', 'risk_breakdown'] as const).map((m) => by[m] && (
        <div key={m}><h3 className="font-semibold">{{ behavioral: 'Behaviour', graph: 'Network', risk_breakdown: 'Risk score' }[m]}</h3><p className="text-sm text-slate-700">{by[m]!.narrative}</p></div>
      ))}
      {by.summary?.payload.timeline && by.summary.payload.timeline.length > 0 && (
        <div><h3 className="font-semibold">Timeline</h3>
          <ol className="text-sm">{by.summary.payload.timeline.map((t) => (<li key={t.transaction_id} className={t.is_this_transaction ? 'font-semibold' : ''}><span className="text-slate-500">{t.occurred_at.slice(0, 16).replace('T', ' ')}</span> {t.sender} → {t.receiver ?? '—'} {t.amount} ({t.tx_type}){t.is_this_transaction && ' ← this transaction'}</li>))}</ol></div>
      )}
      <p role="note" className="text-xs text-slate-600">{DISCLAIMER}</p>
    </div>
  )
}
