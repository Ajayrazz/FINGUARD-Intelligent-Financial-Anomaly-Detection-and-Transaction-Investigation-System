"""Regenerates docs/18-REQUIREMENTS-TRACEABILITY.md. Edit DATA, then run: python3 docs/tools/build_traceability.py"""
from pathlib import Path
# prio: P0=MVP, P1=Core, P2=Advanced. Row: (text, phase, prio, acceptance)
D = {}
D["M1 Transaction Monitoring"] = ("FR-M1", "Ph2 auth, Ph3 schema", [
("Import transactions via CSV", "4", "P0", "100k-row CSV imports; accepted+rejected = total"),
("Import transactions via Excel", "4", "P1", "XLSX imports through same pipeline; formulas not evaluated"),
("Support structured transaction data", "3", "P0", "Canonical schema + JSONB metadata stores optional fields"),
("Generate or validate transaction IDs", "4", "P0", "Missing IDs generated deterministically; malformed flagged"),
("Identify sender accounts", "3", "P0", "Sender resolved to Account row per dataset"),
("Identify receiver accounts", "3", "P0", "Receiver resolved to Account; nullable for merchant-less data"),
("Store transaction amounts", "3", "P0", "Numeric(18,2); negatives rejected"),
("Store transaction timestamps", "3", "P0", "UTC timestamptz; step-to-time mapping documented"),
("Identify transaction types", "3", "P0", "tx_type stored/filterable; unknown types preserved"),
("Maintain historical transaction records", "3", "P0", "Records never overwritten; re-import creates new job"),
("Search transactions", "3", "P0", "Search by id/account returns correct rows; indexed"),
("Filter transactions", "3", "P0", "Filters by type/status/amount/date/risk/dataset"),
("Sort transactions", "3", "P0", "Sort by amount/time/risk ascending/descending"),
("View individual transaction details", "3", "P0", "Detail API+page with related entities"),
("Monitor transaction status", "3", "P1", "Status changes validated and audited"),
("API-based transaction ingestion", "4", "P1", "Batch POST idempotent; per-row result"),
("Extensible architecture for future event-stream ingestion", "4", "P2", "IngestionSource interface documented; API + file implement it"),
("Validate imported records", "4", "P0", "Schema/type/range validation rules tested"),
("Detect malformed records", "4", "P0", "Bad rows -> ImportRowError, import continues"),
("Handle duplicate transaction identifiers", "4", "P0", "reject/skip/flag policy honored and reported"),
("Track data import history", "4", "P0", "Every import listed with user, file hash, counts"),
("Display import status and processing errors", "4", "P0", "Live progress + downloadable error report"),
("Transaction-level auditability", "3", "P0", "TransactionEvent trail for each change"),
])
D["M2 Anomaly Detection"] = ("FR-M2", "Ph3, Ph4, model_registry tables", [
("Unusual transaction amount detection", "5", "P0", "Amount-deviation feature/score validated on PaySim"),
("Abnormal transaction frequency detection", "5", "P1", "Windowed-frequency feature; leakage test passes"),
("Unusual transaction timing detection", "5", "P1", "Timing feature/score available"),
("Rapid successive transaction identification", "5", "P1", "Inter-transaction time bursts flagged; scenario test"),
("Unusual fund transfer detection", "5", "P1", "Transfer-specific anomalies scored"),
("Account activity deviation detection", "6", "P1", "Links to behavioral deviation"),
("Supervised ML transaction classification", "5", "P0", "LR/RF/XGB trained on chronological split; reproducible"),
("Unsupervised anomaly detection", "5", "P0", "IF/LOF/OCSVM/AE run without labels"),
("Historical transaction comparison", "5", "P1", "Compare against account history as-of"),
("Automatic generation of suspicious activity alerts", "11", "P0", "Detection/risk output creates deduplicated alerts"),
("Anomaly score calculation", "5", "P0", "Stored normalized score per prediction"),
("Model prediction storage", "5", "P0", "TransactionPrediction rows linked to run/version"),
("Model version tracking", "5", "P0", "ModelVersion with artifact hash, seed, data hash"),
("Detection result history", "5", "P0", "History per transaction across versions"),
("Model performance tracking", "5", "P0", "ModelEvaluation per split/time; comparison page"),
])
D["M3 Spending Patterns"] = ("FR-M3", "Ph3, Ph4", [
("Calculate average transaction amount", "6", "P0", "Mean/median/std per account as-of"),
("Analyze daily spending", "6", "P1", "Daily aggregates API"),
("Analyze weekly spending", "6", "P1", "Weekly aggregates API"),
("Analyze monthly spending", "6", "P1", "Monthly aggregates API"),
("Detect unusually high-value spending", "6", "P0", "Robust z/MAD threshold test"),
("Identify sudden spending increases", "6", "P1", "Rate/amount jump detected in test scenario"),
("Identify unusual transaction timings", "6", "P1", "Hour-of-day rarity score"),
("Analyze merchant-category behavior where available", "6", "P2", "Computed only when data present; else unavailable"),
("Compare transaction frequency", "6", "P1", "Current vs historical rate"),
("Generate historical account behavioral profiles", "6", "P0", "Profile stored with as_of and version"),
("Calculate behavioral deviation scores", "6", "P0", "0-100 score with component breakdown; cold-start unavailable"),
("Show account spending trends", "6", "P1", "Trends API + chart"),
("Compare current vs historical behavior", "6", "P1", "Side-by-side baseline vs current"),
("Store behavioral analysis results", "6", "P0", "BehaviorAnalysisResult persisted"),
])
D["M4 Graph Analysis"] = ("FR-M4", "Ph3, Ph4 (+Ph5 for 17)", [
("Generate account relationship graphs", "7", "P0", "Snapshot built from PG; counts match"),
("Map sender and receiver relationships", "7", "P0", "Directed edges with amount/time/type"),
("Track multi-account transaction chains", "7", "P1", "Time-respecting chains found in planted data"),
("Identify suspicious transaction chains", "7", "P1", "Rapid chain scored and stored"),
("Detect circular transaction patterns", "7", "P1", "Planted cycle detected"),
("Identify shared beneficiaries", "7", "P1", "Fan-in with common senders found"),
("Analyze rapid movement of funds", "7", "P1", "Hop-time limited path scoring"),
("Detect highly interconnected accounts", "7", "P1", "Degree/PageRank/clustering metrics"),
("Identify communities and clusters", "7", "P1", "Louvain communities stored"),
("Visualize suspicious account networks", "7", "P0", "React Flow page on real Neo4j/PG data"),
("View individual account relationships", "7", "P0", "Neighborhood API with caps"),
("Examine incoming and outgoing transactions", "7", "P0", "Direction filter works"),
("Display transaction details on edge selection", "7", "P1", "Edge click loads transaction detail"),
("Identify relevant neighboring accounts", "7", "P1", "Ranked neighbors"),
("Show transaction timelines in connected networks", "7", "P1", "Timeline API/UI"),
("Store graph analysis results", "7", "P0", "GraphFinding/Metrics persisted"),
("Integrate graph-derived features into risk scoring", "9", "P0", "G component consumed by risk engine; also 7B experiment"),
])
D["M5 Duplicates"] = ("FR-M5", "Ph3, Ph4", [
("Exact duplicate transaction ID detection", "8", "P0", "Detected and reported"),
("Repeated payment detection", "8", "P0", "Same sender/receiver/amount in window detected"),
("Duplicate invoice number identification", "8", "P1", "Normalized invoice-number match"),
("Invoice amount comparison", "8", "P1", "Amount equality/relative difference evidence"),
("Vendor information matching", "8", "P1", "Fuzzy vendor match with score"),
("Invoice date comparison", "8", "P1", "Date proximity evidence"),
("OCR-based invoice data extraction", "8", "P1", "Tesseract really executed; fields extracted with confidence"),
("Similar invoice image detection", "8", "P2", "pHash similarity on synthetic set"),
("Duplicate record alerts", "11", "P1", "Alert on candidate above threshold"),
("Duplicate investigation reports", "8", "P1", "PDF report generated"),
("Exact matching", "8", "P0", "Exact class assigned"),
("Fuzzy matching", "8", "P1", "Strong/potential classes assigned"),
("Similarity score calculation", "8", "P1", "Score stored; documented as non-proof"),
("Human verification of potential duplicates", "8", "P0", "Review decision required; audited"),
])
D["M6 Alerts"] = ("FR-M6", "Ph9 risk, Ph5-8 signals", [
("High-risk transaction notifications", "11", "P0", "High/Critical risk triggers alert"),
("Multiple transaction alerts", "11", "P1", "Burst rule triggers once per bucket"),
("Unusual account activity alerts", "11", "P1", "Behavior deviation trigger"),
("Suspicious beneficiary notifications", "11", "P1", "Beneficiary risk trigger"),
("Repeated transaction failure alerts where data available", "11", "P2", "Only when status data present"),
("High-value transfer alerts", "11", "P1", "Configurable threshold trigger"),
("Rapid fund movement notifications", "11", "P1", "Graph chain trigger"),
("Account behavior change alerts", "11", "P1", "Profile shift trigger"),
("Email notifications", "11", "P1", "Celery email sent (dev: console; SMTP tested)"),
("Alert history management", "11", "P0", "Immutable AlertEvent history"),
("Alert filtering", "11", "P0", "Filter API/UI"),
("Alert prioritization", "11", "P0", "Severity/risk ordering"),
("Alert assignment", "11", "P0", "Assign with permission check"),
("Alert acknowledgment", "11", "P0", "Ack recorded with user/time"),
("Alert escalation", "11", "P1", "Escalation with reason"),
("Link alerts to transactions", "11", "P0", "FK + UI link"),
("Link alerts to risk assessments", "11", "P0", "FK + UI link"),
("Link alerts to investigation cases", "12", "P0", "CaseAlert link via signal"),
("Preserve evidence/signals in alerts (de-duplication of same event)", "11", "P0", "Evidence snapshot stored; dedup test passes"),
])
D["M7 Risk Scoring"] = ("FR-M7", "Ph5, Ph6, Ph7, Ph8", [
("Calculate individual risk component scores", "9", "P0", "A,B,G,F,D,H each 0-100 or unavailable"),
("Calculate overall risk score", "9", "P0", "Weighted formula with renormalization"),
("Assign risk category", "9", "P0", "Thresholds 30/60/80 configurable"),
("Store risk score history", "9", "P0", "Immutable assessments retained"),
("Explain risk factor contributions", "9", "P0", "Per-component contribution in API"),
("Configure risk weights", "9", "P0", "Versioned RiskConfig; validation"),
("Configure thresholds", "9", "P0", "Versioned; ordering validated"),
("Support missing or unavailable signals", "9", "P0", "Every missing combination tested; coverage stored"),
("Record scoring algorithm version", "9", "P0", "algorithm_version stored"),
("Link risk scores to transactions and accounts", "9", "P0", "FKs + account history"),
("Display risk breakdown", "9", "P0", "UI breakdown + coverage"),
("Support historical risk comparisons", "9", "P1", "Compare API"),
])
D["M8 Explainable AI"] = ("FR-M8", "Ph5, Ph9", [
("Feature importance analysis", "10", "P0", "Global importance stored per model version"),
("SHAP-based explanations", "10", "P0", "Local SHAP stored; version-matched"),
("LIME-based local explanations", "10", "P1", "LIME run on tabular model"),
("Anomaly score visualization", "10", "P1", "Chart on explanation panel"),
("Behavioral deviation explanation", "10", "P1", "Component-based narrative"),
("Transaction relationship explanation", "10", "P1", "Graph evidence summary"),
("Risk factor breakdown", "10", "P0", "Shown in report/UI"),
("Suspicious transaction timeline", "10", "P1", "Timeline in explanation"),
("Automatically generated investigation summaries", "10", "P1", "Deterministic template summary"),
("Downloadable PDF reports", "10", "P0", "PDF generated by worker; contains disclaimers"),
("Store explanation records", "10", "P0", "Explanation rows persisted"),
("Link explanations to model and prediction version", "10", "P0", "Mismatch test fails build"),
("Show evidence supporting each alert", "10", "P0", "Alert detail shows evidence"),
])
D["M9 Case Management"] = ("FR-M9", "Ph11 alerts, Ph2 RBAC", [
("Automatic case creation", "12", "P0", "Rule-based case from alert"),
("Unique case ID generation", "12", "P0", "DB-sequence FG-YYYY-NNNNNN"),
("Suspicious transaction assignment", "12", "P0", "Transactions attachable to case"),
("Investigation status tracking", "12", "P0", "Six statuses"),
("Analyst comments", "12", "P0", "Comments persisted"),
("Investigation notes", "12", "P0", "Versioned notes"),
("Evidence attachments", "12", "P0", "Hashed, access-controlled files"),
("Transaction history review", "12", "P1", "History view in case"),
("Related account visualization", "12", "P1", "Graph in case workspace"),
("Investigation activity timeline", "12", "P0", "CaseEvent timeline"),
("Case closure", "12", "P0", "Requires outcome; read-only after"),
("Resolution reports", "12", "P1", "PDF closure report"),
("Role-based access management", "12", "P0", "Matrix tests pass"),
("Complete audit history", "12", "P0", "Immutable events"),
("Case filtering and searching", "12", "P0", "Filters/search"),
("Case prioritization", "12", "P1", "Priority field/ordering"),
("Case reassignment", "12", "P0", "Reassign audited"),
("Escalation workflow", "12", "P1", "Escalated status with reason"),
("Link multiple alerts to one case", "12", "P1", "M2M link"),
("Record every important case action", "12", "P0", "Action-coverage test"),
("Validated case status transitions (+history preserved after closure)", "12", "P0", "Full transition matrix test"),
])
D["M10 Analytics"] = ("FR-M10", "Ph3-Ph12 data", [
("Total transaction volume", "14", "P0", "Equals SQL count"),
("Total transaction value", "14", "P0", "Equals SQL sum"),
("Suspicious transaction count", "14", "P0", "Reconciles with risk data"),
("High-risk account statistics", "14", "P1", "Query-backed"),
("Daily transaction trends", "14", "P0", "Rollup-backed chart"),
("Weekly transaction analysis", "14", "P1", "Rollup-backed"),
("Monthly transaction analysis", "14", "P1", "Rollup-backed"),
("Fraud detection trends", "14", "P1", "Time series"),
("Account risk distribution", "14", "P1", "Histogram"),
("Transaction network visualization", "7", "P0", "Overview mini-graph from real data"),
("Risk category distribution", "14", "P0", "Chart"),
("Detection performance analytics", "14", "P1", "From ModelEvaluation"),
("False-positive analysis", "14", "P1", "From case outcomes"),
("Investigation resolution statistics", "14", "P1", "From cases"),
("Exportable analytics reports", "14", "P1", "PDF/CSV, injection-safe"),
("Model performance comparisons", "14", "P1", "Compare view"),
("Historical trends", "14", "P1", "Long-range chart"),
("Recent suspicious activity", "14", "P0", "Live list"),
("Investigation status summaries", "14", "P0", "Counts by status"),
])
D["UI Pages"] = ("FR-UI", "per feature phase; completion Ph13", [
("Login page", "2", "P0", "Auth flow + states"),
("Overview Dashboard page", "14", "P0", "Real KPIs; states"),
("Transactions page", "3", "P0", "Table+import wizard; states"),
("Anomaly Detection page", "5", "P0", "Real runs/scores"),
("Account Behavior page", "6", "P0", "Real profiles/trends"),
("Relationship Graph page", "7", "P0", "Real graph"),
("Risk Analysis page", "9", "P0", "Real assessments"),
("Duplicate Detection page", "8", "P1", "Review workflow"),
("Alerts page", "11", "P0", "Queue + realtime"),
("Investigations page", "12", "P0", "Workspace"),
("Reports page", "10", "P1", "Generate/download"),
("Model Performance page", "5", "P0", "Compare versions"),
("User Management page", "2", "P0", "Users/roles"),
("Audit Logs page", "2", "P0", "Search/filter"),
("Cross-page navigation workflow (transaction -> accounts -> behavior -> graph -> risk -> explanation -> alert -> case)", "13", "P0", "Playwright journey"),
])
D["Roles (Part 6)"] = ("FR-ROLE", "Ph2", [
("Super Admin capabilities (users, roles, settings, risk params, model config, monitoring)", "2", "P0", "Matrix tests"),
("Financial Analyst capabilities", "2", "P0", "Matrix tests"),
("Fraud Investigator capabilities", "12", "P0", "Matrix tests"),
("Auditor read-only capabilities", "2", "P0", "Writes return 403"),
("Management aggregate-only capabilities", "14", "P0", "No row-level access"),
("Backend permission checks for read/create/update/delete/assign/escalate/resolve/close", "2", "P0", "Generated endpoint x role test"),
])
D["Platform (Parts 3,5)"] = ("PLAT", "Ph1", [
("Celery + Redis background jobs with user-visible task status", "1", "P0", "Job status API + WS"),
("Django Channels WebSockets (alerts, import status, investigation updates, dashboard)", "1", "P0", "Realtime tests"),
("Invoice pipeline: upload, validate, preprocess, OCR, parse, extract, validate, match, review", "8", "P1", "Each stage tested"),
("JWT auth, bcrypt-compatible hashing, rate limiting, session expiry", "2", "P0", "Security tests"),
("Secure file upload validation and evidence storage", "4", "P0", "Upload abuse tests"),
("Sensitive-information masking", "2", "P1", "Masked for unauthorised roles"),
("Data retention/deletion policy and backup/recovery plan", "16", "P1", "Restore drill"),
("Dev/prod configuration separation, no hardcoded secrets", "1", "P0", "Settings test; secrets scan"),
("PostgreSQL <-> Neo4j consistency strategy", "7", "P0", "Rebuild-equivalence test"),
("Reproducible model training with persisted artifacts/metadata", "5", "P0", "Re-run equals metrics"),
("OpenAPI documentation via drf-spectacular", "1", "P1", "Schema served"),
("Django Admin for internal administration", "2", "P2", "Admin registered for core models"),
])
D["Research"] = ("RQ", "Ph5, 7B, 9, 10", [
("RQ1 Hybrid framework vs individual algorithms", "5", "P0", "Reported with real metrics"),
("RQ2 Graph features vs transaction-only", "7B", "P0", "Paired comparison reported"),
("RQ3 Unsupervised detection of unlabeled patterns", "5", "P0", "Analysis reported"),
("RQ4 XAI communication effectiveness", "10", "P1", "Fidelity/stability reported"),
("RQ5 Combined risk scoring improves prioritisation", "9", "P0", "precision@k/workload reported"),
("RQ6 Performance under temporal change", "5", "P0", "Per-window metrics reported"),
])
D["Future scope"] = ("FUT", "after core", [
("Apache Kafka streaming", "-", "P2", "Deferred; ingestion interface ready"),
("Graph Neural Networks", "7B", "P2", "Gate decision D-012"),
("Temporal GNNs", "-", "P2", "Deferred"),
("Federated learning", "-", "P2", "Deferred"),
("Behavioral biometrics", "-", "P2", "Deferred"),
("Device fingerprint analysis", "-", "P2", "Deferred"),
("Privacy-preserving analysis", "-", "P2", "Deferred"),
("Concept drift detection", "-", "P2", "Deferred (RQ6 groundwork)"),
("Adaptive ML", "-", "P2", "Deferred"),
("LLM-assisted summaries", "-", "P2", "Deferred; D-016"),
("Multimodal transaction+document analysis", "-", "P2", "Deferred"),
("Advanced suspicious network discovery", "-", "P2", "Deferred"),
("Automated prioritisation with human approval", "-", "P2", "Deferred"),
])
# Honest status overrides (update when work lands)
OVERRIDE = {"PLAT-01": "In Progress", "PLAT-02": "In Progress", "PLAT-11": "Tested",
  "PLAT-04": "Tested", "PLAT-12": "Implemented", "FR-UI-01": "Implemented", "FR-UI-13": "Implemented", "FR-UI-14": "Implemented",
  "FR-ROLE-01": "In Progress", "FR-ROLE-04": "In Progress", "FR-ROLE-06": "In Progress"}
