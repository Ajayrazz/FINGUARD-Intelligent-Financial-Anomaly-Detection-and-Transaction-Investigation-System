import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Dataset, ImportJob, ImportPreview } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Button } from '../components/ui/Button'
import { ErrorState, LoadingState } from '../components/ui/states'
import { FIELDS, mappingProblems, toApiMapping, type ColumnMap } from '../lib/importMapping'

const NEW = '__new__'

export default function ImportWizardPage() {
  const { can } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const datasets = useQuery({ queryKey: ['datasets'], queryFn: ({ signal }) => api.get<Dataset[]>('/datasets/', signal) })

  const [datasetId, setDatasetId] = useState<string>('')
  const [newName, setNewName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [map, setMap] = useState<ColumnMap>({})
  const [options, setOptions] = useState<Record<string, string>>({ merchant_prefix: '', customer_prefix: '', step_epoch: '' })
  const [dup, setDup] = useState<'reject' | 'skip' | 'flag'>('reject')
  const [error, setError] = useState<string | null>(null)

  const effectiveDataset = datasetId || (datasets.data?.[0] ? String(datasets.data[0].id) : NEW)
  const creating = effectiveDataset === NEW

  const ensureDataset = async (): Promise<number> => {
    if (!creating) return Number(effectiveDataset)
    const d = await api.post<Dataset>('/datasets/', { name: newName.trim(), source_type: 'custom', is_synthetic: true })
    await qc.invalidateQueries({ queryKey: ['datasets'] })
    return d.id
  }
  const messageOf = (e: unknown) =>
    e instanceof ApiError ? Object.values(e.details).flat().join(' ') || e.message : 'Unexpected error'

  const previewMut = useMutation({
    mutationFn: async (f: File) => {
      const ds = await ensureDataset()
      const form = new FormData()
      form.append('file', f)
      return { ds, preview: await api.post<ImportPreview>(`/datasets/${ds}/imports/preview/`, form) }
    },
    onSuccess: ({ ds, preview: p }) => {
      setDatasetId(String(ds))
      setPreview(p)
      setMap(Object.fromEntries(p.columns.map((c) => [c, p.suggested_mapping.columns[c] ?? ''])))
      setOptions((o) => ({ ...o, ...Object.fromEntries(Object.entries(p.suggested_mapping.options).map(([k, v]) => [k, String(v)])) }))
      setError(null)
    },
    onError: (e) => setError(messageOf(e)),
  })

  const start = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('No file')
      const form = new FormData()
      form.append('file', file)
      form.append('mapping', toApiMapping(map, options))
      form.append('dup_policy', dup)
      return api.post<ImportJob>(`/datasets/${effectiveDataset}/imports/`, form)
    },
    onSuccess: (job) => {
      void qc.invalidateQueries({ queryKey: ['imports'] })
      navigate(`/imports/${job.id}`)
    },
    onError: (e) => setError(messageOf(e)),
  })

  if (!can('imports.create')) return <p role="alert" className="p-4">Your role cannot start imports.</p>
  if (datasets.isPending) return <LoadingState />
  if (datasets.isError) return <ErrorState message={datasets.error.message} onRetry={() => void datasets.refetch()} />

  const problems = preview ? mappingProblems(map) : []
  const usesStep = Object.values(map).includes('step') && !Object.values(map).includes('occurred_at')
  const field = 'mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm'

  return (
    <section className="max-w-4xl space-y-6">
      <div>
        <Link to="/imports" className="text-sm text-blue-700 hover:underline">← Imports</Link>
        <h1 className="mt-1 text-2xl font-semibold">New import</h1>
      </div>

      <fieldset className="space-y-3 rounded-lg border border-slate-200 p-4" disabled={start.isPending}>
        <legend className="px-1 font-medium">1. Dataset and file</legend>
        <label className="block text-sm">Dataset
          <select className={field} value={effectiveDataset} onChange={(e) => { setDatasetId(e.target.value); setPreview(null) }}>
            {datasets.data.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            {can('datasets.create') && <option value={NEW}>+ Create a new dataset…</option>}
          </select>
        </label>
        {creating && (
          <label className="block text-sm">New dataset name
            <input className={field} value={newName} onChange={(e) => setNewName(e.target.value)} maxLength={120} />
          </label>
        )}
        <label className="block text-sm">File (.csv or .xlsx)
          <input
            type="file" accept=".csv,.xlsx" className={field}
            onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPreview(null); setError(null) }}
          />
        </label>
        <Button disabled={!file || previewMut.isPending || (creating && newName.trim() === '')} onClick={() => file && previewMut.mutate(file)}>
          {previewMut.isPending ? 'Reading file…' : 'Preview file'}
        </Button>
      </fieldset>

      {error && <ErrorState message={error} />}

      {preview && (
        <>
          <fieldset className="space-y-3 rounded-lg border border-slate-200 p-4" disabled={start.isPending}>
            <legend className="px-1 font-medium">2. Map columns</legend>
            <p className="text-sm text-slate-600">
              {preview.file_name} · ~{(preview.estimated_rows ?? 0).toLocaleString()} rows
              {preview.suggested_mapping.preset && <> · detected <strong>{preview.suggested_mapping.preset}</strong> format (mapping suggested)</>}
              . Unmapped columns are kept in each transaction’s metadata.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-300 text-slate-600">
                  <tr><th className="py-2">File column</th><th>Sample</th><th>Maps to</th></tr>
                </thead>
                <tbody>
                  {preview.columns.map((c, i) => (
                    <tr key={c} className="border-b border-slate-100">
                      <td className="py-1.5 font-mono">{c}</td>
                      <td className="max-w-xs truncate text-slate-600">{preview.rows.slice(0, 3).map((r) => r[i]).join(' · ')}</td>
                      <td>
                        <select aria-label={`Target for ${c}`} className="rounded-md border border-slate-300 px-1 py-0.5" value={map[c] ?? ''} onChange={(e) => setMap({ ...map, [c]: e.target.value })}>
                          <option value="">— keep as metadata —</option>
                          {FIELDS.map((f) => <option key={f.key} value={f.key}>{f.label}{f.required ? ' *' : ''}</option>)}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="block text-sm">Merchant account prefix
                <input className={field} value={options.merchant_prefix} onChange={(e) => setOptions({ ...options, merchant_prefix: e.target.value })} placeholder="e.g. M" />
              </label>
              <label className="block text-sm">Customer account prefix
                <input className={field} value={options.customer_prefix} onChange={(e) => setOptions({ ...options, customer_prefix: e.target.value })} placeholder="e.g. C" />
              </label>
              {usesStep && (
                <label className="block text-sm">Time-step epoch (step 0, UTC)
                  <input className={field} value={options.step_epoch} onChange={(e) => setOptions({ ...options, step_epoch: e.target.value })} placeholder="2026-01-01T00:00:00Z" />
                </label>
              )}
            </div>
            {problems.length > 0 && (
              <ul role="alert" className="list-disc pl-5 text-sm text-red-700">
                {problems.map((p) => <li key={p}>{p}</li>)}
              </ul>
            )}
          </fieldset>

          <fieldset className="space-y-2 rounded-lg border border-slate-200 p-4" disabled={start.isPending}>
            <legend className="px-1 font-medium">3. Duplicate transaction IDs</legend>
            {([
              ['reject', 'Reject duplicates (recommended) — keep the first, report the rest as errors'],
              ['skip', 'Skip duplicates silently — useful for safe re-imports'],
              ['flag', 'Import duplicates under a derived ID and flag them'],
            ] as const).map(([v, label]) => (
              <label key={v} className="flex items-start gap-2 text-sm">
                <input type="radio" name="dup" checked={dup === v} onChange={() => setDup(v)} className="mt-1" /> {label}
              </label>
            ))}
          </fieldset>

          <Button disabled={problems.length > 0 || start.isPending} onClick={() => start.mutate()}>
            {start.isPending ? 'Uploading…' : 'Start import'}
          </Button>
        </>
      )}
    </section>
  )
}
