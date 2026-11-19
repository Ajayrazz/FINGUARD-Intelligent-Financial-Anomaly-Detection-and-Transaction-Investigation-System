export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  role_label: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

export interface Me extends User {
  permissions: string[];
}

export interface Role {
  id: number;
  name: string;
  label: string;
  description: string;
  is_system: boolean;
  permissions: string[];
}

export interface PermissionInfo {
  codename: string;
  description: string;
}

export interface AuditLogEntry {
  id: number;
  created_at: string;
  actor: number | null;
  actor_email: string;
  action: string;
  resource_type: string;
  resource_id: string;
  ip_address: string | null;
  request_id: string;
  changes: Record<string, unknown>;
}

export interface Dataset {
  id: number;
  name: string;
  source_type: string;
  is_synthetic: boolean;
  description: string;
  row_count: number;
  created_at: string;
}

export type TxStatus = "pending" | "completed" | "failed" | "reversed";

export interface TransactionRow {
  id: number;
  dataset: number;
  transaction_id: string;
  sender: number;
  sender_ref: string;
  receiver: number | null;
  receiver_ref: string | null;
  amount: string;
  currency: string;
  tx_type: string;
  occurred_at: string;
  status: TxStatus;
}

export interface AccountBrief {
  id: number;
  account_ref: string;
  account_type: string;
}