TESTS = {"PLAT-04": "tests/test_auth.py (login, lockout, throttle, rotation, blacklist, bcrypt)",
  "PLAT-12": "registered; not covered by tests", "FR-UI-01": "frontend auth.test.tsx (component tests only; no browser E2E yet)",
  "FR-UI-13": "no UI tests yet; backend users/roles tests pass", "FR-UI-14": "no UI tests yet; backend audit tests pass",
  "FR-ROLE-01": "tests/test_rbac_matrix.py (users/roles/audit only; settings/risk/model config pending later phases)",
  "FR-ROLE-04": "test_rbac_matrix.py (auditor has no write perms on current endpoints)",
  "FR-ROLE-06": "test_rbac_matrix.py (completeness + 5 roles x all current endpoints)","PLAT-11": "tests/test_infrastructure.py::test_openapi_schema_served", "PLAT-01": "test_ping_task_runs_eagerly + manual real-worker round trip (job-status API pending)", "PLAT-02": "test_websocket_echo (alerts/import events pending)"}

T = "tests/test_transactions.py"
OVERRIDE.update({
  "FR-M1-03": "Implemented", "FR-M1-05": "Tested", "FR-M1-06": "Tested", "FR-M1-07": "Tested", "FR-M1-08": "Implemented",
  "FR-M1-09": "Tested", "FR-M1-10": "Implemented", "FR-M1-11": "Tested", "FR-M1-12": "Tested", "FR-M1-13": "Tested",
  "FR-M1-14": "Tested", "FR-M1-15": "Tested", "FR-M1-23": "Tested", "FR-UI-03": "Implemented",
  "FR-M2-12": "In Progress", "FR-M2-13": "In Progress", "FR-M2-15": "In Progress",
})
TESTS.update({k: T for k in ["FR-M1-05","FR-M1-06","FR-M1-07","FR-M1-09","FR-M1-11","FR-M1-12","FR-M1-13","FR-M1-14","FR-M1-15","FR-M1-23"]})
TESTS.update({
  "FR-M1-03": "model/serializer tests; column-mapping import is Phase 4", "FR-M1-08": "stored as timestamptz; step-to-time mapping in Phase 4",
  "FR-M1-10": "no update/delete path in API; no dedicated test", "FR-UI-03": "pages/transactions.test.tsx (component tests; not browser-tested)",
  
})

