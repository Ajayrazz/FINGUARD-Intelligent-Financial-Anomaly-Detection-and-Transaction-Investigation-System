"""Report content, part B: section 3.1 and 3.2 (interfaces and functional requirements)."""

B = []


def add(*blocks):
    B.extend(blocks)


def feature(num, title, priority, intro, inputs, processing, outputs, errors, extra=()):
    """One functional requirement in the template's five-part layout."""
    add(
        ("h", 3, f"3.2.{num} {title}"),
        ("h", 4, f"3.2.{num}.1 Introduction"),
        ("p", f"**Priority:** {priority}.  " + intro),
        *extra,
        ("h", 4, f"3.2.{num}.2 Inputs"),
        ("bul", inputs),
        ("h", 4, f"3.2.{num}.3 Processing"),
        ("bul", processing),
        ("h", 4, f"3.2.{num}.4 Outputs"),
        ("bul", outputs),
        ("h", 4, f"3.2.{num}.5 Error Handling"),
        ("bul", errors),
    )


S = "screens/"

add(
    ("h", 1, "3. Specific Requirements"),
    ("p", "This section holds the requirements that guide design, implementation and testing. Each requirement is uniquely identified by its section number, is written to be verifiable, and was checked against the implementation. The word \"shall\" marks a requirement. Priority is High (the system is not useful without it), Medium or Low."),
    ("h", 2, "3.1 External Interface Requirements"),
    ("h", 3, "3.1.1 User Interfaces"),
    ("p", "The user interface is a React 19 single-page application (TypeScript in strict mode, Tailwind CSS 4) with a dark theme, a top navigation bar grouped as Dashboard, Analytics, Data, Detect, Respond and Govern, and an animated footer. Charts use Apache ECharts; 3D charts use ECharts-GL; the relationship network uses React Flow. Lists can be shown as cards or as a table. The requirements for the interface are:"),
    ("bul", [
        "The interface shall show a public landing page, a sign-in page and the account pages (register, confirm e-mail, forgot password, reset password) to visitors, and every other page only to signed-in users.",
        "A page or a navigation item shall be shown only when the user's role holds the permission needed to use it; the server enforces the same permission independently.",
        "Every page shall have loading, empty and error states, a skip-to-content link and a unique page title, and shall work with the keyboard.",
        "Pages shall be usable from 360 px to desktop width without horizontal scrolling and shall pass an automated WCAG 2.1 A/AA scan (axe) on every page.",
        "Scores and flags shall be labelled as automated indicators for prioritising review, not as proof of wrongdoing.",
    ]),
    ("fig", S + "01-landing.png", "Figure 3.1  Public landing page (animated background and 3D feature cards)", 6.0),
    ("fig", S + "02-login.png", "Figure 3.2  Sign-in page with links to password recovery and self-registration", 6.0),
    ("fig", S + "03-register.png", "Figure 3.3  Self-registration page", 6.0),
    ("fig", S + "05-dashboard.png", "Figure 3.4  Dashboard with the animated 3D carousel and live system status (database and Redis)", 6.0),
    ("h", 3, "3.1.2 Hardware Interfaces"),
    ("p", "FinGuard has no direct hardware interface. It runs on any x86-64 or ARM64 host that can run Docker. Development and testing used an Apple-silicon laptop with Docker Desktop; the production image was rehearsed on arm64. A production host should have at least 4 GB of RAM (the machine-learning libraries are large), 2 CPU cores and 40 GB of disk. A GPU is not required: PyTorch is installed in its CPU build."),
    ("h", 3, "3.1.3 Software Interfaces"),
    ("table", "Table 3.1  Software interfaces and components", ["Component", "Version / library", "Role"], [
        ["Python / Django", "Python 3.12, Django 5.2, Django REST Framework 3.16", "Backend, REST API, admin, ORM"],
        ["Authentication", "djangorestframework-simplejwt 5.5, bcrypt", "JWT access and rotating refresh tokens; password hashing"],
        ["API documentation", "drf-spectacular 0.28", "OpenAPI schema and Swagger UI at /api/docs/"],
        ["ASGI server / realtime", "Daphne 4, Channels 4, channels-redis", "HTTP and WebSocket serving"],
        ["Task queue", "Celery 5.5 with Redis 7", "Background jobs and scheduled rollup (beat)"],
        ["Database", "PostgreSQL 16 (psycopg 3)", "System of record, 46 models"],
        ["Graph database (optional)", "Neo4j 5 Community, neo4j driver 5.26", "Rebuildable projection for graph traversal"],
        ["Machine learning", "scikit-learn 1.6, XGBoost 2.1, PyTorch 2.5 (CPU), pandas 2.2, SciPy, PyArrow", "Models, features, evaluation"],
        ["Explainability", "SHAP 0.46, LIME 0.2", "Feature attributions"],
        ["Graph analytics", "NetworkX 3.4", "Cycles, chains, PageRank, Louvain communities"],
        ["Documents and OCR", "pytesseract (Tesseract), Pillow, pypdfium2, rapidfuzz, imagehash, ReportLab", "Invoice OCR, matching, PDF reports"],
        ["Spreadsheet", "openpyxl 3.1", "XLSX import (formulas are not evaluated)"],
        ["Frontend", "React 19, Vite 8, TypeScript 7 (strict), Tailwind 4, TanStack Query 5, React Router 7, React Hook Form 7 + Zod 4", "Single-page application"],
        ["Charts / graph", "ECharts 5, ECharts-GL 2, React Flow (@xyflow/react 13)", "Charts, 3D charts, relationship network"],
        ["Testing", "pytest-django, Vitest 5 + Testing Library, Playwright, axe", "Unit, integration and browser tests"],
        ["Production edge", "Caddy 2", "Automatic HTTPS, security headers, static files"],
    ], [20, 44, 36]),
    ("h", 3, "3.1.4 Communications Interfaces"),
    ("bul", [
        "**REST over HTTPS:** all application traffic uses JSON under /api/v1, described by an OpenAPI schema. Errors share one envelope: `{error: {code, message, details}}`.",
        "**WebSocket (WSS):** pushes alert, import-progress and case-assignment events. A short-lived, single-use ticket obtained from /api/v1/ws/ticket/ authenticates the connection, so tokens never appear in a URL.",
        "**Authentication transport:** the 15-minute access token is sent as a Bearer header and kept only in browser memory; the 8-hour refresh token lives in an httpOnly, SameSite=Strict cookie scoped to /api/v1/auth/ and is rotated on every use.",
        "**SMTP:** verification, reset, approval and alert e-mails are sent by the Celery worker (STARTTLS on port 587 in the tested configuration).",
        "**Bolt:** the optional Neo4j projection is synchronised one way from PostgreSQL.",
        "**Health:** /api/v1/health/ (liveness) and /api/v1/health/ready/ (database and Redis readiness).",
    ]),
    ("h", 2, "3.2 Functional Requirements"),
    ("p", "The fourteen features below are specified in the template's layout: introduction, inputs, processing, outputs and error handling. Screenshots were taken from the running application with public PaySim data and synthetic demonstration data."),
)

