import type { AlertSeverity, AlertStatus } from '../../api/types'

const tone: Record<AlertSeverity, string> = {
  low: 'bg-slate-200 text-slate-800', medium: 'bg-amber-100 text-amber-800', high: 'bg-orange-100 text-orange-900', critical: 'bg-red-100 text-red-800',
}
const statusTone: Record<AlertStatus, string> = {
  new: 'bg-blue-100 text-blue-800', acknowledged: 'bg-slate-200 text-slate-800', escalated: 'bg-purple-100 text-purple-900', closed: 'bg-green-100 text-green-800',
}

/** Severity and status are always written out; colour only reinforces. */
export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium capitalize ${tone[severity]}`}>{severity}</span>
}
export function AlertStatusBadge({ status }: { status: AlertStatus }) {
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium capitalize ${statusTone[status]}`}>{status}</span>
}