OVERRIDE.update({
  "FR-M1-01": "Tested", "FR-M1-02": "Tested", "FR-M1-04": "Tested", "FR-M1-16": "Tested", "FR-M1-17": "Implemented",
  "FR-M1-18": "Tested", "FR-M1-19": "Tested", "FR-M1-20": "Tested", "FR-M1-21": "Tested", "FR-M1-22": "Implemented",
  "PLAT-05": "In Progress", "PLAT-01": "In Progress", "PLAT-02": "In Progress",
})
TESTS.update({k: "tests/test_imports.py (+ live 100k/1M run)" for k in ["FR-M1-01","FR-M1-04","FR-M1-18","FR-M1-19","FR-M1-20","FR-M1-21"]})
TESTS.update({
  "FR-M1-02": "tests/test_imports.py::test_excel_import_and_formulas_are_not_evaluated (small files only)",
  "FR-M1-16": "tests/test_imports.py::test_api_ingest_* (<=1000 records per call)",
  "FR-M1-17": "IngestionSource protocol; file + API sources implement it; no stream source built",
  "FR-M1-22": "API tested; UI pages component-tested only (ImportDetailPage), not browser-tested",
  "PLAT-05": "uploads validated (tests/test_imports.py); evidence storage still Phase 12",
  "PLAT-01": "imports run as Celery jobs with REST+WS status (tests + live); other job types pending",
  "PLAT-02": "tests/test_realtime.py (ticket auth, import progress); alerts/cases/dashboard events pending",
})
OVERRIDE.update({
  "FR-M2-07": "Tested", "FR-M2-08": "Tested", "FR-M2-11": "Tested", "FR-M2-12": "Tested", "FR-M2-13": "Tested",
  "FR-M2-14": "Tested", "FR-M2-15": "Tested", "FR-UI-04": "Implemented", "FR-UI-12": "Implemented", "PLAT-10": "Tested",
  "RQ-03": "In Progress",
})
TESTS.update({
  "FR-M2-07": "tests/test_ml_models.py, test_ml_features_eval.py (LR/RF/XGBoost on real PaySim+ULB; results in doc 08)",
  "FR-M2-08": "tests/test_ml_models.py (labels never used); results in doc 08 (IF/LOF/OCSVM/AE)",
  "FR-M2-11": "tests/test_detection.py (stored score equals research pipeline); raw model score, not a calibrated probability",
  "FR-M2-12": "tests/test_detection.py (Prediction rows per run/transaction)",
  "FR-M2-13": "tests/test_model_registry.py, test_detection.py (hash-verified artifact load)",
  "FR-M2-14": "tests/test_detection.py::test_predictions_endpoint_* (history across runs per transaction)",
  "FR-M2-15": "tests/test_model_registry.py; doc 08 results; offline metrics only (no drift tracking yet)",
  "FR-UI-04": "pages/detection.test.tsx (component tests; not browser-tested)",
  "FR-UI-12": "pages/detection.test.tsx (component tests; not browser-tested)",
  "PLAT-10": "tests/test_ml_features_eval.py (same seed => identical scores); artifact hashes in registry",
  "RQ-03": "unsupervised models evaluated (doc 08); overlap analysis with supervised alerts not done",
})