feature(1, "Account Registration, Sign-in and Approval", "High",
    "Lets a new person request an account and lets an administrator control who gets in. A registered account has **no permissions** until its e-mail is confirmed and a Super Admin approves it with a role.",
    [
        "Registration: e-mail, full name, password (at least 12 characters), acceptance of the terms.",
        "E-mail confirmation: the signed token from the link in the confirmation e-mail.",
        "Sign-in: e-mail and password. Password reset: e-mail, then uid, token and a new password.",
        "Administrator: a role chosen from the assignable roles (the holding role cannot be chosen) to approve, or a rejection.",
    ],
    [
        "The system shall create a self-registered user with the holding role `pending_user`, approval state `pending` and no verified e-mail, and queue a confirmation e-mail after the database transaction commits.",
        "The confirmation link shall be signed, shall expire after 24 hours, and shall notify the Super Admins by e-mail when used.",
        "Registration, resend-confirmation and password-reset requests shall answer identically whether or not the address exists (generic 202 response), to prevent account enumeration.",
        "Sign-in shall reveal \"e-mail not confirmed\" or \"approval pending\" (HTTP 403) only after the correct password; a rejected account receives the generic 401.",
        "After 5 failed sign-ins an account shall be locked for 15 minutes; sign-in is throttled to 10 per minute, registration and reset to 5 per hour.",
        "Password reset shall use a single-use token valid for one hour and shall revoke all refresh tokens of the user.",
        "Passwords shall be at least 12 characters, not common, not numeric only and not similar to the user's attributes, and shall be stored with bcrypt-SHA256.",
        "A Super Admin shall approve (with a role, only after the e-mail is confirmed) or reject a registration; both actions are audited and the user is e-mailed on approval.",
        "Users created by an administrator or migrated from before this feature shall be verified and approved automatically, so nobody is locked out.",
    ],
    [
        "202 with a generic message for registration, resend and reset requests; 200 with an access token and user object on sign-in; 204 after a completed reset.",
        "A \"Waiting for approval\" panel on the User Management page; approval and registration e-mails.",
        "Audit entries `user.registered`, `user.email_verified`, `user.approved`, `user.rejected`, `auth.password_reset_requested`, `auth.password_reset_completed`.",
    ],
    [
        "400 `invalid_token` for an expired or tampered link; 400 with per-field messages for weak or mismatched passwords (shown under the password field).",
        "401 generic message for a wrong password or a rejected account; 403 `email_not_verified` / `pending_approval`; a lockout message after repeated failures; 429 when throttled.",
        "If the mail server is unavailable the failure is logged and the API response is unchanged; the user can request a new e-mail.",
    ],
    extra=[("fig", S + "04-forgot-password.png", "Figure 3.5  Forgot-password request page (sign-in and registration are shown in Figures 3.2 and 3.3)", 5.2)],
)

