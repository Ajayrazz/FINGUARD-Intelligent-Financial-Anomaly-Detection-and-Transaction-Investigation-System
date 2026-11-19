import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Dataset, Paginated, RiskAssessment, RiskAssessmentDetail, RiskCategory, RiskConfig, RiskRun } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { RunStatusBadge, isRunActive } from '../components/detection/RunStatusBadge'
import { BreakdownTable } from '../components/risk/BreakdownTable'
import { RiskBadge } from '../components/risk/RiskBadge'
import { CATEGORY_LABEL, COMPONENT_LABEL, COMPONENT_ORDER } from '../components/risk/riskLabels'
import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/states'
import { useToast } from '../components/ui/Toast'
import { formatDateTime } from '../lib/format'

const CATEGORIES: RiskCategory[] = ['critical', 'high', 'medium', 'low', 'unscored']

function ConfigCard({ cfg, canConfigure, onActivated }: { cfg: RiskConfig; canConfigure: boolean; onActivated: () => void }) {
  const toast = useToast()
  const activate = useMutation({
    mutationFn: () => api.post(`/risk/config/${cfg.id}/activate/`),
    onSuccess: () => { toast('success', `Version ${cfg.version} is now active`); onActivated() },
    onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Could not activate'),
  })
  return (
    <div className={`rounded-md border p-3 text-sm ${cfg.is_active ? 'border-slate-900' : 'border-slate-200'}`}>
      <p className="font-semibold">Version {cfg.version} {cfg.is_active && <span className="rounded bg-slate-900 px-1.5 text-xs font-normal text-white">active</span>} <span className="font-normal capitalize text-slate-500">· {cfg.source}</span></p>
      <p className="mt-1 text-slate-700">{COMPONENT_ORDER.map((k) => `${k} ${(cfg.weights[k] * 100).toFixed(0)}%`).join(' · ')}</p>
      <p className="text-slate-700">Medium ≥ {cfg.thresholds.medium} · High ≥ {cfg.thresholds.high} · Critical ≥ {cfg.thresholds.critical} · policy {cfg.missing_signal_policy} · min coverage {(cfg.min_coverage * 100).toFixed(0)}%{cfg.model_version_name && ` · model ${cfg.model_version_name}`}</p>
      {cfg.notes && <p className="mt-1 text-xs text-slate-500">{cfg.notes}</p>}
      {canConfigure && !cfg.is_active && <Button className="mt-2" variant="secondary" disabled={activate.isPending} onClick={() => activate.mutate()}>Activate version {cfg.version}</Button>}
    </div>
  )
}

function NewConfigForm({ base, onCreated }: { base: RiskConfig; onCreated: () => void }) {
  const toast = useToast()
  const [w, setW] = useState<Record<string, string>>(Object.fromEntries(COMPONENT_ORDER.map((k) => [k, String(base.weights[k])])))
  const [t, setT] = useState<Record<string, string>>({ medium: String(base.thresholds.medium), high: String(base.thresholds.high), critical: String(base.thresholds.critical) })
  const [policy, setPolicy] = useState<string>(base.missing_signal_policy)
  const [minCov, setMinCov] = useState(String(base.min_coverage))
  const sum = COMPONENT_ORDER.reduce((s, k) => s + Number(w[k]), 0)
  const create = useMutation({
    mutationFn: () => api.post('/risk/config/', {
      weights: Object.fromEntries(COMPONENT_ORDER.map((k) => [k, Number(w[k])])),
      thresholds: { medium: Number(t.medium), high: Number(t.high), critical: Number(t.critical) },
      missing_signal_policy: policy, min_coverage: Number(minCov),
    }),
    onSuccess: () => { toast('success', 'New version created (not active yet)'); onCreated() },
    onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Invalid configuration'),
  })
  return (
    <form className="mt-3 space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm" onSubmit={(e) => { e.preventDefault(); create.mutate() }}>
      <h3 className="font-semibold">New configuration version</h3>
      <div className="flex flex-wrap gap-3">
        {COMPONENT_ORDER.map((k) => (
          <label key={k}>{COMPONENT_LABEL[k].name} weight<input aria-label={`${COMPONENT_LABEL[k].name} weight`} className="ml-1 w-16 rounded border border-slate-300 p-1" type="number" step="0.01" min="0" max="1" value={w[k]} onChange={(e) => setW({ ...w, [k]: e.target.value })} /></label>
        ))}
      </div>
      <p className={Math.abs(sum - 1) < 1e-6 ? 'text-green-800' : 'text-red-700'}>Weights sum to {sum.toFixed(2)} (must be 1.00)</p>
      <div className="flex flex-wrap gap-3">
        {(['medium', 'high', 'critical'] as const).map((k) => <label key={k} className="capitalize">{k} from<input aria-label={`${k} threshold`} className="ml-1 w-16 rounded border border-slate-300 p-1" type="number" value={t[k]} onChange={(e) => setT({ ...t, [k]: e.target.value })} /></label>)}
        <label>Missing signals<select className="ml-1 rounded border border-slate-300 p-1" value={policy} onChange={(e) => setPolicy(e.target.value)}><option value="renormalize">Renormalise</option><option value="neutral_prior">Neutral prior</option><option value="strict">Strict (no score)</option></select></label>
        <label>Min coverage<input aria-label="Minimum coverage" className="ml-1 w-16 rounded border border-slate-300 p-1" type="number" step="0.05" min="0" max="1" value={minCov} onChange={(e) => setMinCov(e.target.value)} /></label>
      </div>
      <Button type="submit" disabled={create.isPending}>Create version</Button>
    </form>
  )
}

