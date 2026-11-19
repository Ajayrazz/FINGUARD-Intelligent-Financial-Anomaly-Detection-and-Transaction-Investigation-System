import type { MatchClass, ReviewStatus } from '../../api/types'

export const CLASS_LABEL: Record<MatchClass, string> = {
  exact: 'Exact',
  strong_similar: 'Strong match',
  potential: 'Potential',
  legitimate_repeat: 'Likely legitimate repeat',
}
export const STATUS_LABEL: Record<ReviewStatus, string> = {
  pending: 'Pending review',
  confirmed_duplicate: 'Confirmed duplicate',
  not_duplicate: 'Not a duplicate',
  legitimate_repeat: 'Legitimate repeat',
}