feature(2, "Roles, Permissions and User Administration", "High",
    "Controls what each user may see and do. Permissions are `resource.action` codenames (54 in total) grouped into roles that a Super Admin can edit.",
    [
        "A request from a signed-in user carrying a Bearer access token.",
        "Administrator input: user details, role assignment, activation state, role permission sets.",
    ],
    [
        "The system shall deny by default: every view declares the permissions it needs, and an automated test fails if any route lacks a declaration.",
        "A generated matrix test shall check the allowed and forbidden outcome for every endpoint and each of the five roles.",
        "An unauthorised role shall receive 403 even for identifiers that do not exist (no existence oracle).",
        "Super Admins shall create, update, activate, deactivate users and reset passwords; deactivation shall revoke refresh tokens.",
        "Role permission edits shall take effect without a code change; permissions edited by an administrator shall not be overwritten when new permissions are added later.",
        "Mass assignment shall be ignored: a client cannot set its own role, status or privilege fields.",
    ],
    [
        "User and role lists (cards or table), per-role permission sets, a permission catalogue.",
        "Audit entries for every user, role and permission change.",
    ],
    [
        "403 with a clear message when a permission is missing; 400 when an administrator submits an invalid change.",
        "A role that is not assignable (the holding role) is rejected by the approval form.",
    ],
    extra=[("fig", S + "21-users.png", "Figure 3.6  User management (cards view; mailbox addresses replaced by example.com for privacy)", 6.0)],
)