OVERRIDE.update({
  **{f"FR-M3-{i:02d}": "Tested" for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14)},
  "FR-M3-13": "Implemented", "FR-UI-05": "Implemented",
})
TESTS.update({
  "FR-M3-01": "tests/test_behavior_engine.py::test_profile_statistics_and_aggregates, test_behavior.py (profile API)",
  "FR-M3-02": "tests/test_behavior.py::test_trends_granularity_and_validation (daily)",
  "FR-M3-03": "tests/test_behavior_engine.py::test_aggregate_fills_gaps (weekly); trends API",
  "FR-M3-04": "tests/test_behavior_engine.py::test_aggregate_fills_gaps (monthly); trends API",
  "FR-M3-05": "tests/test_behavior_engine.py (robust median/MAD amount score; scenario)",
  "FR-M3-06": "tests/test_behavior_engine.py (weekly spend-jump component in the 5 x 40,000 scenario)",
  "FR-M3-07": "tests/test_behavior_engine.py::test_unusual_hour_is_detected_and_only_with_enough_history",
  "FR-M3-08": "tests/test_behavior_engine.py (distribution when present, null when absent); no real dataset has categories",
  "FR-M3-09": "burst + tx_per_day + recent_7d vs window (engine scenario test)",
  "FR-M3-10": "tests/test_behavior.py (as-of profile, stored snapshots)",
  "FR-M3-11": "tests/test_behavior_engine.py + test_behavior.py (scenario 77-84, cold start unavailable, batch == live)",
  "FR-M3-12": "tests/test_behavior.py (trends API); UI component-tested",
  "FR-M3-13": "UI table (last 7 days vs window); behavior.test.tsx; not browser-tested",
  "FR-M3-14": "tests/test_behavior.py (BehaviorAnalysisResult per run/transaction)",
  "FR-UI-05": "pages/behavior.test.tsx (component tests; not browser-tested)",
})

