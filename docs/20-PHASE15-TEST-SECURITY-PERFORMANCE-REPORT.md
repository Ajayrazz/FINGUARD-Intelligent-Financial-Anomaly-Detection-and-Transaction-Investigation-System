# 20 — Phase 15 report: integration testing, security, performance

All numbers below come from runs on 2026-11-20 on the development machine (Docker Desktop, macOS) against the dev database: 363,508 transactions (largest dataset 343,027 rows), 686k risk assessments, real PaySim/ULB slices. They describe this machine and this data, not a production deployment.

## 1. Test inventory (what was actually run)

| Layer | Result |
|---|---|
| Backend (pytest, real Postgres/Redis) | **374 passed**, 6 skipped (Neo4j-live tests, skipped when Neo4j is unreachable) |
| Backend static | `ruff check .` clean, `mypy .` clean (284 files) — the exact CI commands |
| Frontend | `vitest` **78 passed**; `oxlint` 0 errors (15 warnings, mostly fast-refresh notes); `tsc -b` clean; production build OK |
| Browser E2E (Playwright, isolated stack) | **27 passed**: auth (4), RBAC per role (7), WCAG 2.1 A/AA axe scan of every page, responsive 360/768 px, landing, analytics (3), cross-page journeys (3) |
| Coverage (backend) | **88 %** of 8,485 statements (`pytest --cov`); services/domain/ml/graph/risk libraries mostly 90–98 %. Lowest: `neo4j_store.py` 59 % and `graph_engine/services.py` 75 % (need a live Neo4j), management commands 0 % (CLI tooling run by hand). Frontend coverage is not measured (no coverage tool installed). |

`pytest --cov` is now part of the CI backend job (report only; not a gate).

## 2. Findings and fixes in this phase

| # | Finding | Severity | Fix | Guard |
|---|---|---|---|---|
| F1 | Case PDF and explanation PDF put user/imported text (case title, notes, resolution summary, transaction ids, account refs) straight into ReportLab markup: tag injection, possible `<img src=file://…>` local-file read, and crashes on stray `<` | **High** | Every data-derived string is XML-escaped before it reaches a Paragraph | `test_case_pdf_report_treats_user_text_as_text_not_markup`, `test_explanation_report_escapes_transaction_text` |
| F2 | `GET /risk/assessments/` without a run filter sorted all 686k rows: **12.6 s** | High (performance) | Index `risk_score_global_idx` on `(overall_score DESC NULLS LAST, id)` (migration 0003): **16 ms** | `benchmark_api` before/after |
| F3 | Cases list ran one or two COUNT queries per row (9 queries for 3 cases, 42 for 20) | Medium | `Count(distinct)` annotations on the list queryset | `tests/test_query_counts.py` |
| F4 | `ruff check .` (the CI command) failed with 9 errors from e2e/benchmark files; `mypy .` failed on `config/settings/e2e.py` | Medium (CI would be red) | Per-file ignores for long lines in management commands/e2e settings; typed `MEDIA_ROOT` | CI commands run clean |
| F5 | Initial JS bundle was 947 kB (283 kB gzip): every page loaded up front | Low | Route-level code splitting: **310 kB (98 kB gzip)**; React Flow loads only on the graph pages, ECharts on first chart | `vite build` |
| F6 | The dashboard (a dozen parallel requests) plus two backends and two worker pools exhausted Postgres' 100 connections (found in Phase 14) | Medium | `max_connections=250`; e2e worker concurrency 2 (D-098) | e2e suite stable |

## 3. Security checklist (OWASP Top 10 2021)

| Risk | Control | Evidence |
|---|---|---|
| A01 Broken access control | Default-deny `HasRolePermission`; every route declared (test fails otherwise); generated 403/200 matrix for every endpoint × 5 roles; unauthorised roles get 403 even for ids that do not exist (no existence oracle); mass assignment ignored (role, status, case_ref, closed_at, privilege fields); no per-user data ownership exists by design (role-based) | `test_rbac_matrix.py`, `test_security.py` |
| A02 Cryptographic failures | bcrypt password hashes; access token 15 min, in memory only; refresh in httpOnly SameSite=Strict cookie scoped to `/api/v1/auth`; tampered, `alg: none`, wrong-key, expired and refresh-as-access tokens rejected; production settings: SSL redirect, secure cookies, HSTS 1 year | `test_auth.py`, `test_security.py` |
| A03 Injection | Django ORM everywhere (no string SQL with user input); SQL-injection strings in search/ordering/filters are inert and the table survives; page size capped at 100; analytics rejects malformed dataset/date/granularity with 400; CSV/spreadsheet formula injection neutralised (import error export, analytics export); PDF markup injection fixed (F1) | `test_security.py`, `test_analytics.py`, `test_imports.py` |
| A04 Insecure design | Append-only audit/history by database triggers; four-eyes closure available (D-088, default off); closed cases immutable | `test_cases.py`, `test_security.py` |
| A05 Security misconfiguration | `DEBUG` false in every settings module; error responses leak no traceback or paths; CORS only for configured origins; `nosniff` on responses | `test_security.py` |
| A06 Vulnerable components | Python deps pinned by `constraints.txt`; npm lockfile. **No automated dependency audit was run** (`pip-audit`/`npm audit` not executed in this phase) — see limitations | — |
| A07 Identification & authentication failures | Lockout after 5 failures, login throttle, refresh rotation + blacklist, logout and deactivation revoke tokens, generic login errors | `test_auth.py` |
| A08 Software & data integrity | Uploads: type/size/content validation, SHA-256 recorded, client file name never used for storage, evidence re-hashed on download; model artifacts hashed | `test_imports.py`, `test_invoices.py`, `test_cases.py`, `test_ml_models.py` |
| A09 Logging & monitoring | Auth, user, import, run, case and export actions audited; audit rows cannot be edited or deleted even by code; secrets redacted in `changes` | `test_security.py`, `test_auth.py` |
| A10 SSRF | The server fetches no user-supplied URLs; the one ReportLab path that could (`<img src>`) is closed by F1 | `test_security.py` |

