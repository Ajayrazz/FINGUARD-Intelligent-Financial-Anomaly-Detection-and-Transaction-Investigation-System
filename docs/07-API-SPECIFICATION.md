# 07 — API Specification (proposal; updated as endpoints are implemented)

Base: `/api/v1/`. Docs: `/api/schema/`, `/api/docs/` (drf-spectacular). JSON only except file uploads (multipart) and downloads.

## Conventions
- **Auth:** `Authorization: Bearer <access>` on everything except `auth/login`, `auth/refresh`, `health/`.
- **Pagination:** page-number (`?page=&page_size=`, max 100) → `{count,next,previous,results}`; large tables (transactions, predictions) offer keyset: `?cursor=`.
- **Filtering/sorting/search:** `django-filter` field params (`?risk_category=high&occurred_after=...`), `?ordering=-amount`, `?search=`.
- **Errors:** `{ "error": { "code": "validation_error", "message": "...", "details": {field:[msgs]}, "request_id": "..." } }`; HTTP 400/401/403/404/409/429.
- **Async operations:** `202 {job_id, status_url}`; poll `GET /jobs/{type}/{id}/` or receive WS events.
- **Permissions:** `Resource.action` codenames from [10](10-SECURITY-AND-RBAC.md). Unlisted = forbidden. Object-level checks (e.g., assignee) in addition.
- **Validation:** DRF serializers; amounts decimal strings; timestamps ISO-8601 UTC.

