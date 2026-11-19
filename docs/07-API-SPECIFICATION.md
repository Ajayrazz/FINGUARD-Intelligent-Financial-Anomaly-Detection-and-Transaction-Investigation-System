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
**Implemented (Phase 1–2):** `GET /health/`, `GET /health/ready/`, `POST /auth/login/`, `POST /auth/refresh/`, `POST /auth/logout/`, `GET /auth/me/`, `GET|POST /users/`, `GET|PATCH /users/{id}/`, `POST /users/{id}/reset-password/`, `GET|POST /roles/`, `GET|PATCH /roles/{id}/`, `GET /permissions/` (added; lists permission codenames for the role editor), `GET /audit/logs/` + `/{id}/`. **Phase 3 added:** `GET|POST /datasets/`, `GET /datasets/{id}/`, `GET /transactions/`, `GET /transactions/{id}/`, `PATCH /transactions/{id}/status/`, `GET /transactions/{id}/events/`, `GET /transactions/{id}/related/`, `GET /accounts/`, `GET /accounts/{id}/`, `GET /accounts/{id}/transactions/?direction=in|out|both`. **Phase 4 added:** `POST /datasets/{id}/imports/` (multipart upload → 202), `POST /datasets/{id}/imports/preview/`, `GET /imports/` (+ filters `dataset,status,source`), `GET /imports/{id}/`, `GET /imports/{id}/errors/` (+`error_code`), `GET /imports/{id}/errors/export/` (CSV), `POST /imports/{id}/cancel/`, `POST /imports/{id}/resume/` (`{"force": true}` for a stuck job), `GET|POST /mapping-profiles/`, `POST /transactions/ingest/`, `POST /ws/ticket/`, and WebSocket `/ws/events/?ticket=`. **Phase 5D added:** `GET /model-versions/` (headline offline test metrics, `scorable` flag; `?status=&model__task_type=&model__algorithm=`), `GET /model-versions/{id}/` (hyper-parameters, feature schema, all evaluations; the internal artifact path is not exposed), `POST /detection/runs/` (`{model_version, dataset, threshold?}` → 202; 400 `detection_not_possible` if the model's features cannot be computed from stored transactions, it is retired, or the dataset is empty), `GET /detection/runs/` (+`dataset,model_version,status`), `GET /detection/runs/{id}/`, `GET /detection/runs/{id}/predictions/` (highest score first, `?flagged=true`, paginated), `GET /transactions/{id}/predictions/` (history across runs). Permissions: `models.read`, `detection.read`, `detection.run`. Predictions never include `ground_truth_label`. Not built from the list below: model activation, training jobs, `/models/` grouping, `/model-performance/compare/`. Everything else below is still a proposal.

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
`GET /analytics/overview/` · `/volume/?granularity=` · `/value/` · `/suspicious/` · `/risk-distribution/` · `/accounts/high-risk/` · `/fraud-trends/` · `/detection-performance/` · `/false-positives/` · `/investigations/summary/` · `/recent-suspicious/` — filters: dataset, date range. Export: `POST /reports/` with analytics type.

### Audit, jobs, system
`GET /audit/logs/` (filters actor/action/resource/date; auditor+admin) · `GET /jobs/{type}/{id}/` · `GET /health/` (liveness) · `GET /health/ready/` (db, redis, neo4j) · `POST /ws/ticket/` (WS auth ticket)

### WebSocket `/ws/events/?ticket=`
Server→client JSON: `{type:"alert.created"|"import.progress"|"case.updated"|"job.finished"|"dashboard.invalidate", data:{…}}`; client may subscribe to `case:<id>` / `import:<id>` (permission-checked).
