# 15 — Decision Log

Status: **Accepted** (follows master prompt), **Proposed** (needs your approval), **Deferred**.

| ID | Decision | Status | Rationale / trade-off |
|---|---|---|---|
| D-001 | Django is the only backend; research doc's Node/Express + FastAPI split is **not** used | Accepted (master prompt Part 3.2) | One language for web+ML, one auth/RBAC surface, simpler deploy. Research doc §11 differs — logged so you can explain the change in your evaluation. |
| D-002 | Develop in Docker with **Python 3.12 and Node 22 LTS**, not the host's Python 3.14 / Node 25 | **Proposed** | Host runtimes are new; PyTorch/XGBoost/SHAP(numba) wheels may lag 3.14, and Node 25 is non-LTS. Cost: Docker required. |
| D-003 | Modular monolith, no microservices | Accepted | Per prompt; revisit only on a measured scaling need. |
| D-004 | Name the pure-Python graph library `graph_engine_lib/` (Django app stays `apps/graph_engine`) | **Proposed** | Prompt's tree has two `graph_engine` modules; avoids import confusion. |
| D-005 | Roadmap refinements R1–R5 (audit/registry earlier, UI slice per phase, 5A–5D split, Phase 7B, risk after 6/7/8) | **Proposed** | Dependency correctness; avoids a big-bang frontend. |
| D-006 | Create app/directory skeletons only when their phase starts | Accepted | Prompt: no unnecessary empty dirs. |
| D-007 | Add TanStack Query, React Hook Form + Zod, React Router to the frontend stack | **Accepted** (proceeded 2026-11-19; installed in Phase 2) | Needed for server-state/loading/error handling and form validation; no major tech replaced. |
| D-008 | Roles stored as `Role` + permission codenames (data), single role per user | **Implemented** (Phase 2) | Meets "role management" and testable matrix; simpler than multi-role. |
| D-009 | Password hashing: bcrypt (`BCryptSHA256PasswordHasher`) per prompt; Argon2 is stronger, mentionable as upgrade | Accepted (bcrypt) | Prompt demands bcrypt-compatible. |
| D-010 | PDF generation with ReportLab (+matplotlib for charts) | **Proposed** | Pure Python, no system libs; WeasyPrint gives nicer HTML templates but needs Pango/Cairo. |
| D-011 | Neo4j projection loading mode for PaySim: full / fraud-neighbourhood subset / aggregated edges — decided after Phase 7 benchmark | **Proposed** | 6.36M edges is heavy on a laptop; PG stays authoritative. |
| D-012 | GNN/PyG is gated on Phase 7B result and scope, not built by default | Accepted (prompt Module 4) | Avoid complexity for appearance. |
| D-013 | Prediction storage policy: full for small runs; above score floor + aggregates for 6M-row runs | **Proposed** | 6M rows × models × runs bloats PG. |
| D-014 | Case resolution and closure are separate permissions; closing may require a second role (configurable) | **Proposed** | Four-eyes control; affects RBAC. |
| D-015 | Deployment target (Render vs AWS) chosen in Phase 16 using measured resource needs | Deferred | Budget dependent. |
| D-016 | Explanation narratives are deterministic templates, not LLM-generated | Accepted | LLM summaries are future scope; keeps explanations traceable to evidence. |
| D-017 | Missing signals: default `renormalize` over available weights + stored coverage; never silent zero | Accepted (prompt Module 7) | See doc 08. |
| D-018 | Ground-truth labels stored separately from predictions and hidden from analyst views by default | **Proposed** | Prevents presenting dataset labels as model output. |
| D-019 | JWT: access in memory, refresh in httpOnly cookie, rotation + blacklist | **Implemented** (Phase 2) | Reduces XSS token theft vs localStorage. |
| D-020 | `alerts` never imports `investigations`; case linking via signal in `investigations` | Accepted | Avoids circular dependency. |
| D-021 | Frontend linter is **oxlint** (what the Vite template ships), not ESLint as docs 04/13 said; TypeScript 7 / Vite 8 / Vitest 5 resolved by the scaffold | **Needs your confirmation** | Works and passes; switch to ESLint if your evaluators expect it. |
| D-022 | Default-deny RBAC: `HasRolePermission` is a default permission class; views must declare `required_permissions`; a generated test fails if any route lacks one | Implemented | Fail-closed against forgotten checks. |
| D-023 | Audit immutability enforced by a PostgreSQL trigger (not just app code); users are never deleted | Implemented | Single DB role in dev, so REVOKE is not usable; trigger holds even for the app role. Superuser can still drop the trigger — noted as limitation. |
| D-024 | Throttle/cache counters in Redis DB 1 (Celery broker stays on DB 0) | Implemented | `cache.clear()` in tests must not wipe the broker. |
| D-025 | Transaction list uses hybrid pagination: page-number by default, keyset when `?cursor=` is passed | Implemented | OFFSET at page 20,000 of 1M rows took 832 ms; keyset stays ~5 ms. Cost: keyset has no total count or page jumps. |
| D-026 | Search is exact-match (transaction ID or account ref), not substring | Implemented | Substring `ILIKE` cannot use the B-tree indexes and would scan millions of rows. Trigram search can be added later if needed. |
| D-027 | Mock data is only created by `seed_mock_transactions`, names must start with `MOCK`, flagged synthetic | Implemented | Prevents random data being mistaken for real/research data (docs/09). |
| D-028 | Import provenance is the `Transaction.import_job` FK; no per-row 'imported' TransactionEvent | Implemented | An event per row would double write volume (6M extra rows). Status changes and other later actions still write events. |
| D-029 | One DB transaction per 50k-row chunk, counters updated in the same transaction; per-dataset advisory lock per chunk | Implemented | Exact checkpoint for resume; serialises concurrent writers so duplicate checks stay correct. Cancelling keeps rows already committed (documented, not rolled back). |
| D-030 | One worker per job via a session advisory lock; resume of a stuck job needs `force` | Implemented | Found live: a killed worker left a job `running` forever. The lock is freed when the connection dies, so a forced resume can never double-process. |
| D-031 | Added dependencies `pandas`, `numpy` (pandas dep), `openpyxl` | Implemented | pandas is needed for ML anyway and gives fast vectorised cleaning; openpyxl is the standard Excel reader (read-only mode, cached values only). |
| D-032 | WebSockets: single-use 30 s ticket from REST, per-user groups; the Phase 1 `/ws/echo/` smoke route was removed | Implemented | Avoids JWTs in URLs; progress goes only to the job's owner. |
| D-033 | API line length 120 (ruff) | Implemented | Long SQL/message literals; formatting only. |
| D-034 | Real datasets live in `datasets/raw/` (read-only, SHA-256 checked before/after); cleaned and split copies go to `datasets/processed/` as parquet with a manifest | Implemented | Raw data is never modified; every run is reproducible and auditable. Added `pyarrow`, `scikit-learn`, `scipy` (`requirements/ml.txt`) and mounted `./datasets` into the backend containers. |
| D-035 | ML code lives in the plain-Python package `backend/ml_engine/` (no Django imports) | Implemented | Keeps experiments runnable from the CLI (NFR-07) and testable without a database. |
| D-036 | Chronological 70/15/15 split snapped to whole time values, verified on every run (`verify_split`) | Implemented | Leakage register item 1; ties on a timestamp never straddle splits. |
| D-037 | ULB: exact duplicates dropped (1,081); PaySim: no rows removed | Implemented | A duplicate across splits would leak; PaySim has no duplicates and no transaction id, so nothing is dropped. |
| D-038 | PaySim `step`/hour-of-run is not a baseline feature; every model is reported with and without balance-derived features | Planned (Phase 5A) | Measured: fraud/hour is constant while volume per hour collapses, and 98% of frauds drain the sender (doc 19). |
| D-039 | PaySim features computed on the full time-ordered frame but only from strictly earlier steps (same-step rows do not see each other); test rows may use train/validation history | Implemented | That is what a deployed system sees; verified by a future-perturbation test. |
| D-040 | Classification threshold = max F1 on validation, frozen for test; PR-AUC is the primary metric; bootstrap CI (100 resamples) reported | Implemented | Leakage item 5; ROC-AUC alone is misleading at 0.1% prevalence. |
| D-041 | Registry versions are `<dataset>-s<seed>-<artifact hash[:8]>`; `register_experiment` is idempotent; the research datasets are recorded by SHA-256 (`training_data_sha256`), not as platform `Dataset` rows | Implemented | Research data is not imported into the transaction tables (doc 09). |
| D-042 | Added `xgboost` (pulls `nvidia-nccl-cu13`, ~200 MB, unused on CPU) | Implemented | Needed for the planned XGBoost model; the GPU library is a transitive dependency of the wheel. |
| D-043 | Random Forest trains on all train positives plus 400k sampled negatives; XGBoost uses the full train split | Implemented | Full-data RF on 4.46M rows is slow for little gain; resampling is applied to train only (leakage item 5). |
| D-044 | Model selection uses validation PR-AUC only; test is scored once after the threshold is frozen | Implemented | No test-set tuning. Early stopping also uses validation (documented). |
| D-045 | PaySim results are always reported for `core` and `core+balance`; the `core` figure is the one quoted as detection skill | Implemented | Balance fields saturate the problem in this simulator (doc 08). |
| D-046 | Added `torch` (CPU wheel via the PyTorch extra index) for the autoencoder | Implemented | Required by the plan (doc 04/08); only the CPU build is installed. `--extra-index-url` is declared in `requirements/ml.txt`. |
| D-047 | LOF and One-Class SVM are fitted on seeded unlabeled train subsamples (50k / 20k rows); their train-split metrics use a 200k-row sample | Implemented | O(n²) / super-linear cost; documented as a limitation. |
| D-048 | 5C models are not tuned (single documented configuration) | Implemented | Unsupervised tuning needs labels, which would blur the unsupervised claim; revisit only if justified. |
| D-049 | Detection scores a whole dataset per run (no scope filter); every transaction gets a `Prediction` row | Implemented | Simple and auditable; histogram and top-k come from one table. Capped at 2M rows. |
| D-050 | Artifacts load only from `ML_ARTIFACTS_DIR` with a matching SHA-256 | Implemented | Pickle executes code on load; hash + directory check blocks swapped or foreign files. |
| D-051 | The platform reuses `ml_engine.features.paysim.build_features` unchanged; missing `step` falls back to whole hours since the first transaction | Implemented | One feature implementation for training and serving (verified equal on real data). Fallback is a documented approximation. |
| D-052 | Model-registry API is read-only; models are registered by the `register_experiment` command, not through the API | Implemented | Training stays a reproducible CLI workflow (NFR-07); activation and training jobs are deferred. |
| D-053 | Behavior = an account's outgoing transactions; history strictly earlier in (occurred_at, id) order, 90-day window, latest 500 | Implemented | Spending patterns; deterministic tie handling prevents same-timestamp leakage (tested). |
| D-054 | Deviation = 0.5·max + 0.5·weighted mean of available components; cold start (<5 prior) is `unavailable` with null score | Implemented | A single extreme signal must not be averaged away; unavailable is never 0 (D-missing-signal policy). Constants are uncalibrated until Phase 9. |
| D-055 | Live profile/trend/transaction endpoints compute on demand; runs persist results and profile snapshots (accounts with history) | Implemented | GETs do not write; stored results support ranking and later risk aggregation. |
| D-056 | Found by the batch==live test: pandas 3 datetimes are microsecond-resolution, so epoch conversion uses `Timedelta.total_seconds()` instead of `astype(int64)/1e9` | Fixed | Silent 1000× time error would have corrupted batch scores. |
