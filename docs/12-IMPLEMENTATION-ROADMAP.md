# 12 — Implementation Roadmap

Proposed refinements to the master prompt's 0–16 ordering (rationale in D-005/D-006). Phase numbers are kept so the plan maps 1:1; changes are marked **▲**.

▲ **R1** The `audit` and `model_registry` foundations move earlier (audit in Phase 2, registry models in Phase 3) because every later phase writes to them.
▲ **R2** **UI slice per phase:** each phase ships its frontend pages on real APIs; Phase 13 becomes completion, polish, cross-page workflows and accessibility — not "build all pages at the end".
▲ **R3** Phase 5 split 5A/5B/5C (baseline → tree models + IF → remaining unsupervised/AE) to enforce "baseline first".
▲ **R4** New **Phase 7B**: graph-feature experiments (RQ2) + GNN go/no-go gate — needs ML (5) and graph (7).
▲ **R5** Risk (9) follows Behavioral (6), Graph (7), Duplicates (8) because it consumes B, G, D; alerts (11) consume risk; cases (12) consume alerts.

Global rule for every task: explain → implement → test → run tests → document → update tracker/matrix (Part 8). Each phase ends with a demo + approval gate.

## Dependency overview
`0 → 1 → 2 → 3 → 4 → 5A/B/C`; `3 → 6`; `3 → 7 → 7B(5,7)`; `3 → 8`; `(5,6,7,8) → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16`. Phases 6, 7, 8 are independent of each other and can be reordered by priority after Phase 5.

---
## Phase 0 — Requirement analysis & architecture *(this deliverable)*
Tasks: workspace inspection; docs 00–18; traceability matrix. **Acceptance:** you approve plan and open decisions (doc 15). **Tests:** n/a. **Docs:** all.

## Phase 1 — Environment & foundation
Tasks: 1.1 repo skeleton, `.gitignore`, `git init`; 1.2 Docker (Python 3.12, Node 22) + Compose (postgres, redis, neo4j-later-profile); 1.3 Django project with `config/settings/{base,development,production}`, env loading; 1.4 app skeletons for foundation apps only (accounts, audit) — others created in their phase (no empty dirs); 1.5 DRF + drf-spectacular + CORS + structured logging + error handler; 1.6 Celery+Redis wiring, Channels wiring; 1.7 Vite+React+TS strict+Tailwind shell; 1.8 health endpoints (`/health/`, `/health/ready/`); 1.9 CI (ruff, mypy, pytest, eslint, tsc, vitest); 1.10 README + dev guide.
**Deliverables:** `docker compose up` runs db, redis, backend, worker, frontend. **Acceptance:** health endpoints green; sample Celery task round-trips; WS echo test; frontend renders and calls health; CI green. **Tests:** pytest health/celery/channels smoke; vitest smoke. **Docs:** 04, 14, 15, 16, handoff.

## Phase 2 — Auth, users, RBAC, audit core
Tasks: 2.1 custom User + Role/Permission models + seeds; 2.2 login/logout/refresh (rotation, blacklist, throttle, lockout); 2.3 `HasPerm` permission class + permission registry; 2.4 user & role management APIs; 2.5 `audit` app + `audit.log()` + append-only protection; 2.6 frontend auth (token handling, route guards, PermissionGate, Login, User Management, Audit Logs pages); 2.7 matrix test over every endpoint × role; 2.8 docs.
**Acceptance:** each of 5 roles verified against matrix (403s tested); auth events audited; last-admin protection. **Tests:** unit + API + generated RBAC matrix test + frontend guard tests. **Docs:** 07, 10, 06.

## Phase 3 — DB foundation & transaction management
Tasks: 3.1 datasets/transactions/accounts models + `model_registry` models (tables only) + migrations; 3.2 indexes & constraints; 3.3 transaction + account APIs (search, filter, sort, pagination/keyset, detail, status, events); 3.4 `TransactionEvent` auditability; 3.5 Transactions UI + detail page v1; 3.6 seed test data script (labelled mock); 3.7 query-plan check on 1M synthetic rows.
**Acceptance:** list p95 target met on 1M rows; FK/constraint tests; permissions per matrix. **Docs:** 06, 07.

## Phase 4 — Import & processing pipeline
Tasks: 4.1 upload endpoint + file validation; 4.2 preview + schema inference + mapping profiles; 4.3 chunked CSV reader; 4.4 Excel reader (read-only openpyxl; row limits documented); 4.5 cleaning/missing-value/type conversion; 4.6 duplicate-ID policy; 4.7 bulk-load path (staging + COPY) and account upsert; 4.8 Celery job with progress, cancel, resume; 4.9 WebSocket progress; 4.10 import history + error report UI; 4.11 API ingestion endpoint; 4.12 ingestion interface abstraction (`IngestionSource`) documenting Kafka extension point; 4.13 benchmark 100k→1M→6.36M PaySim.
**Acceptance:** malformed/duplicate/missing-column fixtures handled; progress visible live; 1M import completes without blocking API; throughput recorded. **Tests:** fixtures, task tests (eager + real worker), large-file test (marked slow). **Docs:** 09, 07, 17.

## Phase 5 — ML research & detection models
5A: EDA report; preprocessing; feature engineering (time-respecting); chronological splits; LR baseline; evaluation harness; model registry writes; leakage tests.
5B: Random Forest, XGBoost, Isolation Forest; hyperparameter search; PR-AUC-led comparison; threshold selection; latency/throughput benchmarks.
5C: LOF, OC-SVM, Autoencoder (only after 5B baselines reviewed); ULB benchmark; drift-over-time evaluation (RQ6 first pass); hybrid candidate (RQ1 first pass).
5D: inference service layer, DetectionRun/Prediction storage, detection APIs, Anomaly Detection + Model Performance pages (real data).
**Acceptance:** reproducible re-run gives identical metrics (same seed); leakage tests pass; each algorithm documented per template in doc 08; results labelled with dataset/split. **Tests:** pipeline unit tests, leakage perturbation tests, artifact load/hash tests, API tests. **Docs:** 08, 06, 07, 17.

