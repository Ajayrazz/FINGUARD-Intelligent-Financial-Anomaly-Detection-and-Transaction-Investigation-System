import type { RiskCategory } from '../../api/types'
import { CATEGORY_LABEL, CATEGORY_TONE } from './riskLabels'

/** The category is always written out; colour is only reinforcement. */
export function RiskBadge({ category }: { category: RiskCategory }) {
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${CATEGORY_TONE[category]}`}>{CATEGORY_LABEL[category]}</span>
}