OVERRIDE.update({
  **{f"FR-M4-{i:02d}": "Tested" for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 15, 16)},
  "FR-M4-10": "Implemented", "FR-M4-14": "In Progress", "FR-UI-06": "Implemented",
})
TESTS.update({
  "FR-M4-01": "tests/test_graph.py (snapshot edge count equals PostgreSQL; real 343k-row slice built in ~41-69 s)",
  "FR-M4-02": "tests/test_graph.py, test_graph_lib.py (directed aggregated edges with count/amount/time)",
  "FR-M4-03": "tests/test_graph_lib.py::test_rapid_pass_through_chain_* (time-respecting, hop-limited)",
  "FR-M4-04": "tests/test_graph_lib.py, test_graph.py (planted 4-hop chain found and scored); none occur in the real PaySim slice",
  "FR-M4-05": "tests/test_graph_lib.py::test_time_ordered_cycle_*, test_graph.py (planted A1>A2>A3>A1); none in the real PaySim slice",
  "FR-M4-06": "tests/test_graph_lib.py (needs >=3 senders x >=2 payees, Poisson significance, merchants exempt), test_graph.py",
  "FR-M4-07": "tests/test_graph_lib.py (chain hop limit/retention); same detector as FR-M4-03",
  "FR-M4-08": "tests/test_graph_lib.py::test_metrics_* (degree, PageRank, clustering); stored per account",
  "FR-M4-09": "Louvain community id stored per account; dense_cluster finding (stars excluded); tests/test_graph_lib.py",
  "FR-M4-10": "pages/graph.test.tsx (React Flow mocked in jsdom: the diagram itself is not rendered in tests or a browser)",
  "FR-M4-11": "tests/test_graph.py (neighborhood API, caps reported)",
  "FR-M4-12": "tests/test_graph.py::test_neighborhood_depth_direction_and_amount_filters",
  "FR-M4-13": "tests/test_graph.py (edge detail API); UI panel component-tested",
  "FR-M4-14": "nodes carry graph risk score and finding flags; no ranked-neighbour list yet",
  "FR-M4-15": "tests/test_graph.py (timeline API); UI list component-tested",
  "FR-M4-16": "tests/test_graph.py (GraphFinding / AccountGraphMetrics persisted per snapshot)",
  "FR-UI-06": "pages/graph.test.tsx (component tests; not browser-tested)",
})