## Implementation status
**Implemented (Phase 1–2):** `GET /health/`, `GET /health/ready/`, `POST /auth/login/`, `POST /auth/refresh/`, `POST /auth/logout/`, `GET /auth/me/`, `GET|POST /users/`, `GET|PATCH /users/{id}/`, `POST /users/{id}/reset-password/`, `GET|POST /roles/`, `GET|PATCH /roles/{id}/`, `GET /permissions/` (added; lists permission codenames for the role editor), `GET /audit/logs/` + `/{id}/`. **Phase 3 added:** `GET|POST /datasets/`, `GET /datasets/{id}/`, `GET /transactions/`, `GET /transactions/{id}/`, `PATCH /transactions/{id}/status/`, `GET /transactions/{id}/events/`, `GET /transactions/{id}/related/`, `GET /accounts/`, `GET /accounts/{id}/`, `GET /accounts/{id}/transactions/?direction=in|out|both`. **Phase 4 added:** `POST /datasets/{id}/imports/` (multipart upload → 202), `POST /datasets/{id}/imports/preview/`, `GET /imports/` (+ filters `dataset,status,source`), `GET /imports/{id}/`, `GET /imports/{id}/errors/` (+`error_code`), `GET /imports/{id}/errors/export/` (CSV), `POST /imports/{id}/cancel/`, `POST /imports/{id}/resume/` (`{"force": true}` for a stuck job), `GET|POST /mapping-profiles/`, `POST /transactions/ingest/`, `POST /ws/ticket/`, and WebSocket `/ws/events/?ticket=`. **Phase 5D added:** `GET /model-versions/` (headline offline test metrics, `scorable` flag; `?status=&model__task_type=&model__algorithm=`), `GET /model-versions/{id}/` (hyper-parameters, feature schema, all evaluations; the internal artifact path is not exposed), `POST /detection/runs/` (`{model_version, dataset, threshold?}` → 202; 400 `detection_not_possible` if the model's features cannot be computed from stored transactions, it is retired, or the dataset is empty), `GET /detection/runs/` (+`dataset,model_version,status`), `GET /detection/runs/{id}/`, `GET /detection/runs/{id}/predictions/` (highest score first, `?flagged=true`, paginated), `GET /transactions/{id}/predictions/` (history across runs). Permissions: `models.read`, `detection.read`, `detection.run`. Predictions never include `ground_truth_label`. Not built from the list below: model activation, training jobs, `/models/` grouping, `/model-performance/compare/`. **Phase 6 added:** `GET /accounts/{id}/behavior/profile/` and `/behavior/trends/?granularity=day|week|month` (query: `as_of` ISO-8601 [default now], `window_days` 1–365 [default 90], `direction=out|in` [default out]; computed live from transactions strictly before `as_of`), `GET /transactions/{id}/behavior/` (deviation 0–100, coverage, per-component score and evidence; `status: unavailable_cold_start` with a null score when history is too thin), `POST /behavior/runs/` (`{dataset}` → 202), `GET /behavior/runs/`, `GET /behavior/runs/{id}/`, `GET /behavior/runs/{id}/results/` (highest deviation first; `?status=`, `?min_score=`). Permissions `behavior.read`, `behavior.run`. **Phase 7 added:** `POST /graph/snapshots/` (`{dataset, as_of?, window_days?}` → 202), `GET /graph/snapshots/` + `/{id}/`, `GET /graph/findings/?snapshot=|dataset=&type=&min_score=&account=` (highest score first), `GET /graph/accounts/{id}/metrics/`, `GET /graph/accounts/{id}/neighborhood/?depth=1-3&limit≤200&direction=out|in|both&min_amount=&from=&to=&source=auto|postgres|neo4j` (hard caps depth 3 / 200 nodes / 500 edges; `truncated` says when a cap cut the result; `source=neo4j` returns 409 if the projection is unsynced or Neo4j is down), `GET /graph/accounts/{id}/timeline/` (same filters; ≤200 events), `GET /graph/edges/{tx_id}/`, `GET|POST /graph/datasets/{id}/sync/` (GET = status + PostgreSQL↔Neo4j drift counts; POST = 202 queue a sync, `?rebuild=true` wipes and reloads). Permissions `graph.read`, `graph.run`. Not built: `/graph/communities/{id}/`. **Phase 8 added:** `POST /invoices/upload/` (multipart field `file`; PNG/JPEG/PDF ≤ 10 MB, validated by content → 202), `GET /invoices/` + `/{id}/` (extracted fields, per-field OCR confidence, status), `PATCH /invoices/{id}/fields/` (human correction; marks the invoice verified), `GET /invoices/{id}/file/` (authenticated, `nosniff`, server-chosen name), `POST /duplicates/scan/` (`{kind: transaction|invoice, dataset?}` → 202), `GET /duplicates/scans/`, `GET /duplicates/candidates/` (`kind, match_class, review_status, min_score`; highest score first), `GET /duplicates/candidates/{id}/` (both records + evidence), `POST /duplicates/candidates/{id}/review/` (`{decision: confirmed_duplicate|not_duplicate|legitimate_repeat, notes}`), `GET /duplicates/candidates/{id}/report/` (PDF). Permissions `duplicates.read|create|run|review`. The upload route is `/invoices/upload/` (not `POST /invoices/` as proposed). **Phase 9 added:** `GET /risk/assessments/` (+ `run, transaction, account, category, min_score, scored=true`; highest first), `GET /risk/assessments/{id}/` (all components with value, weight, contribution, availability reason, source), `POST /risk/runs/` (`{dataset, config?}` → 202; `config` defaults to the active version), `GET /risk/runs/` + `/{id}/`, `GET /risk/config/` + `/{id}/`, `POST /risk/config/` (new version: `weights` for A,B,G,F,D,H summing to 1, `thresholds` 0<medium<high<critical≤100, `missing_signal_policy`, `min_coverage`, optional `model_version`; 400 with the reason if invalid), `POST /risk/config/{id}/activate/`, `GET /transactions/{id}/risk/` (latest; 404 if never scored) and `/risk/history/`, `GET /accounts/{id}/risk/history/`, `GET /risk/compare/?a=&b=` (flags non-comparable pairs). Permissions `risk.read`, `risk.run`, `risk.configure` (Super Admin only by default). There is no config edit endpoint by design. Not built: a `risk_category` filter on `/transactions/`. **Phase 10 added:** `POST /transactions/{id}/explanations/` (`{methods?, model_version?}`; methods `shap, lime, behavioral, graph, risk_breakdown, summary`; → 202 job), `GET /transactions/{id}/explanations/` (latest of each kind; `?all=true` for history; every item has `model_version`, `prediction`, `assessment`, `current`, `stale_reason`, `note`, `disclaimer`), `GET /explanations/{id}/`, `GET /explanation-jobs/{id}/` (`result.created` / `result.skipped` with reasons), `GET /transactions/{id}/explanations/report/` (PDF), `POST|GET /model-versions/{id}/importance/` (global feature importance). Permissions `explain.read`, `explain.generate`. **Phase 11 added:** `GET /alerts/` (`status, open=true, severity, alert_type, dataset, transaction, account, assignee=me|none|<id>, category, created_after/before`; ordered open-first, severity, risk score, newest), `GET /alerts/{id}/` (with the evidence snapshot), `POST /alerts/{id}/acknowledge|assign|escalate|close/` (`{assignee}`, `{reason}`, `{outcome, notes}`; invalid transitions are 409), `GET /alerts/{id}/events/` and `/notifications/`, `GET /alerts/summary/` (counts only), `GET /alerts/assignees/`, `POST /alerts/evaluate/` (`{dataset}` → 202), `GET /alerts/runs/`, `GET|POST /alerts/policy/` + `POST /alerts/policy/{id}/activate/`, `GET /transactions/{id}/alerts/`. Permissions `alerts.read|summary|run|acknowledge|assign|escalate|close|configure`. WebSocket: `alert.created` and `alert.updated` events go to every connected user with `alerts.read`. Not built: `create-case` / `link-case` (Phase 12), `has_alert` filter on `/transactions/`. **Phase 12 added:** `GET|POST /cases/` (`status, open=true, priority, assignee=me|none|<id>, outcome, dataset, search [case number prefix, title, account reference], opened_after/before`; open first, then priority, then newest; POST `{title, description?, priority?, alert?, transactions?}`), `GET|PATCH /cases/{id}/` (PATCH title/description/priority only; the detail carries `allowed_transitions` for the caller and `read_only_reason` when closed), `POST /cases/{id}/transition/` (`{to_status, reason?, outcome?, summary?}`; 409 for an illegal move, 403 if the target status needs a permission the caller lacks), convenience `POST /cases/{id}/escalate|resolve|close|assign/`, `GET /cases/{id}/events/` (timeline), `GET|POST /cases/{id}/notes/` (`{kind: comment|note, body}`), `GET|PATCH /cases/{id}/notes/{note}/` (GET = every revision; PATCH adds one), `GET|POST /cases/{id}/evidence/` (multipart `file`, `description`), `GET /cases/{id}/evidence/{e}/download/`, `GET|POST /cases/{id}/alerts/`, `GET|POST /cases/{id}/transactions/`, `GET /cases/{id}/accounts/`, `GET /cases/{id}/report/` (PDF), `GET /cases/summary/` (counts), `GET /cases/assignees/`, `POST /alerts/{id}/create-case/` and `/link-case/` (`{case}`). Permissions `cases.read|summary|create|update|assign|transition|escalate|resolve|close|comment|note|evidence`. There is no delete anywhere. Everything else below is still a proposal.

**Transactions as built:** filters `dataset, sender, receiver` (exact account ref), `tx_type, status, amount_min/max, occurred_after/before`, and `q` (exact transaction ID or account ref — exact on purpose so the indexes are used; no substring search yet). Sort with `ordering=occurred_at|amount|id` (prefix `-` for descending). Default pagination is page-number (`page`, `page_size` ≤ 100, includes `count`). Adding `?cursor=` (empty first, then the opaque `next` URL) switches to keyset pagination: no `count`, no random page access, flat latency at any depth. `ground_truth_label` is never returned (D-018). Status changes require `transactions.update_status`, reject no-op/unknown statuses with 400, and write a `TransactionEvent` + audit record in one DB transaction. `POST /transactions/ingest/` is Phase 4. The Management role has no row-level access (aggregates arrive in Phase 14).

**Imports as built:** upload fields `file`, `mapping` (JSON string `{"columns": {source: canonical}, "options": {...}}`), `preset` (`paysim`), `mapping_profile` (id) and `dup_policy` (`reject` default | `skip` | `flag`); mapping precedence: explicit JSON > profile > preset > auto-suggestion; an invalid mapping is a 400 and no job/file is created. Files: `.csv`/`.xlsx` only, checked by extension, size (CSV 2 GB, XLSX 100 MB, configurable), magic bytes and (XLSX) zip-bomb limits; stored under a random name; the client filename is only kept as a label. Job states: `pending → validating → running → completed | completed_with_errors | failed | cancelled`. Counters: `rows_processed = accepted + rejected + skipped duplicates`; `rows_duplicate` counts duplicate IDs under any policy. Only the first 10,000 row errors per job are stored (counts stay exact). Row numbers count data rows excluding the header; blank lines are ignored. Ingest API: ≤ 1000 records, canonical field names, per-record results (`accepted | rejected | duplicate_skipped | accepted_flagged_duplicate`), default `dup_policy=skip` so retries are idempotent. WebSocket events are pushed only to the user who started the job (`{"type": "import.progress", "data": {...}}`); tickets are single-use and expire after 30 s.

**Behavior as built (auth):** refresh token is only in an httpOnly cookie `fg_refresh` (path `/api/v1/auth/`, SameSite=Strict); login/refresh bodies carry only the access token (15 min). Lockout and throttle both return **429** (`account_locked` / throttled); bad credentials 401 `invalid_credentials` (same message for unknown email). A route or action with no declared permission returns **403** (default deny), including disabled methods (so PUT/DELETE on users give 403 or 405, never succeed). Users and audit logs cannot be deleted. Roles: `super_admin` permissions are immutable; role `name` is immutable; changes take effect on the next request.

## Endpoints (R=read C=create U=update D=delete)
### Auth & users (accounts)
| Method | Path | Notes | Permission |
|---|---|---|---|
| POST | `/auth/login/` | `{email,password}` → `{access, user}` + refresh cookie | public, throttled |
| POST | `/auth/refresh/` · `/auth/logout/` | rotate / blacklist | authenticated |
| GET | `/auth/me/` | profile + permission list (drives UI) | authenticated |
| GET/POST | `/users/` · GET/PATCH `/users/{id}/` | `PATCH is_active` to deactivate; no hard delete | users.* (Super Admin) |
| POST | `/users/{id}/reset-password/` | | Super Admin |
| GET/POST/PATCH | `/roles/` `/roles/{id}/` | permission assignment | roles.* (Super Admin) |

### Datasets & imports
| POST | `/datasets/` · GET `/datasets/` `/datasets/{id}/` | | datasets.* |
| POST | `/datasets/{id}/imports/` | multipart file + `mapping_profile` + `dup_policy` → 202 | imports.create |
| POST | `/datasets/{id}/imports/preview/` | first rows + inferred mapping, no persistence | imports.create |
| GET | `/imports/` `/imports/{id}/` `/imports/{id}/errors/` | status, counters, row errors (paged) | imports.read |
| POST | `/imports/{id}/cancel/` | | imports.create |
| CRUD | `/mapping-profiles/` | | datasets.* |

### Transactions & accounts
| POST | `/transactions/ingest/` | API ingestion `{dataset, transactions:[...]}` (≤ 1000/batch), idempotent on transaction_id; result per row | transactions.ingest |
| GET | `/transactions/` | filters: dataset, sender, receiver, type, status, amount_min/max, occurred_after/before, risk_category, has_alert, label; search on id/account | transactions.read |
| GET | `/transactions/{id}/` | detail incl. latest risk, predictions, alerts, case | transactions.read |
| PATCH | `/transactions/{id}/status/` | monitored status change (audited) | transactions.update_status |
| GET | `/transactions/{id}/events/` | audit trail | transactions.read |
| GET | `/transactions/{id}/related/` | related transactions (same pair/accounts/time window) | transactions.read |
| GET | `/accounts/` `/accounts/{id}/` | with risk summary | accounts.read |
| GET | `/accounts/{id}/transactions/?direction=in|out` | | accounts.read |

### Detection & models
| GET | `/models/` `/model-versions/{id}/` `/model-versions/{id}/evaluations/` | | models.read |
| POST | `/model-versions/{id}/activate/` | | models.manage |
| POST | `/training-jobs/` | `{algorithm, dataset, split, params, seed}` → 202 (admin only) | models.manage |
| POST | `/detection/runs/` | `{model_version, dataset, scope}` → 202 | detection.run |
| GET | `/detection/runs/` `/detection/runs/{id}/` `/detection/runs/{id}/predictions/` | | detection.read |
| GET | `/transactions/{id}/predictions/` | history across versions | detection.read |
| GET | `/model-performance/compare/?versions=` | for Model Performance page | models.read |

### Behavioral
| GET | `/accounts/{id}/behavior/profile/?as_of=` | | behavior.read |
| GET | `/accounts/{id}/behavior/trends/?granularity=day|week|month` | spending trends | behavior.read |
| GET | `/transactions/{id}/behavior/` | deviation + components | behavior.read |
| POST | `/behavior/runs/` | recompute profiles → 202 | behavior.run |

### Graph
| POST | `/graph/snapshots/` | build → 202 | graph.run |
| GET | `/graph/snapshots/` `/{id}/` | incl. Neo4j sync status | graph.read |
| GET | `/graph/accounts/{id}/neighborhood/?depth=&limit=&direction=&min_amount=&from=&to=` | nodes/edges for React Flow (hard caps) | graph.read |
| GET | `/graph/edges/{tx_id}/` | edge → transaction detail | graph.read |
| GET | `/graph/findings/?type=&min_score=` · `/graph/accounts/{id}/metrics/` · `/graph/communities/{id}/` | | graph.read |
| GET | `/graph/accounts/{id}/timeline/` | transactions timeline in network | graph.read |

### Duplicates & invoices
| POST | `/invoices/` | multipart upload (validated type/size/magic bytes) → 202 OCR pipeline | duplicates.create |
| GET | `/invoices/` `/invoices/{id}/` | extracted fields + confidence | duplicates.read |
| PATCH | `/invoices/{id}/fields/` | human correction of OCR fields | duplicates.review |
| POST | `/duplicates/scan/` | transaction/invoice scan → 202 | duplicates.run |
| GET | `/duplicates/candidates/` `/{id}/` | filters: kind, match_class, review_status, min_score | duplicates.read |
| POST | `/duplicates/candidates/{id}/review/` | `{decision, notes}` | duplicates.review |
| GET | `/duplicates/candidates/{id}/report/` | PDF | duplicates.read |

### Risk
| GET | `/risk/assessments/?transaction=&account=&category=` · `/risk/assessments/{id}/` | components, availability, coverage | risk.read |
| POST | `/risk/score/` | score scope → 202 | risk.run |
| GET | `/transactions/{id}/risk/history/` · `/accounts/{id}/risk/history/` · `/risk/compare/?a=&b=` | | risk.read |
| GET/POST | `/risk/config/` · POST `/risk/config/{id}/activate/` | weights/thresholds; validates weights sum & ordering | risk.configure |

### Explainability & reports
| GET | `/transactions/{id}/explanations/` · `/explanations/{id}/` | by method + model version | explain.read |
| POST | `/transactions/{id}/explanations/` | generate SHAP/LIME on demand → 202 | explain.generate |
| POST | `/reports/` | `{type, params, format}` → 202 | reports.create |
| GET | `/reports/` `/reports/{id}/` `/reports/{id}/download/` | | reports.read |

### Alerts
| GET | `/alerts/` `/alerts/{id}/` | filter: status, severity, type, assignee, date, category | alerts.read |
| POST | `/alerts/{id}/acknowledge/` · `/assign/` · `/escalate/` · `/close/` | assign `{assignee}`; escalate `{reason}` | alerts.acknowledge / assign / escalate |
| GET | `/alerts/{id}/events/` | history | alerts.read |
| POST | `/alerts/{id}/create-case/` · `/link-case/` | | cases.create |

### Cases
| GET/POST | `/cases/` | filter: status, priority, assignee, search | cases.read/create |
| GET/PATCH | `/cases/{id}/` | PATCH priority/title only | cases.update |
| POST | `/cases/{id}/transition/` | `{to_status, reason}`; 409 if invalid | cases.transition |
| POST | `/cases/{id}/assign/` · `/escalate/` · `/close/` · `/resolve/` (`outcome`, `summary`) | | per RBAC |
| GET/POST | `/cases/{id}/notes/` · `/evidence/` (multipart) · `/alerts/` · `/transactions/` | | cases.* |
| GET | `/cases/{id}/timeline/` · `/graph/` · `/report/` (PDF) | | cases.read |

### Analytics
All under `/analytics/`, filters `dataset`, `from`, `to` (YYYY-MM-DD) unless noted; `analytics.read`.
`GET datasets/` (id and name only) · `overview/` (transactions, value, flagged, high-risk, open alerts/cases, `refreshed_at`) · `volume/?granularity=day|week|month` (transactions, value, flagged per period) · `risk-distribution/` (latest succeeded risk run per dataset) · `accounts/high-risk/` · `recent-suspicious/` · `investigations/summary/` (by status/priority/outcome, resolution hours mean/median/max) · `false-positives/` (investigator decisions + labelled research view) · `detection-performance/` (test-split PR-AUC/ROC-AUC/recall@1%FPR, measured latency/throughput; no filters).
`GET export/?report=volume|risk-distribution|high-risk-accounts|false-positives|investigations|recent-suspicious&file=csv|pdf` (`analytics.export`, audited `analytics.exported`). `POST refresh/[?dataset=]` rebuilds the daily rollup (`analytics.refresh`, audited). Invalid dataset, date, granularity, report or file → 400 `validation_error`. Fraud trends are the `flagged` series of `volume/`.

### Audit, jobs, system
`GET /audit/logs/` (filters actor/action/resource/date; auditor+admin) · `GET /jobs/{type}/{id}/` · `GET /health/` (liveness) · `GET /health/ready/` (db, redis, neo4j) · `POST /ws/ticket/` (WS auth ticket)

### WebSocket `/ws/events/?ticket=`
Server→client JSON: `{type:"alert.created"|"import.progress"|"case.updated"|"job.finished"|"dashboard.invalidate", data:{…}}`; client may subscribe to `case:<id>` / `import:<id>` (permission-checked).