feature(3, "Dataset Import", "High",
    "Loads transaction files into a dataset through a guided, validated, resumable background job. This is the entry point for all data.",
    [
        "A CSV file (up to 2 GB) or an XLSX file, a dataset name, and a column mapping.",
        "The mapping comes from, in order: explicit JSON, a saved mapping profile, a preset (for example `paysim`) or automatic suggestion.",
        "A duplicate-ID policy for the job: `reject` (default), `skip` or `flag`.",
        "Alternatively a JSON batch posted to the ingestion API (`POST /transactions/ingest/`, permission `transactions.ingest`).",
    ],
    [
        "The system shall store the upload under a random name, record its SHA-256 and never use the client's file name for storage.",
        "A preview step shall show the detected header, a sample and the mapping before anything is imported.",
        "Only a transaction id (generated when absent), a sender, a receiver or merchant, an amount and a time reference are mandatory; other columns are stored as optional fields or metadata.",
        "The job shall run in Celery in chunks, with statuses pending, validating, running, completed, completed with errors, failed and cancelled; it shall be cancellable and resumable from the last committed chunk.",
        "Each rejected row shall be stored with an error code and message and the job shall continue; accepted plus rejected shall equal the total.",
        "Amounts shall be stored as exact decimals (negatives rejected); times as UTC timestamps; accounts shall be created per dataset.",
        "Excel formulas shall not be evaluated, and values that start with a formula character shall be neutralised in exported error reports.",
        "Progress shall be pushed over WebSocket and shown live; every import shall be listed in the import history with user, hash and counts.",
    ],
    [
        "A dataset with accounts and transactions, an import job record, a downloadable error report (CSV), a progress bar and an import history list.",
        "Measured: about 12,000 rows per second at one million rows; a real 343,027-row PaySim slice was imported and scored through the same pipeline.",
    ],
    [
        "Unsupported type, oversize file or unreadable encoding: 400 with a message before any row is read.",
        "Missing mandatory mapping: 400 listing the unmapped fields. Malformed row: recorded as a row error, job status \"completed with errors\".",
        "Worker crash or restart: the job can be resumed from its last committed chunk; a cancelled job keeps the rows already committed.",
    ],
    extra=[("fig", S + "10-import-wizard.png", "Figure 3.7  Import wizard (upload, mapping preview, duplicate policy)", 6.0)],
)

feature(4, "Transaction Monitoring", "High",
    "Lets users search, filter, sort and open transactions and accounts and, with permission, change a monitoring status.",
    [
        "Filters: dataset, type, status, amount range, date range, risk score, account and free-text search; sort by amount, time or risk; page cursor.",
        "A transaction or account identifier for the detail pages.",
    ],
    [
        "The system shall page results with a hard cap of 100 rows per page and use database indexes for the search and sort paths.",
        "The transaction detail shall show the sender and receiver with balances where present and the risk assessment with all six components; predictions, alerts and explanations are available per transaction through the API.",
        "A status change (pending, completed, failed, reversed) shall be validated and audited; transaction records shall never be overwritten (a re-import creates a new job).",
        "Search strings shall be handled by the ORM only, so SQL-injection attempts are inert.",
    ],
    [
        "Lists as cards or tables with 3D summaries, detail pages, an account page with links to behaviour and relationship graph.",
        "Measured on 363,508 transactions: list p95 5-9 ms, detail 2 ms, deep page 5,000 about 170 ms.",
    ],
    [
        "404 for an unknown transaction (after a permission check), 400 for an invalid filter or status transition, 403 without `transactions.read`.",
    ],
    extra=[("fig", S + "07-transactions.png", "Figure 3.8  Transaction list", 6.0), ("fig", S + "08-transaction-detail.png", "Figure 3.9  Transaction detail with the risk assessment and signal coverage (PaySim slice)", 6.0)],
)