OVERRIDE.update({**{f"FR-M5-{i:02d}": "Tested" for i in (1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14)}, "FR-UI-08": "Implemented"})
TESTS.update({
  "FR-M5-01": "tests/test_duplicate_transactions.py (same id in two datasets; rows flagged at import). Within one dataset the unique constraint already prevents duplicates",
  "FR-M5-02": "tests/test_duplicates_lib.py, test_duplicate_transactions.py (strong <=1 h, potential <=24 h, regular series = legitimate repeat); real PaySim slice: 0 candidates",
  "FR-M5-03": "tests/test_duplicates_lib.py, test_invoices.py (normalised number match, 1-char OCR slip)",
  "FR-M5-04": "tests/test_duplicates_lib.py (equal / within 1%, relative difference in evidence)",
  "FR-M5-05": "tests/test_duplicates_lib.py (rapidfuzz token-set ratio on normalised vendor)",
  "FR-M5-06": "tests/test_duplicates_lib.py (days apart, billing-interval recognition)",
  "FR-M5-07": "tests/test_invoices.py (real Tesseract on PNG/JPEG/PDF; 40/40 fields on the clean synthetic set; degradation table in doc 08); synthetic invoices only",
  "FR-M5-08": "tests/test_duplicates_lib.py, test_invoices.py (pHash Hamming distance as supporting evidence; synthetic set only)",
  "FR-M5-10": "tests/test_invoices.py (PDF generated with records, evidence, review status); layout not visually verified",
  "FR-M5-11": "tests/test_invoices.py, test_duplicate_transactions.py (exact class)",
  "FR-M5-12": "tests/test_invoices.py (strong/potential/legitimate classes; 10/10 expected pairs on the synthetic set)",
  "FR-M5-13": "score 0-100 stored with evidence; missing signals not counted as 0 (tests/test_duplicates_lib.py); documented as non-proof",
  "FR-M5-14": "tests/test_invoices.py (nothing auto-confirmed; review needs duplicates.review; audited; decisions survive rescans)",
  "FR-UI-08": "pages/duplicates.test.tsx (component tests; not browser-tested)",
})

