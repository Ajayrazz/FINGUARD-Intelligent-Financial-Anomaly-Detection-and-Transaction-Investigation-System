import type { CasePriority, CaseStatus } from '../../api/types'

const prio: Record<CasePriority, string> = { low: 'bg-slate-200 text-slate-800', medium: 'bg-amber-100 text-amber-800', high: 'bg-orange-100 text-orange-900', critical: 'bg-red-100 text-red-800' }
const stat: Record<CaseStatus, string> = {
  new: 'bg-blue-100 text-blue-800', under_review: 'bg-slate-200 text-slate-800', investigation: 'bg-indigo-100 text-indigo-900',
  escalated: 'bg-purple-100 text-purple-900', resolved: 'bg-teal-100 text-teal-900', closed: 'bg-green-100 text-green-800',
}
export const STATUS_LABEL: Record<CaseStatus, string> = { new: 'New', under_review: 'Under review', investigation: 'Investigation in progress', escalated: 'Escalated', resolved: 'Resolved', closed: 'Closed' }
export const OUTCOME_LABEL = { confirmed_suspicious: 'Confirmed suspicious', false_positive: 'False positive', inconclusive: 'Inconclusive', referred: 'Referred' } as const

export function PriorityBadge({ priority }: { priority: CasePriority }) {
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium capitalize ${prio[priority]}`}>{priority}</span>
}
export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${stat[status]}`}>{STATUS_LABEL[status]}</span>
}
