export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface User {
  id: number
  email: string
  full_name: string
  role: string
  role_label: string
  is_active: boolean
  last_login: string | null
  created_at: string
}

export interface Me extends User {
  permissions: string[]
}

export interface Role {
  id: number
  name: string
  label: string
  description: string
  is_system: boolean
  permissions: string[]
}

export interface PermissionInfo {
  codename: string
  description: string
}

export interface AuditLogEntry {
  id: number
  created_at: string
  actor: number | null
  actor_email: string
  action: string
  resource_type: string
  resource_id: string
  ip_address: string | null
  request_id: string
  changes: Record<string, unknown>
}

export interface Dataset {
  id: number
  name: string
  source_type: string
  is_synthetic: boolean
  description: string
  row_count: number
  created_at: string
}

export type TxStatus = 'pending' | 'completed' | 'failed' | 'reversed'

export interface TransactionRow {
  id: number
  dataset: number
  transaction_id: string
  sender: number
  sender_ref: string
  receiver: number | null
  receiver_ref: string | null
  amount: string
  currency: string
  tx_type: string
  occurred_at: string
  status: TxStatus
}

export interface AccountBrief {
  id: number
  account_ref: string
  account_type: string
}

export interface TransactionDetail {
  id: number
  dataset: number
  dataset_name: string
  transaction_id: string
  sender: AccountBrief
  receiver: AccountBrief | null
  amount: string
  currency: string
  tx_type: string
  occurred_at: string
  step: number | null
  sender_balance_before: string | null
  sender_balance_after: string | null
  receiver_balance_before: string | null
  receiver_balance_after: string | null
  merchant_name: string
  merchant_category: string
  status: TxStatus
  metadata: Record<string, unknown>
  created_at: string
}

export interface TransactionEvent {
  id: number
  event_type: string
  actor_email: string | null
  payload: Record<string, unknown>
  created_at: string
}

export interface AccountDetail {
  id: number
  dataset: number
  dataset_name: string
  account_ref: string
  account_type: string
  first_seen_at: string | null
  last_seen_at: string | null
  sent_count: number
  sent_total: string
  received_count: number
  received_total: string
}

export type ImportStatus =
  | 'pending' | 'validating' | 'running' | 'completed' | 'completed_with_errors' | 'failed' | 'cancelled'

export interface ImportJob {
  id: number
  dataset: number
  dataset_name: string
  source: 'file' | 'api'
  file_name: string
  file_size: number
  file_sha256: string
  status: ImportStatus
  dup_policy: 'reject' | 'skip' | 'flag'
  rows_total: number
  rows_processed: number
  rows_accepted: number
  rows_rejected: number
  rows_duplicate: number
  error_summary: string
  created_by_email: string | null
  created_at: string
  updated_at: string
  started_at: string | null
  finished_at: string | null
}

export interface ImportRowError {
  id: number
  row_number: number
  error_code: string
  message: string
  raw: Record<string, unknown>
}

export interface ImportPreview {
  file_name: string
  format: 'csv' | 'xlsx'
  columns: string[]
  rows: string[][]
  estimated_rows: number | null
  suggested_mapping: { columns: Record<string, string>; options: Record<string, unknown>; preset: string | null }
  presets: string[]
}

export interface TestMetrics {
  pr_auc: number
  pr_auc_ci95?: [number, number]
  roc_auc: number
  base_rate: number
  positives: number
  rows: number
  recall_at_fpr_1pct: number
}

export interface ModelVersionRow {
  id: number
  model_name: string
  algorithm: string
  task_type: 'supervised' | 'unsupervised' | 'graph'
  version: string
  status: 'candidate' | 'active' | 'retired'
  dataset: string
  feature_set: string | null
  random_seed: number | null
  trained_at: string | null
  test_metrics: TestMetrics | null
  scorable: boolean
}

export type RunStatus = 'pending' | 'running' | 'succeeded' | 'failed'

export interface ScoreSummary {
  min: number
  max: number
  mean: number
  quantiles: Record<string, number>
  histogram: { counts: number[]; edges: number[] }
  threshold: number
}