export interface TransactionDetail {
  id: number;
  dataset: number;
  dataset_name: string;
  transaction_id: string;
  sender: AccountBrief;
  receiver: AccountBrief | null;
  amount: string;
  currency: string;
  tx_type: string;
  occurred_at: string;
  step: number | null;
  sender_balance_before: string | null;
  sender_balance_after: string | null;
  receiver_balance_before: string | null;
  receiver_balance_after: string | null;
  merchant_name: string;
  merchant_category: string;
  status: TxStatus;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface TransactionEvent {
  id: number;
  event_type: string;
  actor_email: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AccountDetail {
  id: number;
  dataset: number;
  dataset_name: string;
  account_ref: string;
  account_type: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
  sent_count: number;
  sent_total: string;
  received_count: number;
  received_total: string;
}

export type ImportStatus =
  | "pending"
  | "validating"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed"
  | "cancelled";

export interface ImportJob {
  id: number;
  dataset: number;
  dataset_name: string;
  source: "file" | "api";
  file_name: string;
  file_size: number;
  file_sha256: string;
  status: ImportStatus;
  dup_policy: "reject" | "skip" | "flag";
  rows_total: number;
  rows_processed: number;
  rows_accepted: number;
  rows_rejected: number;
  rows_duplicate: number;
  error_summary: string;
  created_by_email: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ImportRowError {
  id: number;
  row_number: number;
  error_code: string;
  message: string;
  raw: Record<string, unknown>;
}

export interface ImportPreview {
  file_name: string;
  format: "csv" | "xlsx";
  columns: string[];
  rows: string[][];
  estimated_rows: number | null;
  suggested_mapping: {
    columns: Record<string, string>;
    options: Record<string, unknown>;
    preset: string | null;
  };
  presets: string[];
}

export interface TestMetrics {
  pr_auc: number;
  pr_auc_ci95?: [number, number];
  roc_auc: number;
  base_rate: number;
  positives: number;
  rows: number;
  recall_at_fpr_1pct: number;
}

export interface ModelVersionRow {
  id: number;
  model_name: string;
  algorithm: string;
  task_type: "supervised" | "unsupervised" | "graph";
  version: string;
  status: "candidate" | "active" | "retired";
  dataset: string;
  feature_set: string | null;
  random_seed: number | null;
  trained_at: string | null;
  test_metrics: TestMetrics | null;
  scorable: boolean;
}

export type RunStatus = "pending" | "running" | "succeeded" | "failed";

export interface ScoreSummary {
  min: number;
  max: number;
  mean: number;
  quantiles: Record<string, number>;
  histogram: { counts: number[]; edges: number[] };
  threshold: number;
}

export interface DetectionRun {
  id: number;
  model_version: number;
  model_name: string;
  algorithm: string;
  version: string;
  dataset: number;
  dataset_name: string;
  is_mock_data: boolean;
  threshold: number;
  threshold_source: string;
  status: RunStatus;
  rows_scored: number;
  rows_flagged: number;
  score_summary: ScoreSummary | Record<string, never>;
  error_message: string;
  created_by_email: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface PredictionRow {
  id: number;
  transaction_id: number;
  external_id: string;
  amount: string;
  tx_type: string;
  occurred_at: string;
  sender: string;
  receiver: string | null;
  score: number;
  flagged: boolean;
}

export interface BehaviorPeriod {
  period: string;
  count: number;
  total: number;
}

export interface BehaviorProfile {
  account: number;
  account_ref: string;
  as_of: string;
  window_days: number;
  direction: "out" | "in";
  profile_version: string;
  tx_count: number;
  sufficient_history: boolean;
  avg_amount: number | null;
  median_amount: number | null;
  std_amount: number | null;
  p95_amount: number | null;
  mad_amount: number | null;
  tx_per_day: number;
  unique_counterparties: number;
  hour_histogram: number[];
  merchant_category_dist: Record<string, number> | null;
  aggregates: {
    daily: BehaviorPeriod[];
    weekly: BehaviorPeriod[];
    monthly: BehaviorPeriod[];
  };
  recent_7d: { count: number; total: number; avg: number | null };
}

export interface BehaviorComponent {
  available: boolean;
  score: number | null;
  reason?: string;
  value?: number;
  detail?: Record<string, unknown>;
}

export interface TransactionBehavior {
  transaction: number;
  account: number;
  profile_version: string;
  status: "scored" | "unavailable_cold_start";
  deviation_score: number | null;
  coverage: number;
  history_count: number;
  components: Record<string, BehaviorComponent>;
}

export type FindingType =
  | "cycle"
  | "chain"
  | "fan_in"
  | "fan_out"
  | "shared_beneficiary"
  | "dense_cluster";

export interface GraphSnapshot {
  id: number;
  dataset: number;
  dataset_name: string;
  is_mock_data: boolean;
  as_of: string;
  window_days: number | null;
  status: RunStatus;
  node_count: number;
  edge_count: number;
  finding_count: number;
  truncated: Record<string, boolean>;
  error_message: string;
  created_by_email: string | null;
  created_at: string;
  built_at: string | null;
}

export interface GraphFinding {
  id: number;
  snapshot: number;
  finding_type: FindingType;
  score: number;
  account_ids: number[];
  accounts: { id: number; account_ref: string }[];
  transaction_ids: number[];
  evidence: Record<string, unknown>;
  detected_at: string;
}

export interface GraphNode {
  id: number;
  account_ref: string;
  account_type: string;
  depth: number;
  graph_risk_score: number | null;
  in_finding: boolean;
}

export interface GraphEdge {
  source: number;
  target: number;
  count: number;
  total: number;
  first_at: string;
  last_at: string;
  transaction_ids: number[];
}

export interface Neighborhood {
  center: number;
  source: "neo4j" | "postgres";
  depth: number;
  truncated: boolean;
  snapshot: number | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface SyncStatus {
  dataset: number;
  status: "never" | "running" | "synced" | "failed";
  last_tx_id: number;
  edges_synced: number;
  last_error: string;
  updated_at: string | null;
  drift: {
    postgres: { nodes: number; edges: number };
    neo4j: { nodes: number; edges: number } | null;
    in_sync: boolean | null;
    error: string | null;
  };
}

export interface GraphEdgeDetail {
  transaction_id: number;
  external_id: string;
  sender: { id: number; account_ref: string };
  receiver: { id: number; account_ref: string } | null;
  amount: string;
  currency: string;
  tx_type: string;
  occurred_at: string;
  status: string;
}

export interface GraphTimelineEvent {
  transaction_id: number;
  external_id: string;
  occurred_at: string;
  sender: string;
  receiver: string | null;
  amount: string;
  tx_type: string;
}

export type InvoiceStatus =
  "uploaded" | "ocr_done" | "needs_review" | "reviewed" | "failed";

export interface InvoiceRow {
  id: number;
  document_id: number | null;
  original_name: string;
  status: InvoiceStatus;
  ocr_confidence: number | null;
  error_message: string;
  vendor_name: string;
  invoice_number: string;
  amount: string | null;
  currency: string;
  invoice_date: string | null;
  extracted_fields: Record<string, string | null>;
  field_confidence: Record<string, number>;
  verified_by_email: string | null;
  verified_at: string | null;
  created_at: string | null;
}

export type MatchClass =
  "exact" | "strong_similar" | "potential" | "legitimate_repeat";
export type ReviewStatus =
  "pending" | "confirmed_duplicate" | "not_duplicate" | "legitimate_repeat";

export interface DuplicateCandidate {
  id: number;
  kind: "transaction" | "invoice";
  record_a_type: string;
  record_a_id: number;
  record_b_type: string;
  record_b_id: number;
  match_class: MatchClass;
  similarity_score: number;
  review_status: ReviewStatus;
  reviewed_by_email: string | null;
  reviewed_at: string | null;
  notes: string;
  created_at: string;
}

export interface DuplicateRecord {
  type: "transaction" | "invoice";
  id: number;
  [key: string]: string | number | boolean | null;
}

export interface DuplicateCandidateDetail extends DuplicateCandidate {
  evidence: Record<string, unknown>;
  record_a: DuplicateRecord | null;
  record_b: DuplicateRecord | null;
}

export type RiskCategory = "low" | "medium" | "high" | "critical" | "unscored";
export type RiskComponentKey = "A" | "B" | "G" | "F" | "D" | "H";

export interface RiskComponent {
  available: boolean;
  value: number | null;
  reason: string;
  source: Record<string, unknown>;
  weight: number;
  contribution: number | null;
  imputed: boolean;
}

export interface RiskAssessment {
  id: number;
  transaction: number;
  external_id: string;
  amount: string;
  tx_type: string;
  occurred_at: string;
  account: number;
  account_ref: string;
  overall_score: number | null;
  category: RiskCategory;
  weight_coverage: number;
  low_coverage: boolean;
  capped: boolean;
  policy: string;
  config_version: number;
  run: number;
  component_values: Partial<Record<RiskComponentKey, number | null>>;
  computed_at: string;
}

export interface RiskAssessmentDetail extends RiskAssessment {
  components: Record<RiskComponentKey, RiskComponent>;
  algorithm_version: string;
  detection_run: number | null;
  behavior_run: number | null;
  graph_snapshot: number | null;
}

export interface RiskConfig {
  id: number;
  version: number;
  weights: Record<RiskComponentKey, number>;
  thresholds: { medium: number; high: number; critical: number };
  missing_signal_policy: "renormalize" | "neutral_prior" | "strict";
  min_coverage: number;
  model_version: number | null;
  model_version_name: string | null;
  is_active: boolean;
  source: "default" | "manual" | "calibrated";
  notes: string;
  created_by_email: string | null;
  created_at: string;
  used_by_assessments: boolean;
}

export interface RiskRun {
  id: number;
  dataset: number;
  dataset_name: string;
  config: number;
  config_version: number;
  status: RunStatus;
  params: Record<string, unknown>;
  rows_total: number;
  rows_scored: number;
  category_counts: Record<string, number>;
  coverage_summary: Record<string, number>;
  error_message: string;
  created_by_email: string | null;
  created_at: string;
  finished_at: string | null;
}

export type ExplanationMethod =
  | "shap"
  | "lime"
  | "feature_importance"
  | "behavioral"
  | "graph"
  | "risk_breakdown"
  | "summary";

export interface AttributionRow {
  name: string;
  label: string;
  value: number;
  display: string;
  contribution: number;
  rule?: string;
}

export interface Explanation {
  id: number;
  transaction: number | null;
  method: ExplanationMethod;
  prediction: number | null;
  assessment: number | null;
  model_version: number | null;
  model_version_name: string | null;
  payload: {
    features?: AttributionRow[];
    score?: number;
    threshold?: number;
    space?: string;
    base_value?: number;
    algorithm?: string;
    note?: string;
    background?: string;
    sections?: { title: string; text: string }[];
    timeline?: {
      transaction_id: number;
      external_id: string;
      occurred_at: string;
      amount: string;
      tx_type: string;
      sender: string;
      receiver: string | null;
      is_this_transaction: boolean;
    }[];
    disclaimer?: string;
  };
  narrative: string;
  generator_version: string;
  generated_at: string;
  current: boolean;
  stale_reason: string;
  note: string;
  disclaimer: string;
}

export interface ExplanationJob {
  id: number;
  status: RunStatus;
  result: { created: string[]; skipped: Record<string, string> };
  error_message: string;
}

export type AlertSeverity = "low" | "medium" | "high" | "critical";
export type AlertStatus = "new" | "acknowledged" | "escalated" | "closed";

export interface AlertRow {
  id: number;
  alert_type: string;
  type_label: string;
  severity: AlertSeverity;
  status: AlertStatus;
  dataset: number | null;
  dataset_name: string | null;
  transaction: number | null;
  transaction_external_id: string | null;
  account: number | null;
  account_ref: string | null;
  assessment: number | null;
  risk_score: number | null;
  reason: string;
  assignee: number | null;
  assignee_email: string | null;
  acknowledged_at: string | null;
  escalated_at: string | null;
  closed_at: string | null;
  outcome: string;
  created_at: string;
}

export interface AlertDetail extends AlertRow {
  evidence_snapshot: Record<string, unknown>;
  escalation_reason: string;
  close_notes: string;
  policy_version: number;
  dedup_key: string;
  cases?: { id: number; case_ref: string; status: string }[];
}

export interface AlertEventRow {
  id: number;
  event_type: string;
  actor_email: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AlertSummary {
  open_by_severity: Record<AlertSeverity, number>;
  by_status: Partial<Record<AlertStatus, number>>;
  unassigned_open: number;
}

export interface AlertPolicy {
  id: number;
  version: number;
  config: Record<string, unknown>;
  is_active: boolean;
  notes: string;
  created_by_email: string | null;
  created_at: string;
}

export interface NotificationRow {
  id: number;
  channel: string;
  recipient: string;
  status: string;
  error: string;
  sent_at: string;
}

export type CaseStatus =
  | "new"
  | "under_review"
  | "investigation"
  | "escalated"
  | "resolved"
  | "closed";
export type CasePriority = "low" | "medium" | "high" | "critical";
export type CaseOutcome =
  "confirmed_suspicious" | "false_positive" | "inconclusive" | "referred";

export interface CaseRow {
  id: number;
  case_ref: string;
  title: string;
  priority: CasePriority;
  status: CaseStatus;
  dataset: number | null;
  assignee: number | null;
  assignee_email: string | null;
  created_by_email: string | null;
  auto_created: boolean;
  opened_at: string;
  outcome: CaseOutcome | "";
  closed_at: string | null;
  alert_count: number;
  transaction_count: number;
}

export interface CaseDetail extends CaseRow {
  description: string;
  resolution_summary: string;
  resolved_at: string | null;
  resolved_by_email: string | null;
  closed_by_email: string | null;
  allowed_transitions: CaseStatus[];
  read_only_reason: string | null;
  alerts: AlertRow[];
}

export interface CaseNoteRow {
  id: number;
  kind: "comment" | "note";
  author: number;
  author_email: string;
  body: string;
  revision_count: number;
  edited: boolean;
  created_at: string;
}

export interface CaseEvidenceRow {
  id: number;
  original_name: string;
  sha256: string;
  mime: string;
  size: number;
  description: string;
  uploaded_by_email: string | null;
  created_at: string;
}

export interface CaseEventRow {
  id: number;
  event_type: string;
  actor_email: string | null;
  from_status: string;
  to_status: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface CaseTransactionRow {
  id: number;
  transaction: number;
  external_id: string;
  amount: string;
  tx_type: string;
  occurred_at: string;
  sender: string;
  receiver: string | null;
  note: string;
}

export interface CaseAccountRow {
  id: number;
  account_ref: string;
  account_type: string;
  roles: string[];
}

export interface CaseSummary {
  by_status: Partial<Record<CaseStatus, number>>;
  open_by_priority: Record<CasePriority, number>;
  outcomes: Partial<Record<CaseOutcome, number>>;
  unassigned_open: number;
}