feature(5, "Anomaly Detection and Model Registry", "High",
    "Scores transactions with machine-learning models and records every model version so that any score can be reproduced.",
    [
        "A dataset and a registered model version (and optionally an alert threshold override).",
        "Offline training inputs: the prepared PaySim and ULB splits (chronological train, validation, test).",
    ],
    [
        "The system shall provide seven model families: logistic regression, random forest and XGBoost (supervised); Isolation Forest, Local Outlier Factor, one-class SVM and an autoencoder (unsupervised, labels never used in fitting).",
        "Features shall use only the row itself and strictly earlier history (no leakage); `step`, labels and identifiers shall never be features; scaling shall be fitted on the training split only.",
        "A detection run shall rebuild the training features from stored transactions with the same function, verify the model artifact's SHA-256, and store one prediction (score, label) per transaction linked to run and model version.",
        "A model version shall record algorithm, hyper-parameters, feature schema, seed, split strategy, data hash, library versions and offline evaluation metrics (PR-AUC primary, ROC-AUC, recall at fixed false-positive rates, bootstrap intervals).",
        "Models trained on the ULB set need PCA components that platform data does not have; the API shall refuse to run them with a clear error.",
        "Single-transaction and batch inference latency shall be measured and shown with each model version.",
    ],
    [
        "Detection runs and predictions, a model performance page (3D chart of PR-AUC by algorithm and data set) and per-version evaluation cards.",
        "Platform check: PR-AUC of the platform scoring equals the research code's value on the same rows (0.2109 both ways).",
    ],
    [
        "400 when the model cannot be applied to the dataset; a failed run keeps its status and error message; an artifact whose hash differs from the registry is refused.",
    ],
    extra=[("fig", S + "11-detection.png", "Figure 3.10  Anomaly detection runs", 6.0), ("fig", S + "12-model-performance.png", "Figure 3.11  Model performance (offline results; 3D chart of PR-AUC)", 6.0)],
)

feature(6, "Behavioural Analysis", "Medium",
    "Compares each transaction with the sender's own history to find unusual spending.",
    ["A dataset; for the profile page an account, a direction (outgoing or incoming) and a window (days)."],
    [
        "History for a transaction shall be everything strictly before it, within 90 days and at most the latest 500 transactions (no future data).",
        "Five components shall be computed, each scored 0-100: amount (robust z-score with median and MAD, upward only), burst (transactions in the last 10 minutes), spend jump (last 7 days versus the weekly average), new counterparty (receiver never paid before) and hour of day (rarity of the UTC hour).",
        "The overall deviation shall be 0.5 times the maximum plus 0.5 times the weighted mean (weights 0.30, 0.25, 0.20, 0.15, 0.10) of the available components.",
        "An account with fewer than 5 earlier transactions shall be reported as unavailable (cold start) with the reason for each component, never as a score of 0.",
        "Profiles (mean, median, 95th percentile, per-day rate, counterparties) and daily, weekly and monthly trends shall be stored and returned.",
    ],
    [
        "A behaviour run, per-transaction results with components and coverage, an account profile page with current versus historical figures, trend and time-of-day charts.",
        "Scenario test: five payments of 40,000 within ten minutes after 60 days of payments of about 800 scored 77-84 (the regular customer's maximum was 31).",
    ],
    [
        "Cold-start accounts return an \"unavailable\" status; a window with no transactions shows an empty-state message; an invalid granularity is rejected with 400.",
    ],
    extra=[("fig", S + "13-account-behavior.png", "Figure 3.12  Account behaviour profile (synthetic demonstration account)", 6.0)],
)

