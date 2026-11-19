# 06 — Database Design

> **Implemented so far (migrations exist):** `accounts` (Permission, Role, User), `audit` (AuditLog + append-only trigger), `datasets` (Dataset, ColumnMappingProfile, ImportJob, ImportRowError), `transactions` (Account, Transaction, TransactionEvent + append-only trigger `transactions/0002`), `model_registry` (MLModel, ModelVersion, ModelEvaluation — tables only). Everything else is still a proposal.
> **Phase 4 additions:** `ImportJob` gained `source` (file|api), `mapping` (resolved JSON), `dup_policy`, `stored_path`, `cancel_requested`, `updated_at`. Per-job provenance is the `Transaction.import_job` FK; no per-row 'imported' events are written (decision D-028).
> **Deviations (Phase 3):** `Transaction` indexes named explicitly; the dataset/time index is `(dataset, -occurred_at, -id)` so the default list and keyset paging are index-ordered; `Dataset.row_count` is a stored counter (maintained by imports/seeding) because live `COUNT(*)` is too slow for list views.
> **Deviation from proposal:** `Role↔Permission` is an M2M to a `Permission` table (codenames seeded from `apps/accounts/registry.py`); `User` has `failed_login_count`/`locked_until` and no `is_superuser` (admin access = Super Admin role).

Conventions: `bigint` identity PKs (UUID only for public-facing tokens); `created_at/updated_at` on mutable tables; money as `Numeric(18,2)`; timestamps `timestamptz` UTC; JSONB for flexible metadata; FK `PROTECT` for evidential records (nothing in evidence tables cascades on delete).

## PostgreSQL entities
### accounts
- **User**(email unique, password, full_name, role FK→Role, is_active, failed_login_count, locked_until, last_login, created_at)
- **Role**(name unique, description, is_system) + M2M **Permission codenames** (resource.action). Seeded: super_admin, financial_analyst, fraud_investigator, auditor, management.

### audit
- **AuditLog** (append-only; DB-level REVOKE UPDATE/DELETE for app role): actor FK null, actor_email snapshot, action, resource_type, resource_id, ip, user_agent, request_id, changes JSONB, created_at. Index (resource_type, resource_id, created_at), (actor, created_at), (action, created_at).

### datasets
- **Dataset**(name, source_type [paysim|ulb|elliptic|custom], is_synthetic, description, row_count, schema_version, content_sha256)
- **ColumnMappingProfile**(dataset FK, name, mapping JSONB, dup_policy, created_by)
- **ImportJob**(dataset FK, file path/name/size/sha256, status [pending|validating|running|completed|failed|cancelled|completed_with_errors], rows_total/processed/accepted/rejected/duplicates, celery_task_id, started_at, finished_at, created_by, error_summary)
- **ImportRowError**(job FK, row_number, raw JSONB, error_code, message) idx(job,row_number)

### transactions
- **Account**(dataset FK, account_ref, account_type [customer|merchant|unknown], first_seen_at, last_seen_at, metadata JSONB) **UNIQUE(dataset, account_ref)**
- **Transaction**(dataset FK, import_job FK, transaction_id [external/generated], sender FK, receiver FK null, amount Numeric CHECK ≥0, currency null, tx_type, occurred_at timestamptz, step int null, sender_balance_before/after null, receiver_balance_before/after null, merchant_name/category null, status, ground_truth_label bool null *(dataset label — kept apart from predictions)*, metadata JSONB, created_at) **UNIQUE(dataset, transaction_id)**; indexes: (dataset, occurred_at), (sender, occurred_at), (receiver, occurred_at), (dataset, tx_type), (amount), (status), (import_job). Optional range-partition by dataset/month if 6M-row benchmarks demand it.
- **TransactionEvent**(transaction FK, event_type [imported|status_changed|flagged|reviewed…], actor, payload, created_at) → transaction-level auditability.

### model_registry
- **MLModel**(name, task_type [supervised|unsupervised|graph], algorithm)
- **ModelVersion**(model FK, version, artifact_path, artifact_sha256, artifact_format, hyperparameters JSONB, feature_schema JSONB, preprocessing_artifact_path, training_dataset FK, training_data_sha256, split_strategy JSONB, random_seed, library_versions JSONB, code_commit, status [candidate|active|retired], trained_at, trained_by)
- **ModelEvaluation**(version FK, split_name, metrics JSONB [precision, recall, f1, pr_auc, roc_auc, fpr, latency_ms, throughput], curves_path, notes) — also used for performance tracking over time.

