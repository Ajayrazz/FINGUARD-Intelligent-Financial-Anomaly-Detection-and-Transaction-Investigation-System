import { useQuery } from '@tanstack/react-query'
import { api, type ReadinessResponse } from '../api/client'
import { ErrorState, LoadingState } from '../components/ui/states'

/** Infrastructure status. The analytics Overview Dashboard is delivered in Phase 14. */
export default function StatusPage() {
  const q = useQuery({ queryKey: ['health-ready'], queryFn: ({ signal }) => api.get<ReadinessResponse>('/health/ready/', signal) })
  return (
    <section>
      <h1 className="text-2xl font-semibold">System status</h1>
      <div className="mt-4 max-w-md rounded-lg border border-slate-200 p-4" aria-live="polite">
        {q.isPending && <LoadingState label="Checking backend…" />}
        {q.isError && <ErrorState message={`Backend unreachable: ${q.error.message}`} onRetry={() => void q.refetch()} />}
        {q.data && (
          <ul>
            {Object.entries(q.data.checks).map(([name, status]) => (
              <li key={name} className="flex justify-between py-1">
                <span>{name}</span>
                <span className={status === 'ok' ? 'text-risk-low' : 'text-risk-critical'}>{status}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