feature(7, "Graph Relationship Analysis", "Medium",
    "Finds suspicious structure in who pays whom and lets users explore an account's network.",
    ["A dataset (optionally an as-of time); for exploration an account, depth, direction, minimum amount and data source."],
    [
        "The system shall build a directed graph of accounts per dataset snapshot using only transactions up to the snapshot time.",
        "It shall detect, with bounded search budgets: cycles of 2-5 accounts within 7 days; rapid pass-through chains (forwarded within an hour, at least 80 % retained, at least 3 hops); fan-in and fan-out of at least 5 counterparties within 24 hours; shared beneficiaries that are improbable by chance; and dense clusters (Louvain communities of 5-200 accounts with density and clustering of at least 0.5).",
        "It shall compute per-account in- and out-degree, weighted degree, PageRank, clustering and community.",
        "The per-account graph score G shall be 0.5 times the best finding score plus 0.5 times the weighted mean of five component scores (cycle 0.25, chain 0.25, fan 0.20, shared 0.15, cluster 0.15).",
        "Neighbourhood queries shall run on PostgreSQL by default and on Neo4j when selected; the Neo4j projection shall be one-way, idempotent and rebuildable.",
    ],
    [
        "Graph snapshots, findings with evidence and transaction ids, account metrics, an interactive relationship network (React Flow), an edge detail and a timeline.",
        "Planted cycles, chains, fan-in and shared beneficiaries were all found in a synthetic dataset; on the real PaySim slice 84 fan-in patterns were found and no cycles or chains.",
    ],
    [
        "A search that hits its budget reports `truncated`; neighbourhoods are capped; an unreachable Neo4j falls back to PostgreSQL; an unknown account returns 404.",
    ],
    extra=[("fig", S + "14-graph-overview.png", "Figure 3.13  Graph analysis overview", 6.0), ("fig", S + "15-relationship-graph.png", "Figure 3.14  Relationship network of a fan-in account (PaySim slice; flags mark accounts in a detected pattern)", 6.0)],
)

feature(8, "Duplicate Invoice and Transaction Detection", "Medium",
    "Finds repeated payments and duplicate invoices and requires a person to confirm each candidate.",
    ["Invoice files (PDF, PNG or JPEG, up to 10 MB), or a transaction dataset to scan, and review decisions."],
    [
        "Uploads shall be validated by content (magic bytes), size, decodability, at most 40 megapixels and at most 5 PDF pages.",
        "OCR shall run Tesseract after grayscale, autocontrast and upscaling; vendor, invoice number, date and total shall be extracted with the confidence of their line, and a person may verify or correct each field.",
        "Pair similarity shall be a weighted score over the available signals (number 0.35, vendor 0.20, amount 0.25, date 0.10, image hash 0.10).",
        "Each candidate shall be classed exact, strong similar, potential or legitimate repeat (regular billing intervals), with the evidence stored; templated invoices alone shall not be duplicates.",
        "Repeated payments (same sender, receiver, amount and type within an hour or a day) and identical transaction ids across datasets shall be reported.",
        "Nothing shall be confirmed automatically; a recorded review decision is the only determination and is audited.",
    ],
    [
        "Invoices, candidates (cards and a 3D summary by class and review state), evidence, a PDF report and alerts for strong candidates.",
        "On a synthetic invoice set: 40/40 fields extracted and 10/10 pair outcomes correct when clean; accuracy falls under heavy rotation or noise (Appendix A.3).",
    ],
    [
        "400 for an invalid or oversize file; an unreadable image yields fields marked not found rather than guesses; a missing OCR engine fails the test suite.",
    ],
    extra=[("fig", S + "16-duplicates.png", "Figure 3.15  Duplicate detection candidates", 6.0)],
)

feature(9, "Risk Scoring", "High",
    "Combines the available signals into one explainable 0-100 score per transaction, with an honest statement of how much of the evidence was available.",
    ["A dataset, a risk configuration (weights, thresholds, missing-signal policy, minimum coverage) and the latest detection run, behaviour run, graph snapshot and duplicate scan."],
    [
        "The score shall be R = sum(w_i x S_i) / sum(w_i) over the available components A (model anomaly), B (behaviour), G (graph), F (frequency), D (duplicate) and H (history); default weights 0.25, 0.20, 0.20, 0.15, 0.10, 0.10.",
        "Categories shall be Low below 30, Medium from 30, High from 60 and Critical from 80 (configurable and validated).",
        "An unavailable component shall never be treated as zero. Three policies shall be supported: renormalize (default), neutral prior and strict; the share of weight that was available (coverage) shall be stored.",
        "A signal shall only count if it was available at the transaction's time (a graph pattern only after it completed).",
        "Every assessment shall store components, weights, contributions, coverage, configuration version and algorithm version, so it can be recomputed.",
        "Configurations shall be versioned; only a user with `risk.configure` may create or activate one.",
    ],
    [
        "Risk runs and assessments, a risk analysis page with configuration cards and weight bars, a per-transaction breakdown table and a comparison of two assessments.",
        "On the real PaySim slice (343,027 transactions) scoring took 44 s; coverage was 55-65 % because sender history was unavailable for every account.",
    ],
    [
        "A transaction with coverage below the minimum receives no score and a stated reason; an invalid configuration (weights not summing to 1, thresholds out of order) is rejected with 400.",
    ],
    extra=[("fig", "fig_risk.png", "Figure 3.16  Risk scoring model", 6.4), ("fig", S + "17-risk-analysis.png", "Figure 3.17  Risk analysis page with configuration versions", 6.0)],
)