OVERRIDE.update({**{f"FR-M7-{i:02d}": "Tested" for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12)}, "FR-M7-11": "Implemented", "FR-UI-07": "Implemented", "RQ-05": "In Progress"})
TESTS.update({
  "FR-M7-01": "tests/test_risk.py, test_risk_engine_lib.py (A,B,G,F,D,H each 0-100 or unavailable with a reason); F and H are this project's definitions (D-067)",
  "FR-M7-02": "tests/test_risk_engine_lib.py (documented formula; renormalised weighted mean)",
  "FR-M7-03": "tests/test_risk_engine_lib.py::test_category_boundaries_*, configurable thresholds",
  "FR-M7-04": "tests/test_risk.py (assessments append-only: DB trigger blocks UPDATE/DELETE; AccountRiskHistory for Medium+)",
  "FR-M7-05": "tests/test_risk.py (per-component weight and contribution; contributions sum to the score)",
  "FR-M7-06": "tests/test_risk.py (versioned RiskConfig; weights validated; used versions immutable; activation audited)",
  "FR-M7-07": "tests/test_risk_engine_lib.py, test_risk.py (ordering and range validated)",
  "FR-M7-08": "tests/test_risk_engine_lib.py (all 64 availability combinations x 3 policies), test_risk.py (coverage, low-coverage cap)",
  "FR-M7-09": "algorithm_version stored on every assessment (tests/test_risk.py)",
  "FR-M7-10": "transaction and sender account FKs; GET /transactions/{id}/risk/, /accounts/{id}/risk/history/",
  "FR-M7-11": "pages/risk.test.tsx (breakdown table, coverage, unavailable reasons); not browser-tested",
  "FR-M7-12": "tests/test_risk.py (compare API; flags non-comparable config/algorithm versions)",
  "FR-UI-07": "pages/risk.test.tsx (component tests; not browser-tested)",
  "RQ-05": "calibration experiment executed on a real PaySim slice: combined score NOT better than the single model score (doc 08); hybrid RQ1 untested",
})