### detection
- **DetectionRun**(model_version FK, dataset FK, scope JSONB, status, started/finished, created_by)
- **TransactionPrediction**(run FK, transaction FK, score float, predicted_label null, threshold, is_anomaly) **UNIQUE(run, transaction)**, idx(transaction), idx(run, score DESC). Volume control: store full scores for runs ≤ N rows; for 6M-row runs store rows above a configurable score floor plus aggregates (D-013).

### behavioral
- **AccountBehaviorProfile**(account FK, as_of, window_days, tx_count, avg_amount, median_amount, std_amount, p95_amount, daily/weekly/monthly aggregates JSONB, hour_histogram JSONB, merchant_category_dist JSONB null, unique_counterparties, tx_per_day, profile_version) idx(account, as_of)
- **BehaviorAnalysisResult**(transaction FK, account FK, profile FK, deviation_score 0–100, components JSONB, status [scored|unavailable_cold_start])

### graph_engine
- **GraphSnapshot**(dataset FK, as_of, params JSONB, node_count, edge_count, built_at, neo4j_sync_status)
- **AccountGraphMetrics**(snapshot FK, account FK, in_degree, out_degree, weighted_in/out, pagerank, clustering, community_id, graph_risk_score)
- **GraphFinding**(snapshot FK, finding_type [cycle|chain|shared_beneficiary|fan_in|fan_out|dense_cluster], account_ids int[], transaction_ids bigint[], score, evidence JSONB, detected_at)
- **Neo4jSyncState**(dataset FK, last_tx_id, last_synced_at, status, error)

### duplicates
- **InvoiceDocument**(file path, sha256, mime, size, uploaded_by, status [uploaded|validated|ocr_done|extracted|needs_review|reviewed], ocr_text, ocr_confidence, phash)
- **Invoice**(document FK null, vendor_name, vendor_normalized, invoice_number, invoice_number_normalized, amount, currency, invoice_date, extracted_fields JSONB, field_confidence JSONB, verified_by)
- **DuplicateCandidate**(kind [transaction|invoice], record_a_type/id, record_b_type/id, match_class [exact|strong_similar|potential|legitimate_repeat], similarity_score, evidence JSONB, review_status [pending|confirmed_duplicate|not_duplicate|legitimate_repeat], reviewed_by, reviewed_at, notes) **UNIQUE(kind, a, b)** (a<b ordering)

### risk_engine
- **RiskConfig**(version, weights JSONB, thresholds JSONB, missing_signal_policy, is_active, created_by, created_at) — immutable once used; edits create new version.
- **RiskAssessment**(transaction FK, account FK, config FK, algorithm_version, components JSONB `{A:{value,available,source_ref}}`, overall_score, category, weight_coverage, detection_run FK null, snapshot FK null, computed_at) idx(transaction, computed_at), (account, computed_at), (category, computed_at)
- **AccountRiskHistory**(account FK, as_of, score, category, assessment_count)

### explainability
- **Explanation**(prediction FK null, assessment FK null, model_version FK, method [shap|lime|feature_importance|behavioral|graph|risk_breakdown], payload JSONB, narrative text, generated_at, generator_version)
- **InvestigationSummary**(case FK or transaction FK, text, generated_from JSONB refs, generator_version)

### alerts
- **Alert**(alert_type, severity, status, dedup_key, transaction FK null, account FK null, assessment FK null, reason text, evidence_snapshot JSONB, assignee FK null, acknowledged_by/at, escalated_at, created_at) — partial unique on `dedup_key` where status ≠ closed.
- **AlertEvent**(alert FK, event_type, actor, payload, created_at) · **NotificationLog**(alert FK, channel, recipient, status, sent_at, error)

### investigations
- **Case**(case_ref unique `FG-YYYY-NNNNNN` from DB sequence, title, priority, status, assignee, created_by, opened_at, closed_at, outcome null, resolution_summary)
- **CaseAlert**(case, alert) · **CaseTransaction**(case, transaction)
- **CaseNote**(case, author, body, kind [comment|note], created_at) — edits create revisions, no hard delete
- **CaseEvidence**(case, file path, original_name, sha256, mime, size, uploaded_by, description)
- **CaseEvent**(case, event_type, actor, from_status, to_status, payload, created_at) — immutable; drives timeline & audit

