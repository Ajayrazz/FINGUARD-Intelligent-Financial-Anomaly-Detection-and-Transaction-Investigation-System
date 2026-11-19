import type { RiskCategory, RiskComponentKey } from '../../api/types'

export const COMPONENT_LABEL: Record<RiskComponentKey, { name: string; meaning: string }> = {
  A: { name: 'Model anomaly', meaning: 'Model score for this transaction (50 = the model’s own alert threshold)' },
  B: { name: 'Behaviour', meaning: 'Deviation from the sender’s own history (amount, spend jump, new counterparty, hour)' },
  G: { name: 'Graph', meaning: 'Strongest network pattern (cycle, chain, fan-in/out, …) involving either account, once it had completed' },
  F: { name: 'Frequency', meaning: 'Burst of the sender’s transactions in a short window' },
  D: { name: 'Duplicate', meaning: 'Similarity to an earlier transaction not dismissed by a reviewer' },
  H: { name: 'History', meaning: 'Human-confirmed duplicates in the accounts’ earlier transactions' },
}
export const COMPONENT_ORDER: RiskComponentKey[] = ['A', 'B', 'G', 'F', 'D', 'H']

export const CATEGORY_LABEL: Record<RiskCategory, string> = { low: 'Low', medium: 'Medium', high: 'High', critical: 'Critical', unscored: 'Not scored' }
export const CATEGORY_TONE: Record<RiskCategory, string> = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-amber-100 text-amber-800',
  high: 'bg-orange-100 text-orange-900',
  critical: 'bg-red-100 text-red-800',
  unscored: 'bg-slate-200 text-slate-800',
}