feature(10, "Explainable AI Reports", "High",
    "Explains why a transaction was scored as it was, and keeps the explanation tied to the exact model version that produced it.",
    ["A transaction (or prediction) and the methods requested: SHAP, LIME, behavioural, graph, risk breakdown, investigation summary."],
    [
        "SHAP shall be exact for tree models and linear models; its additivity (base value plus contributions equals the model output) shall be tested.",
        "LIME shall work for any model with a seeded local surrogate and a stored note that it is random; it is the only method for the unsupervised models.",
        "Before explaining, the stored prediction shall be recomputed from rebuilt features and must match; otherwise the method is skipped with an explanation.",
        "Behavioural, graph and risk explanations shall be deterministic narratives over stored components; the investigation summary shall have the five fixed sections Prediction, Indicator, Evidence, Assessment and Outcome.",
        "An explanation shall be marked stale when the same model version has been re-run or a newer risk or graph result exists; the PDF report repeats versions and the disclaimer that contributions are not causation.",
        "Global feature importance (mean absolute SHAP over 1,000 sampled transactions plus intrinsic importance) shall be available per model version.",
    ],
    [
        "Stored explanations with narratives, charts of contributions, a PDF report per transaction.",
        "Measured: SHAP additivity error 8e-7; SHAP faithful by the deletion test; LIME top-3 features overlap between seeds only 0.68-0.75.",
    ],
    [
        "Generation runs as a job; a model that cannot be reproduced yields a skipped method with a reason; all user and imported text in PDFs is XML-escaped (a markup-injection defect found in testing was fixed).",
    ],
)

feature(11, "Alerts and Notifications", "High",
    "Turns signals into a prioritised, deduplicated queue of alerts that people can acknowledge, assign, escalate and close.",
    ["A dataset to evaluate (manually or automatically after a risk run) and an active alert policy."],
    [
        "Nine rules shall read stored results of the other engines: high risk, multiple transactions (burst), unusual activity, behaviour change, suspicious beneficiary, rapid fund movement, failed transactions, high value and duplicate record.",
        "Each alert shall carry a `dedup_key` (type, subject and, for bursts, a 24-hour bucket); a repeat shall not create a second alert, and the same event at a higher severity shall raise the open alert in place.",
        "Evidence shall be snapshotted when the alert is created; a cap of 500 alerts per rule shall keep only the highest-priority candidates and report the rest as suppressed.",
        "Status shall move new, acknowledged, escalated, closed; closing needs an outcome. Escalation needs a reason. Assignment is limited to eligible users.",
        "E-mail at or above a configured severity and live WebSocket notification shall be sent; an alert at or above the policy severity may open a case automatically.",
        "Alert policies shall be versioned and only `alerts.configure` users may activate one.",
    ],
    [
        "An alert queue (cards or table) sorted by status, severity, risk and time, with counts by severity, filters and a rule-evaluation action.",
        "Real-data note: the default high-value rule produced 8,225 alerts on the PaySim slice before the cap was added.",
    ],
    [
        "An invalid policy is rejected with 400; an invalid transition is rejected with 409; a notification failure does not stop the alert action itself.",
    ],
    extra=[("fig", S + "18-alerts.png", "Figure 3.18  Alert queue with severity counts", 6.0)],
)