### analytics
- **Report**(type, params JSONB, format, status, file path, requested_by, created_at, expires_at)
- **DailyAggregate**(dataset, date, tx_count, tx_value, flagged_count, by_risk_category JSONB, by_type JSONB) — rollup refreshed by beat task.

## Key constraints
Amount ≥ 0; case status/transition enforced in service + DB CHECK on enum; one active RiskConfig; one active ModelVersion per (model, dataset kind); sender ≠ receiver permitted (flag as data-quality note) but both non-null for transfer types.

## Neo4j graph model
```
(:Account {dataset_id, account_ref, pg_id, account_type, risk_score?, community_id?})
(:Account)-[:TRANSFERRED {tx_pk, tx_id, amount, ts, tx_type, risk_category?}]->(:Account)
(:Finding {pg_id, type, score})-[:INVOLVES]->(:Account)
Constraints: UNIQUE (dataset_id, account_ref) on Account; UNIQUE tx_pk on TRANSFERRED (via relationship property index)
```
**Boundary:** PG owns all business/investigation data. Neo4j stores only IDs + minimal edge attributes needed for traversal; details always re-fetched from PG by `pg_id`.

## Measured query performance (Phase 3, 2026-11-19)
Setup: **1,000,000 MOCK rows** (random data; 50,000 accounts) in Postgres 16 inside Docker on a laptop, all indexes present, timed through the real DRF stack (serialization, permission check, filters, COUNT), median of 5 runs after a warm-up. Bulk generation took 33 s. Indicative only: single run, one machine, no concurrent load.

| Request | Median |
|---|---|
| List page 1 (dataset filter, with COUNT) | 34 ms |
| List with type+status filter | 32 ms |
| Amount range / 1-day range / exact sender | 16 / 6 / 6 ms |
| Search `q` = transaction ID / account ref | 4 / 5 ms |
| Sort by amount desc (with/without type filter) | 32 / 29 ms |
| Transaction detail / related / account detail / account transactions | 2 / 2 / 2 / 3 ms |
| **Page-number, page 20,000 (OFFSET 500k)** | **832 ms** (misses the 500 ms target; why keyset exists) |
| **Keyset (`?cursor=`) pages 1–10 vs 391–400** | **4.3 ms vs 4.8 ms** (flat; 400 pages, 10,000 rows, 0 duplicates) |

The 6.36M-row PaySim case has not been measured; `COUNT(*)` and OFFSET cost grow with size, so large datasets should use filters or `?cursor=`. Insert cost with 7 transaction indexes is the trade-off for fast reads; Phase 4 will measure real import throughput and may use deferred index creation for bulk loads.

## Measured import performance (Phase 4, 2026-11-19)
Real stack (HTTP upload → Celery worker → Postgres 16 in Docker on a laptop), **random PaySim-format MOCK files**, `preset=paysim`, `dup_policy=reject`, 50,000-row chunks, all 7 transaction indexes present. Single runs; indicative only.

| File | Rows | Duration | Throughput |
|---|---|---|---|
| mock100k.csv (7.6 MB) | 100,000 | 6.8 s | ~14,700 rows/s |
| mock1m.csv (76 MB) | 1,000,000 | 83.6 s | ~12,000 rows/s |

* **Target missed:** NFR-01 aimed for ≥ 20k rows/s. Measured ~12k rows/s at 1M rows.
* **Where the time goes (one 50k chunk):** read 0.12 s + clean 0.34 s (CPU, ~12%); duplicate-ID check 0.05 s; account upsert+lookup 0.74 s; full COPY incl. accounts 1.78 s. The rest is counters/row-error writes and index growth: throughput falls as the table grows (3.4 s/chunk at 100k vs 4.2 s/chunk at 1M). The bottleneck is PostgreSQL (COPY into 7 indexes + foreign-key checks), not Python.
* **API stayed responsive** during a 1M-row import: list requests 20–50 ms vs ~20 ms idle; `/health/` < 10 ms.
* **6.36M rows (full PaySim) not run.** Extrapolating linearly gives ~9–12 minutes but index growth makes that optimistic; schedule a real run in Phase 15. Possible optimisations if needed: create secondary indexes after bulk load, drop FK checks for the load, larger COPY batches.
* **Bug found by this run:** the first version of the "first/last seen" account update planned badly on freshly loaded tables (minutes for 100k rows). Fixed by ANALYZE + temp-table aggregation; a regression test covers correctness but not the speed.