## Phase 6 — Behavioral analysis
Tasks: profile computation (as-of), avg/daily/weekly/monthly, frequency, timing histogram, merchant category (when present), deviation scoring (robust stats), cold-start handling, historical comparison, trends API, Account Behavior page; includes the "5 × ₹40,000 in 10 min" scenario test.
**Acceptance:** scenario produces high deviation with component breakdown; no future leakage test; unavailable signal represented explicitly.

## Phase 7 — Graph analytics & Neo4j
Tasks: 7.1 Neo4j container + driver + constraints; 7.2 graph builder (NetworkX, as-of); 7.3 algorithms (degree, PageRank, chains with time/hop limits, cycles, shared beneficiaries, communities, dense clusters); 7.4 persist findings/metrics; 7.5 PG→Neo4j sync (watermark, idempotent MERGE, rebuild command, drift check); 7.6 neighbourhood/timeline/edge APIs with caps; 7.7 Relationship Graph page (React Flow); 7.8 graph risk score G; 7.9 performance profile on PaySim subset/full (D-011).
**Acceptance:** planted chain/cycle/fan-in detected; Neo4j rebuild from PG matches counts; killing Neo4j does not break imports; graph page uses real queries.

## Phase 7B ▲ — Graph-feature experiments & GNN gate
Tasks: time-respecting graph features into 5B models; paired comparison (RQ2); decision record on PyG/GNN (D-012). **Acceptance:** documented result regardless of outcome (positive or negative).

## Phase 8 — Duplicates, OCR
Tasks: exact transaction-ID and repeated-payment detection; invoice upload pipeline (validate → preprocess → Tesseract → parse → field extract → validate → match → human review); normalisation; fuzzy (rapidfuzz) + similarity score; image similarity (pHash); classes incl. legitimate repeat; review workflow; PDF duplicate report; Duplicate Detection page.
**Acceptance:** synthetic invoice set with controlled duplicates classified as expected; OCR actually executed on files (test fails if Tesseract missing); human review required before "confirmed".

## Phase 9 — Risk scoring engine
Tasks: component normalisation A,B,G,F,D,H; `RiskConfig` versioning & validation; missing-signal policy + coverage; categories; history; breakdown API; calibration experiments (RQ5); Risk Analysis page; admin config UI.
**Acceptance:** unit tests for every missing-signal combination; reproducible assessment from stored components; calibration report.

## Phase 10 — Explainable AI
Tasks: SHAP (tree), LIME, feature importance, behavioral/graph/risk-breakdown explanations, narrative summaries (template-based, deterministic — not LLM), persistence tied to model/prediction version, PDF report, Explanation panel, fidelity/stability evaluation (RQ4).
**Acceptance:** explanation fetch always returns matching model version; stale-version mismatch test; PDF renders and includes disclaimers.

## Phase 11 — Alerts & notifications
Tasks: alert rules per Module 6 types (high-risk, multiple-tx, unusual activity, suspicious beneficiary, repeated failures when `status` data exists, high-value, rapid movement, behavior change); dedup policy; prioritisation; lifecycle (ack/assign/escalate/close); email (Celery, console backend in dev, SMTP configurable); WebSocket push; Alerts page.
**Acceptance:** duplicate-event test creates one alert; meaningful new reason creates a new one; evidence snapshot preserved.

## Phase 12 — Case management
Tasks: auto case creation from alerts (rules), case ref sequence, assignment/reassignment, validated state machine, notes (versioned), evidence upload (hash, secure storage), related transactions/graph, timeline from `CaseEvent`, escalation, resolution/closure with outcome, closure report PDF, permission tests, Investigations page.
**Acceptance:** every invalid transition rejected (full matrix test); closed case immutable but history viewable; every action audited.

## Phase 13 — Frontend completion
Tasks: end-to-end navigation flows (transaction → accounts → behavior → graph → risk → explanation → alert → case), a11y audit, responsive pass, consistent empty/error states, toasts/confirmations, remove all prototype mocks.
**Acceptance:** Playwright journey passes per role; no page contains static dummy data.

## Phase 14 — Analytics & reporting
Tasks: rollup tables + beat jobs; all Module 10 metrics; false-positive analysis; resolution statistics; model-comparison dashboards; PDF/CSV exports (injection-safe).
**Acceptance:** dashboard numbers reconcile with direct SQL counts in tests.

## Phase 15 — Integration, testing, optimisation
Tasks: E2E, API, DB, ML, graph, RBAC, security tests (OWASP checklist, upload attacks, IDOR); import stress; performance profiling and index/query tuning; bug fixing; coverage report. **Acceptance:** targets in doc 03 measured and recorded (met or documented as limitation).

## Phase 16 — Deployment & final documentation
Tasks: prod compose, secrets, HTTPS, migrations guide, backup/restore drill, deployment (Render or AWS per D-015), user guide, final experiment report (RQ1–RQ6 results from real runs), limitations, demo script.
**Acceptance:** fresh-machine deployment from docs; demo workflow runs end to end.

## Future-scope hooks (not scheduled)
Kafka (ingestion interface), GNN/temporal GNN (7B gate), federated learning, biometrics, device fingerprint, privacy-preserving analysis, drift detection/adaptive ML (RQ6 groundwork), LLM-assisted summaries, multimodal analysis, automated prioritisation with human approval — each recorded as `FUT-xx` rows in the traceability matrix with status *Deferred (architecture-ready)*.