OVERRIDE.update({**{f"FR-M8-{i:02d}": "Tested" for i in (1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12)}, "FR-M8-04": "Implemented", "RQ-04": "In Progress"})
TESTS.update({
  "FR-M8-01": "tests/test_explain.py::test_global_feature_importance_* (mean |SHAP| + intrinsic importance, per model version)",
  "FR-M8-02": "tests/test_explain_lib.py (additivity for XGBoost/RF/logistic regression), test_explain.py (contributions reproduce the stored score)",
  "FR-M8-03": "tests/test_explain_lib.py, test_explain.py (seeded, reproducible; instability documented and measured in doc 08)",
  "FR-M8-04": "pages/explain.test.tsx (contribution bars with printed values); not browser-tested",
  "FR-M8-05": "tests/test_explain.py (deterministic behavioural narrative; cold start stated)",
  "FR-M8-06": "tests/test_explain.py (graph patterns completed by the transaction's time, in plain language)",
  "FR-M8-07": "tests/test_explain.py (risk breakdown narrative with contributions and excluded signals)",
  "FR-M8-08": "tests/test_explain.py (timeline in the summary: this transaction + sender's recent + related transactions)",
  "FR-M8-09": "tests/test_explain_lib.py, test_explain.py (template summary with five fixed sections; no language model)",
  "FR-M8-10": "tests/test_explain.py (PDF with versions, disclaimer and stale warning, text checked); layout not visually inspected",
  "FR-M8-11": "tests/test_explain.py (Explanation rows with payload, narrative, generator version)",
  "FR-M8-12": "tests/test_explain.py (DB CHECK + version-mismatch error + staleness when the same model is re-run or risk/graph are superseded)",
  "RQ-04": "SHAP/LIME stability and fidelity measured on real PaySim (doc 08); the structured usability review of explanations was NOT done",
})

OVERRIDE.update({**{f"FR-M6-{i:02d}": "Tested" for i in range(1, 13)}, "FR-M5-09": "Tested", "FR-UI-09": "Implemented"})
TESTS.update({
  "FR-M6-01": "tests/test_alerts.py (high_risk alerts from the latest risk run, severity from category)",
  "FR-M6-02": "tests/test_alerts.py::test_a_burst_is_one_alert_per_bucket_* (once per bucket; severity rises in place)",
  "FR-M6-03": "tests/test_alerts.py (unusual_activity from behavioural deviation)",
  "FR-M6-04": "tests/test_alerts.py::test_rapid_fund_movement_and_suspicious_beneficiary_* (shared-beneficiary / fan-in findings)",
  "FR-M6-05": "tests/test_alerts.py::test_high_value_and_failed_transaction_rules (evaluated only when failed-status data exists)",
  "FR-M6-06": "tests/test_alerts.py (configurable threshold; severity by multiple)",
  "FR-M6-07": "tests/test_alerts.py (graph chain findings)",
  "FR-M6-08": "tests/test_alerts.py (spend-jump behaviour change; a sudden weekly spend shift, not a full profile comparison)",
  "FR-M6-09": "tests/test_alerts.py (console/locmem backend, a real SMTP wire test against a local test server, failure logged); no live external SMTP service tried",
  "FR-M6-10": "tests/test_alerts.py (AlertEvent append-only trigger; lifecycle events; NotificationLog)",
  "FR-M6-11": "tests/test_alerts.py (status/severity/type/assignee/category/date filters); pages/alerts.test.tsx",
  "FR-M6-12": "tests/test_alerts.py (open before closed, then severity, risk score, newest; per-rule cap)",
  "FR-M5-09": "tests/test_alerts.py (duplicate_record alerts for exact/strong candidates not dismissed by a reviewer)",
  "FR-UI-09": "pages/alerts.test.tsx (queue, filters, lifecycle actions, live toast; component tests only, not browser-tested)",
})

out = ["# 18 — Requirements Traceability Matrix", "",
"Generated by `docs/tools/build_traceability.py`. Statuses: Not Started · Planned · In Progress · Implemented · Tested · Verified · Blocked · Deferred. A requirement is **Verified** only when behavior is implemented and tests actually executed (Definition of Done, Part 12). Priority: P0 = MVP, P1 = core, P2 = advanced/optional.", "",
"Source numbering follows the master prompt module lists, in order (e.g., FR-M1-05 = Module 1 item 5). Extra rows (rules stated in prose, e.g. validated transitions) are appended at the end of each module.", ""]
total = 0
for mod, (pref, deps, rows) in D.items():
    out += [f"## {mod}", "", "| ID | Requirement | Prio | Phase | Dependencies | Acceptance criteria | Status | Tests |", "|---|---|---|---|---|---|---|---|"]
    for i, (t, ph, pr, ac) in enumerate(rows, 1):
        st = "Deferred" if pref == "FUT" else OVERRIDE.get(f"{pref}-{i:02d}", "Planned")
        out.append(f"| {pref}-{i:02d} | {t} | {pr} | {ph} | {deps} | {ac} | {st} | {TESTS.get(f"{pref}-{i:02d}", "TBD")} |")
        total += 1
    out.append("")
out.insert(4, f"Total rows: **{total}**.\n")
Path(__file__).resolve().parent.parent.joinpath("18-REQUIREMENTS-TRACEABILITY.md").write_text("\n".join(out))
print(total)