feature(12, "Investigation Case Management", "High",
    "Gives investigators a structured workflow from alert to outcome with notes, evidence and a complete, tamper-resistant history.",
    ["Cases created from alerts or by hand; transitions, assignments, notes, evidence files (PDF, PNG, JPEG or text up to 20 MB), an outcome and a summary."],
    [
        "A case reference of the form FG-YYYY-NNNNNN shall be drawn from a database sequence.",
        "Status shall follow the validated machine new, under review, investigation, escalated, resolved, closed (Figure 4.9); every other change, including staying in the same status, shall be rejected with 409.",
        "Each status change needs the matching permission (for example escalate, resolve, close) and writes an immutable case event.",
        "The outcome (confirmed suspicious, false positive, inconclusive, referred) shall be chosen by a person with a written summary; closing a case closes its linked alerts with the matching outcome.",
        "Notes shall keep revisions and be editable only by their author and never on a closed case; evidence shall be validated by content, stored under a random name, hashed, and re-hashed on every download.",
        "Case events and closed cases shall be immutable, enforced by database triggers; an optional four-eyes rule for closure is available and off by default.",
        "A PDF case report shall be generated with all user text escaped.",
    ],
    [
        "A case list and detail page (alerts, transactions, accounts involved, notes, evidence, timeline), assignment, a PDF report and a case summary count.",
        "A closed case's history remains readable; dashboards count cases by status and outcome.",
    ],
    [
        "409 for an invalid transition or an edit of a closed case; 400 for an invalid file; 403 without the needed permission; a hash mismatch on download is refused.",
    ],
    extra=[("fig", S + "19-cases.png", "Figure 3.19  Investigation cases", 6.0), ("fig", S + "20-case-detail.png", "Figure 3.20  Case detail with linked alert, transaction, notes, evidence and timeline", 6.0)],
)

feature(13, "Analytics and Reporting", "Medium",
    "Shows management and analysts what is happening and exports it.",
    ["A dataset, a grouping (day, week or month) and a date range; an export request (report and format)."],
    [
        "Figures shall come from stored data through a daily-aggregate rollup table refreshed hourly by Celery, on demand and lazily on first use; the rollup shall be idempotent.",
        "Ten read endpoints shall serve: datasets, overview, volume over time, risk distribution, high-risk accounts, recent suspicious transactions, investigation summary, false positives, detection performance and model versions.",
        "CSV and PDF export shall neutralise formula injection and escape markup, and every export shall be audited.",
    ],
    [
        "An analytics page with key figures, a volume chart (bars, value area and flagged line), case workflow pipeline, risk rings and tables; downloadable CSV and PDF.",
        "Measured p95 latency 2-4 ms for most endpoints and 250 ms for high-risk accounts on 363,508 transactions.",
    ],
    [
        "Malformed dataset, date or granularity: 400; no data: an empty state; a failed refresh keeps the previous rollup and shows its timestamp.",
    ],
    extra=[("fig", S + "06-analytics.png", "Figure 3.21  Analytics dashboard", 6.0)],
)

feature(14, "Audit Log", "High",
    "Provides a trustworthy record of who did what.",
    ["Every state-changing or security-relevant request; for viewing, filters by actor, action, resource and time."],
    [
        "Authentication, user, role, import, run, case, alert-policy, risk-configuration and export actions shall be recorded with actor, e-mail, action, resource, IP address, user agent, request id and a changes object.",
        "Secrets shall be redacted from the changes object.",
        "Audit rows shall be append-only: database triggers shall reject updates and deletes, even from application code.",
        "Only users with `audit.read` (Super Admin and Auditor by default) shall view the log.",
    ],
    ["A filterable audit log page and API; retention is by backup and database policy."],
    ["403 without permission; invalid filters return 400; an attempted edit of an audit row fails at the database."],
    extra=[("fig", S + "22-audit-logs.png", "Figure 3.22  Audit log viewer", 6.0)],
)