export default function RiskAnalysisPage() {
  const { can } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [dataset, setDataset] = useState('')
  const [category, setCategory] = useState<'' | RiskCategory>('')
  const [selected, setSelected] = useState<number | null>(null)
  const datasets = useQuery({ queryKey: ['datasets'], queryFn: ({ signal }) => api.get<Dataset[]>('/datasets/', signal) })
  const configs = useQuery({ queryKey: ['risk-configs'], queryFn: ({ signal }) => api.get<RiskConfig[]>('/risk/config/', signal) })
  const runs = useQuery({
    queryKey: ['risk-runs'],
    queryFn: ({ signal }) => api.get<Paginated<RiskRun>>('/risk/runs/', signal),
    refetchInterval: (query) => (query.state.data?.results.some((r) => isRunActive(r.status)) ? 3000 : false),
  })
  const latest = (runs.data?.results ?? []).find((r) => String(r.dataset) === dataset && r.status === 'succeeded')
  const start = useMutation({
    mutationFn: () => api.post<RiskRun>('/risk/runs/', { dataset: Number(dataset) }),
    onSuccess: () => { toast('success', 'Risk scoring started'); void qc.invalidateQueries({ queryKey: ['risk-runs'] }) },
    onError: (e: unknown) => toast('error', e instanceof ApiError ? e.message : 'Could not start'),
  })
  const rows = useQuery({
    queryKey: ['risk-assessments', latest?.id, category],
    enabled: !!latest,
    queryFn: ({ signal }) => api.get<Paginated<RiskAssessment>>(`/risk/assessments/?run=${latest!.id}&scored=true${category ? `&category=${category}` : ''}`, signal),
  })
  const detail = useQuery({
    queryKey: ['risk-assessment', selected],
    enabled: selected !== null,
    queryFn: ({ signal }) => api.get<RiskAssessmentDetail>(`/risk/assessments/${selected}/`, signal),
  })
  const active = configs.data?.find((c) => c.is_active)
  const total = latest ? Math.max(latest.rows_total, 1) : 1
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Risk Analysis</h1>
      <p className="text-sm text-slate-600">One 0–100 score per transaction from six signals, with every component and the signal coverage shown. Scores prioritise review; they are not findings.</p>

      <div className="flex flex-wrap items-end gap-3 rounded-md border border-slate-200 bg-slate-50 p-4">
        <label className="text-sm"><span className="block font-medium">Dataset</span>
          <select className="mt-1 w-80 rounded border border-slate-300 p-1.5" value={dataset} onChange={(e) => { setDataset(e.target.value); setSelected(null) }}>
            <option value="">Select…</option>{(datasets.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.name} ({d.row_count.toLocaleString()} rows)</option>)}
          </select></label>
        {can('risk.run') && <Button disabled={!dataset || start.isPending} onClick={() => start.mutate()}>Score with active configuration</Button>}
        <p className="basis-full text-xs text-slate-600">Uses the latest detection run, behavioural analysis, graph snapshot and duplicate scan of the dataset. Signals that were never run show as unavailable.</p>
      </div>

      <div>
        <h2 className="font-semibold">Configuration</h2>
        {configs.isPending && <LoadingState />}
        {configs.isError && <ErrorState message={configs.error.message} />}
        {configs.data && (
          <div className="mt-1 grid gap-2 sm:grid-cols-2">
            {configs.data.slice(0, 4).map((c) => <ConfigCard key={c.id} cfg={c} canConfigure={can('risk.configure')} onActivated={() => void qc.invalidateQueries({ queryKey: ['risk-configs'] })} />)}
          </div>
        )}
        {can('risk.configure') && active && <NewConfigForm key={active.id} base={active} onCreated={() => void qc.invalidateQueries({ queryKey: ['risk-configs'] })} />}
      </div>

      {dataset && !latest && !runs.isPending && <EmptyState title="No finished risk run for this dataset" hint={can('risk.run') ? 'Start one above.' : undefined} />}
      {latest && (
        <>
          <div>
            <h2 className="font-semibold">Run #{latest.id} <RunStatusBadge status={latest.status} /> <span className="text-sm font-normal text-slate-600">· config v{latest.config_version} · {latest.rows_scored.toLocaleString()} scored · {latest.finished_at ? formatDateTime(latest.finished_at) : ''}</span></h2>
            <ul className="mt-1 space-y-1 text-sm" aria-label="Category distribution">
              {CATEGORIES.map((c) => {
                const n = latest.category_counts[c] ?? 0
                return (
                  <li key={c} className="flex items-center gap-2"><span className="w-20">{CATEGORY_LABEL[c]}</span>
                    <span className="h-3 rounded bg-slate-500" style={{ width: `${Math.max((n / total) * 100, n > 0 ? 1 : 0)}%`, maxWidth: '60%' }} aria-hidden />
                    <span className="tabular-nums">{n.toLocaleString()}</span></li>
                )
              })}
            </ul>
            <p className="mt-1 text-xs text-slate-600">Signal coverage in this run: {Object.entries(latest.coverage_summary).map(([k, v]) => `${(Number(k) * 100).toFixed(0)}% → ${v.toLocaleString()}`).join(' · ')}</p>
          </div>
          <div>
            <div className="flex items-center justify-between"><h2 className="font-semibold">Highest-scoring transactions</h2>
              <label className="text-sm">Category{' '}<select className="rounded border border-slate-300 p-1" value={category} onChange={(e) => setCategory(e.target.value as '' | RiskCategory)}><option value="">All scored</option>{CATEGORIES.filter((c) => c !== 'unscored').map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}</select></label></div>
            {rows.isPending && <LoadingState />}
            {rows.isError && <ErrorState message={rows.error.message} />}
            {rows.data && rows.data.results.length === 0 && <EmptyState title="Nothing in this category" />}
            {rows.data && rows.data.results.length > 0 && (
              <table className="mt-1 w-full text-left text-sm">
                <thead className="border-b border-slate-300 text-slate-600"><tr><th className="py-1">Transaction</th><th className="text-right">Score</th><th>Category</th><th className="text-right">Coverage</th>{COMPONENT_ORDER.map((k) => <th key={k} className="text-right" title={COMPONENT_LABEL[k].name}>{k}</th>)}</tr></thead>
                <tbody>
                  {rows.data.results.map((r) => (
                    <tr key={r.id} className={`border-b border-slate-100 ${selected === r.id ? 'bg-slate-100' : ''}`}>
                      <td className="py-1"><button className="text-blue-700 hover:underline" onClick={() => setSelected(r.id)}>{r.external_id}</button></td>
                      <td className="text-right tabular-nums">{r.overall_score?.toFixed(1)}</td><td><RiskBadge category={r.category} />{r.capped && <span title="held at High: low coverage"> *</span>}</td>
                      <td className="text-right tabular-nums">{(r.weight_coverage * 100).toFixed(0)}%</td>
                      {COMPONENT_ORDER.map((k) => <td key={k} className="text-right tabular-nums">{r.component_values[k] != null ? r.component_values[k]!.toFixed(0) : '–'}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
      {selected !== null && (
        <div role="region" aria-label="Assessment breakdown" className="rounded-md border border-slate-300 p-4">
          {detail.isPending && <LoadingState />}
          {detail.isError && <ErrorState message={detail.error.message} />}
          {detail.data && <><p className="mb-2 text-sm"><Link className="text-blue-700 hover:underline" to={`/transactions/${detail.data.transaction}`}>Transaction {detail.data.external_id}</Link> · sender <Link className="font-mono text-blue-700 hover:underline" to={`/accounts/${detail.data.account}`}>{detail.data.account_ref}</Link></p><BreakdownTable a={detail.data} /></>}
        </div>
      )}
    </section>
  )
}