export interface DetectionRun {
  id: number
  model_version: number
  model_name: string
  algorithm: string
  version: string
  dataset: number
  dataset_name: string
  is_mock_data: boolean
  threshold: number
  threshold_source: string
  status: RunStatus
  rows_scored: number
  rows_flagged: number
  score_summary: ScoreSummary | Record<string, never>
  error_message: string
  created_by_email: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface PredictionRow {
  id: number
  transaction_id: number
  external_id: string
  amount: string
  tx_type: string
  occurred_at: string
  sender: string
  receiver: string | null
  score: number
  flagged: boolean
}

export interface BehaviorPeriod {
  period: string
  count: number
  total: number
}

export interface BehaviorProfile {
  account: number
  account_ref: string
  as_of: string
  window_days: number
  direction: 'out' | 'in'
  profile_version: string
  tx_count: number
  sufficient_history: boolean
  avg_amount: number | null
  median_amount: number | null
  std_amount: number | null
  p95_amount: number | null
  mad_amount: number | null
  tx_per_day: number
  unique_counterparties: number
  hour_histogram: number[]
  merchant_category_dist: Record<string, number> | null
  aggregates: { daily: BehaviorPeriod[]; weekly: BehaviorPeriod[]; monthly: BehaviorPeriod[] }
  recent_7d: { count: number; total: number; avg: number | null }
}

export interface BehaviorComponent {
  available: boolean
  score: number | null
  reason?: string
  value?: number
  detail?: Record<string, unknown>
}

export interface TransactionBehavior {
  transaction: number
  account: number
  profile_version: string
  status: 'scored' | 'unavailable_cold_start'
  deviation_score: number | null
  coverage: number
  history_count: number
  components: Record<string, BehaviorComponent>
}

export type FindingType = 'cycle' | 'chain' | 'fan_in' | 'fan_out' | 'shared_beneficiary' | 'dense_cluster'

export interface GraphSnapshot {
  id: number
  dataset: number
  dataset_name: string
  is_mock_data: boolean
  as_of: string
  window_days: number | null
  status: RunStatus
  node_count: number
  edge_count: number
  finding_count: number
  truncated: Record<string, boolean>
  error_message: string
  created_by_email: string | null
  created_at: string
  built_at: string | null
}

export interface GraphFinding {
  id: number
  snapshot: number
  finding_type: FindingType
  score: number
  account_ids: number[]
  accounts: { id: number; account_ref: string }[]
  transaction_ids: number[]
  evidence: Record<string, unknown>
  detected_at: string
}

export interface GraphNode {
  id: number
  account_ref: string
  account_type: string
  depth: number
  graph_risk_score: number | null
  in_finding: boolean
}

export interface GraphEdge {
  source: number
  target: number
  count: number
  total: number
  first_at: string
  last_at: string
  transaction_ids: number[]
}

export interface Neighborhood {
  center: number
  source: 'neo4j' | 'postgres'
  depth: number
  truncated: boolean
  snapshot: number | null
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface SyncStatus {
  dataset: number
  status: 'never' | 'running' | 'synced' | 'failed'
  last_tx_id: number
  edges_synced: number
  last_error: string
  updated_at: string | null
  drift: {
    postgres: { nodes: number; edges: number }
    neo4j: { nodes: number; edges: number } | null
    in_sync: boolean | null
    error: string | null
  }
}

export interface GraphEdgeDetail {
  transaction_id: number
  external_id: string
  sender: { id: number; account_ref: string }
  receiver: { id: number; account_ref: string } | null
  amount: string
  currency: string
  tx_type: string
  occurred_at: string
  status: string
}

export interface GraphTimelineEvent {
  transaction_id: number
  external_id: string
  occurred_at: string
  sender: string
  receiver: string | null
  amount: string
  tx_type: string
}

export type InvoiceStatus = 'uploaded' | 'ocr_done' | 'needs_review' | 'reviewed' | 'failed'

export interface InvoiceRow {
  id: number
  document_id: number | null
  original_name: string
  status: InvoiceStatus
  ocr_confidence: number | null
  error_message: string
  vendor_name: string
  invoice_number: string
  amount: string | null
  currency: string
  invoice_date: string | null
  extracted_fields: Record<string, string | null>
  field_confidence: Record<string, number>
  verified_by_email: string | null
  verified_at: string | null
  created_at: string | null
}

export type MatchClass = 'exact' | 'strong_similar' | 'potential' | 'legitimate_repeat'
export type ReviewStatus = 'pending' | 'confirmed_duplicate' | 'not_duplicate' | 'legitimate_repeat'

export interface DuplicateCandidate {
  id: number
  kind: 'transaction' | 'invoice'
  record_a_type: string
  record_a_id: number
  record_b_type: string
  record_b_id: number
  match_class: MatchClass
  similarity_score: number
  review_status: ReviewStatus
  reviewed_by_email: string | null
  reviewed_at: string | null
  notes: string
  created_at: string
}

export interface DuplicateRecord {
  type: 'transaction' | 'invoice'
  id: number
  [key: string]: string | number | boolean | null
}

export interface DuplicateCandidateDetail extends DuplicateCandidate {
  evidence: Record<string, unknown>
  record_a: DuplicateRecord | null
  record_b: DuplicateRecord | null
}
