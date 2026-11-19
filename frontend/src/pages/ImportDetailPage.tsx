import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api/client'
import type { ImportJob, ImportRowError, Paginated } from '../api/types'
import { PermissionGate } from '../auth/guards'
import { ImportStatusBadge, isActive } from '../components/imports/ImportStatusBadge'
import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/states'
import { useToast } from '../components/ui/Toast'
import { useEvents } from '../hooks/useEvents'
import { useNow } from '../hooks/useNow'
import { formatDateTime } from '../lib/format'

const STALL_MS = 60_000

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-lg tabular-nums">{value.toLocaleString()}</dd>
    </div>
  )
}

export default function ImportDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const toast = useToast()
  const [errPage, setErrPage] = useState(1)
  const now = useNow()

  const job = useQuery({
    queryKey: ['import', id],
    queryFn: ({ signal }) => api.get<ImportJob>(`/imports/${id}/`, signal),
    refetchInterval: (query) => (query.state.data && isActive(query.state.data.status) ? 3000 : false),
  })
  useEvents((e) => {
    if (e.type === 'import.progress' && String(e.data.id) === id) {
      qc.setQueryData<ImportJob>(['import', id], (old) => (old ? { ...old, ...(e.data as Partial<ImportJob>) } : old))
      if (['completed', 'completed_with_errors', 'failed', 'cancelled'].includes(String(e.data.status))) {
        void qc.invalidateQueries({ queryKey: ['import', id] })
        void qc.invalidateQueries({ queryKey: ['import', id, 'errors'] })
      }
    }
  })
  const errors = useQuery({
    queryKey: ['import', id, 'errors', errPage],
    queryFn: ({ signal }) => api.get<Paginated<ImportRowError>>(`/imports/${id}/errors/?page=${errPage}`, signal),
    enabled: (job.data?.rows_rejected ?? 0) > 0,
  })

  const act = useMutation({
    mutationFn: ({ action, force }: { action: 'cancel' | 'resume'; force?: boolean }) =>
      api.post<ImportJob>(`/imports/${id}/${action}/`, force ? { force: true } : undefined),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['import', id] }),
    onError: (e) => toast('error', e instanceof ApiError ? JSON.stringify(e.details) || e.message : 'Action failed'),
  })

  if (job.isPending) return <LoadingState />
  if (job.isError) return <ErrorState message={job.error.message} onRetry={() => void job.refetch()} />
  const j = job.data
  const pct = j.rows_total > 0 ? Math.min(100, Math.round((j.rows_processed / j.rows_total) * 100)) : 0
  const stalled = isActive(j.status) && now - new Date(j.updated_at).getTime() > STALL_MS

  return (
    <section className="space-y-6">
      <div>
        <Link to="/imports" className="text-sm text-blue-700 hover:underline">← Imports</Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">Import #{j.id}</h1>
          <ImportStatusBadge status={j.status} />
          <PermissionGate permission="imports.create">
            {isActive(j.status) && !stalled && (
              <Button variant="secondary" disabled={act.isPending} onClick={() => act.mutate({ action: 'cancel' })}>Cancel</Button>
            )}
            {(j.status === 'failed' || j.status === 'cancelled') && (
              <Button disabled={act.isPending} onClick={() => act.mutate({ action: 'resume' })}>Resume from row {j.rows_processed.toLocaleString()}</Button>
            )}
            {stalled && (
              <Button variant="danger" disabled={act.isPending} onClick={() => act.mutate({ action: 'resume', force: true })}>
                No progress for over a minute — resume
              </Button>
            )}
          </PermissionGate>
        </div>
        <p className="text-sm text-slate-600">
          {j.file_name} → {j.dataset_name} · {j.created_by_email ?? 'system'} · duplicates policy: {j.dup_policy}
        </p>
      </div>

      <div>
        <div
          role="progressbar" aria-label="Import progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}
          className="h-3 w-full overflow-hidden rounded bg-slate-200"
        >
          <div className="h-full bg-slate-800 transition-all" style={{ width: `${pct}%` }} />
        </div>
        <p className="mt-1 text-sm text-slate-600">
          {j.rows_processed.toLocaleString()} of ~{j.rows_total.toLocaleString()} rows ({pct}%)
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-4 rounded-lg border border-slate-200 p-4 sm:grid-cols-4">
        <Stat label="Accepted" value={j.rows_accepted} />
        <Stat label="Rejected" value={j.rows_rejected} />
        <Stat label="Duplicate IDs" value={j.rows_duplicate} />
        <Stat label="Processed" value={j.rows_processed} />
      </dl>
      <p className="text-xs text-slate-500">
        Started {j.started_at ? formatDateTime(j.started_at) : '—'} · Finished {j.finished_at ? formatDateTime(j.finished_at) : '—'} · SHA-256 {j.file_sha256 || '—'}
      </p>
      {j.error_summary && <ErrorState message={j.error_summary} />}

      {j.rows_rejected > 0 && (
        <div>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Rejected rows</h2>
            <Button variant="secondary" onClick={() => void downloadFile(`/imports/${id}/errors/export/`, `import-${id}-errors.csv`).catch(() => toast('error', 'Download failed'))}>
              Download CSV
            </Button>
          </div>
          <p className="text-sm text-slate-600">Row numbers count data rows, excluding the header.</p>
          <div className="mt-2">
            {errors.isPending && <LoadingState />}
            {errors.isError && <ErrorState message={errors.error.message} onRetry={() => void errors.refetch()} />}
            {errors.data && errors.data.results.length === 0 && <EmptyState title="No stored row errors" />}
            {errors.data && errors.data.results.length > 0 && (
              <>
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-300 text-slate-600">
                    <tr><th className="py-2">Row</th><th>Problem</th><th>Detail</th></tr>
                  </thead>
                  <tbody>
                    {errors.data.results.map((e) => (
                      <tr key={e.id} className="border-b border-slate-100 align-top">
                        <td className="py-2 tabular-nums">{e.row_number}</td>
                        <td className="font-mono">{e.error_code}</td>
                        <td>{e.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-3 flex items-center gap-3 text-sm">
                  <Button variant="secondary" disabled={!errors.data.previous} onClick={() => setErrPage((p) => p - 1)}>Previous</Button>
                  <span>Page {errPage} · {errors.data.count.toLocaleString()} stored errors</span>
                  <Button variant="secondary" disabled={!errors.data.next} onClick={() => setErrPage((p) => p + 1)}>Next</Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
