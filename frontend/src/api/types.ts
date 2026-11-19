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