## 4. Performance (NFR-02), 25 requests each after a warm-up

| Endpoint | p50 ms | p95 ms |
|---|---|---|
| transactions list (page 1 / sorted by amount / filtered) | 8.0 / 7.8 / 4.5 | 9.0 / 8.5 / 5.1 |
| transactions list, deep page 5,000 (offset paging) | 152 | 169 |
| transaction / account detail | 1.8 / 1.6 | 2.1 / 1.8 |
| alerts list / summary | 5.6 / 1.3 | 6.2 / 1.4 |
| cases list / detail | 2.9 / 3.6 | 3.1 / 4.0 |
| analytics overview / volume (day) / risk distribution | 3.4 / 1.8 / 1.8 | 3.9 / 1.9 / 1.9 |
| analytics high-risk accounts | 243 | 250 |
| analytics false positives | 69 | 84 |
| analytics detection performance / model versions | 3.1 / 3.8 | 3.9 / 4.5 |
| graph findings | 2.4 | 5.7 |
| **risk assessments list — before F2** | **12,587** | **16,371** |
| **risk assessments list — after F2** | **16** | **17** |

Reproduce: `docker compose exec backend python manage.py benchmark_api --runs 25 --json out.json`.

Inference latency and throughput (NFR-03) are measured per model at registration and shown on the Analytics page: single-transaction median latency 0.05–0.12 ms for XGBoost/logistic regression/one-class SVM/autoencoder, ~4–5 ms for Isolation Forest, ~12 ms for Random Forest, ~14.5 ms for LOF on PaySim; batch throughput from ~21k rows/s (LOF) to tens of millions of rows/s (XGBoost).

## 5. Non-functional requirements scorecard (doc 03)

| ID | Status | Evidence / gap |
|---|---|---|
| NFR-01 import throughput | **Target missed** | ~12k rows/s at 1M rows (target 20k); 6.36M rows not measured (doc 06). Not re-measured this phase. |
| NFR-02 list p95 < 500 ms on 1M+ rows | **Met on measured data; 1M+ not re-measured** | All list/detail p95 ≤ 170 ms on 363k rows (above); the 1M-row transaction check from Phase 3 stands (doc 06). The 6.36M-row case is untested. |
| NFR-03 inference latency/throughput | Met (measured, reported) | §4 |
| NFR-04 modular monolith, scalable workers | Met by design; not load-tested | — |
| NFR-05 idempotent/resumable tasks | Met | resume-from-chunk, job lock, analytics refresh idempotent tests |
| NFR-06 Neo4j sync one-way/idempotent | Met when Neo4j is available | Neo4j-live tests skipped otherwise |
| NFR-07 reproducibility | Met | seeded retraining/identical-metrics and artifact-hash tests |
| NFR-08/09/10 security, privacy, audit | Met per §3; account masking by role not implemented | doc 17 |
| NFR-11 maintainability | **Met**: ruff + mypy + tsc clean; import-linter is **not configured** (gap) | — |
| NFR-12 testability | Backend coverage 88 % (goal 80 %); frontend coverage not measured | §1 |
| NFR-13 accessibility | Axe finds no A/AA violation on every page; manual screen-reader pass not done | e2e `a11y.spec.ts` |
| NFR-14 observability | JSON logs, request ids, health/readiness | — |
| NFR-15 portability | `docker compose up` runs the full stack (verified repeatedly, including `beat`) | — |
| NFR-16 documentation | Updated in the same change as code | docs 06, 07, 13, 15–20 |
| NFR-17 retention / backup-restore drill | **Not done** (Phase 16) | — |
| NFR-18 pinned runtime | Met | — |

## 6. Known gaps carried to Phase 16 or accepted

* No `pip-audit` / `npm audit` run; no dependency-update policy.
* No penetration test, no fuzzing beyond the cases above, no load test beyond single-user latency (`benchmark_api` is sequential).
* Concurrency under real multi-user load, the 6.36M-row import and 1M+ row analytics rollup are unmeasured.
* The browser E2E suite is not in CI (needs the Compose stack); it is run manually per `e2e/README.md`.
* Frontend line coverage unmeasured; ~15 oxlint warnings remain (fast-refresh export patterns).
