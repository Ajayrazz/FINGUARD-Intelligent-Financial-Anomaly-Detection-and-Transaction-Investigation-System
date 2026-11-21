"""Report content, part A: cover data, sections 1 and 2.

A block is a tuple: ("h", level, text) | ("p", text) | ("bul", [items]) | ("num", [items]) |
("table", caption, headers, rows, col_widths_in_percent) | ("fig", file, caption, width_in_inches) | ("note", text) | ("pb",)
Inline: **bold**, `code`.  Every statement is taken from the code base or the project documents (docs/00-24).
"""

PROJECT = "FinGuard"
PROJECT_FULL = "FinGuard: An Intelligent Financial Anomaly Detection and Transaction Investigation System Using Machine Learning, Graph Analytics and Explainable Artificial Intelligence"
DOC_TITLE = "Software Requirements Specification"
COURSE_CODE = "[Course code: to be filled in]"
COURSE_NAME = "[Course name: to be filled in]"
STUDENTS = [
    ("Ajay Razz", "12326749"),
    ("Vikash Kumar", "12307252"),
    ("Rajvardhan", "12325161"),
]
PREPARED_FOR = "Continuous Assessment 3"
TERM = "[Academic term: to be filled in; the template shows Spring 2025]"
SUPERVISOR = "[Supervisor / faculty name: to be filled in]"
INSTITUTION = "[Institution and department: to be filled in]"
SUBMISSION_DATE = "[Submission date: to be filled in]"

A = []  # blocks


def add(*blocks):
    A.extend(blocks)


# ------------------------------------------------------------------------------------------------ 1. INTRODUCTION
add(
    ("h", 1, "1. Introduction"),
    ("p", "This Software Requirements Specification (SRS) describes **FinGuard**, a web platform that helps analysts and investigators find unusual financial transactions, understand why they were flagged, trace the accounts connected to them, and record the investigation that follows. It is written for the three developers, for faculty who review the project, and for any engineer who must maintain or extend the system. It follows the structure of the supplied IEEE-style SRS template. Every requirement and every statement about behaviour in this document was checked against the source code and the project's test results; where something is only planned, it is labelled as future scope."),
    ("h", 2, "1.1 Purpose"),
    ("p", "The purpose of this SRS is to state precisely what FinGuard does, for whom, under which constraints, and how that was verified. The intended audience is: (a) the course evaluators of Continuous Assessment 3, who need to judge whether the implemented system satisfies its stated requirements; (b) the project team, who use it as the single reference for scope and traceability; and (c) future maintainers and researchers who extend the modules or repeat the experiments."),
    ("p", "FinGuard is built as a final-year Computer Science Engineering project. The specification therefore also records the research framing: the project's contribution is the **integration and honest measurement** of known techniques (supervised and unsupervised machine learning, behavioural profiling, graph analytics, duplicate detection, explainable AI, risk scoring and case management) in one auditable platform, not the invention of new algorithms."),
    ("h", 2, "1.2 Scope"),
    ("p", "**Product name.** FinGuard (full title: " + PROJECT_FULL + ")."),
    ("p", "**What the software does.** FinGuard imports transaction data, stores it in a relational database, scores it with machine-learning models and rule-based engines, combines the signals into an explainable 0-100 risk score, raises deduplicated alerts, and supports human investigation through cases, notes, evidence and reports. It consists of ten functional modules and a cross-cutting layer for security and audit:"),
    ("table", "Table 1.1  The ten modules and the cross-cutting layer", ["#", "Module", "Implemented in (Django app / library)"], [
        ["1", "Financial transaction monitoring (import, storage, search, history)", "datasets, transactions"],
        ["2", "AI transaction anomaly detection (supervised and unsupervised)", "detection, model_registry, ml_engine"],
        ["3", "Unusual spending pattern detection (behavioural profiles)", "behavior"],
        ["4", "Graph relationship analysis (NetworkX; optional Neo4j projection)", "graph_engine, graph_engine_lib"],
        ["5", "Duplicate invoice and transaction identification (OCR, fuzzy matching)", "duplicates, duplicates_lib"],
        ["6", "Suspicious account activity alerts", "alerts"],
        ["7", "Intelligent risk scoring engine", "risk_engine, risk_engine_lib"],
        ["8", "Explainable AI reports (SHAP, LIME, PDF)", "explain"],
        ["9", "Investigation case management", "cases"],
        ["10", "Visualisation and analytics dashboard", "analytics, React frontend"],
        ["-", "Cross-cutting: users, roles, authentication, audit log", "accounts, audit"],
    ], [6, 58, 36]),
    ("p", "**What the software does not do.** FinGuard produces indicators and review alerts. It never declares a person or a transaction fraudulent; a human investigator decides the outcome of every case. It is not connected to any bank or payment network, does not move money, and does not process live card or banking traffic. It is a single-organisation system: every approved user shares the same data (there are no separate customer workspaces, see section 2.4). It has no mobile application, no multi-factor authentication and no CAPTCHA."),
    ("p", "**Goals, stated measurably.** The following goals guided the implementation and are verified in Appendix A.2:"),
    ("bul", [
        "Import files of one million rows or more in the background without blocking the API; measured about 12,000 rows per second at one million rows (the initial target of 20,000 rows per second was **not** met).",
        "Answer transaction list and search requests in under 500 ms at the 95th percentile; measured 5-170 ms on 363,508 transactions.",
        "Explain every model score with a stored, versioned explanation (SHAP for tree and linear models, LIME for any model).",
        "Enforce every permission on the server (default deny) and record security-relevant actions in an append-only audit log.",
        "Run the whole system with one command (`docker compose up`) and provide a production deployment with automatic HTTPS and a tested backup and restore.",
    ]),
    ("h", 2, "1.3 Definitions, Acronyms, and Abbreviations"),
    ("table", "Table 1.2  Terms used in this document", ["Term", "Meaning"], [
        ["Alert", "A deduplicated notification that a transaction or account deserves review, created by a rule or by the risk score."],
        ["Anomaly", "A transaction or behaviour that differs from what a model or profile expects. Rare does not mean fraudulent."],
        ["API", "Application Programming Interface; here the REST interface under /api/v1."],
        ["Audit log", "An append-only table that records who did what and when; protected by database triggers."],
        ["Case", "An investigation record with status, assignee, notes, evidence and an outcome chosen by a human."],
        ["Celery", "Python task queue used for imports, scoring, graph builds, OCR, PDFs and e-mail."],
        ["Channels", "Django extension that serves WebSockets for live updates."],
        ["CSP", "Content Security Policy; a browser header that limits where scripts can come from."],
        ["DFD", "Data Flow Diagram."],
        ["DRF", "Django REST Framework."],
        ["ERD", "Entity Relationship Diagram."],
        ["Fan-in / fan-out", "Many accounts paying one account (fan-in) or one account paying many (fan-out) in a short time."],
        ["JWT", "JSON Web Token (RFC 7519); the access token carried by every API request."],
        ["LIME", "Local Interpretable Model-agnostic Explanations; a local surrogate-model explanation method."],
        ["LOF", "Local Outlier Factor; an unsupervised density-based anomaly detector."],
        ["Neo4j", "A graph database. In FinGuard it holds a rebuildable copy of the account graph; PostgreSQL is authoritative."],
        ["NFR / FR", "Non-functional / functional requirement."],
        ["OCR", "Optical Character Recognition; here Tesseract is used to read invoice images."],
        ["PaySim", "A public synthetic mobile-money transaction simulator data set used for training and evaluation."],
        ["PR-AUC", "Area under the precision-recall curve; the main metric for rare-fraud data."],
        ["RBAC", "Role-Based Access Control."],
        ["Risk score (R)", "A 0-100 combination of six component scores (A, B, G, F, D, H) with a stored coverage value."],
        ["SHAP", "SHapley Additive exPlanations; an additive feature-attribution method."],
        ["SPA", "Single-page application; the React frontend."],
        ["ULB data set", "The public credit-card fraud data set of the Universite Libre de Bruxelles (284,807 transactions)."],
        ["WebSocket", "A persistent browser-server connection used to push alerts and progress."],
    ], [22, 78]),
    ("h", 2, "1.4 References"),
    ("p", "All references below exist and were consulted for the design; none was invented. Project documents are in the repository folder `docs/`."),
    ("table", "Table 1.3  References", ["Ref.", "Document"], [
        ["[1]", "IEEE Std 830-1998, IEEE Recommended Practice for Software Requirements Specifications. IEEE, 1998. (The supplied template follows the IEEE guide to the SRS.)"],
        ["[2]", "E. A. Lopez-Rojas, A. Elmir and S. Axelsson, \"PaySim: A financial mobile money simulator for fraud detection,\" 28th European Modeling and Simulation Symposium (EMSS), Larnaca, 2016."],
        ["[3]", "A. Dal Pozzolo, O. Caelen, R. A. Johnson and G. Bontempi, \"Calibrating probability with undersampling for unbalanced classification,\" IEEE Symposium Series on Computational Intelligence (SSCI), 2015. (ULB credit-card fraud data set.)"],
        ["[4]", "F. T. Liu, K. M. Ting and Z.-H. Zhou, \"Isolation Forest,\" 8th IEEE International Conference on Data Mining (ICDM), 2008, pp. 413-422."],
        ["[5]", "M. M. Breunig, H.-P. Kriegel, R. T. Ng and J. Sander, \"LOF: Identifying density-based local outliers,\" ACM SIGMOD, 2000, pp. 93-104."],
        ["[6]", "B. Scholkopf, J. C. Platt, J. Shawe-Taylor, A. J. Smola and R. C. Williamson, \"Estimating the support of a high-dimensional distribution,\" Neural Computation 13(7), 2001, pp. 1443-1471."],
        ["[7]", "L. Breiman, \"Random forests,\" Machine Learning 45(1), 2001, pp. 5-32."],
        ["[8]", "T. Chen and C. Guestrin, \"XGBoost: A scalable tree boosting system,\" ACM SIGKDD, 2016, pp. 785-794."],
        ["[9]", "S. M. Lundberg and S.-I. Lee, \"A unified approach to interpreting model predictions,\" Advances in Neural Information Processing Systems 30 (NeurIPS), 2017."],
        ["[10]", "M. T. Ribeiro, S. Singh and C. Guestrin, \"Why should I trust you? Explaining the predictions of any classifier,\" ACM SIGKDD, 2016, pp. 1135-1144."],
        ["[11]", "V. D. Blondel, J.-L. Guillaume, R. Lambiotte and E. Lefebvre, \"Fast unfolding of communities in large networks,\" Journal of Statistical Mechanics, P10008, 2008. (Louvain method.)"],
        ["[12]", "A. A. Hagberg, D. A. Schult and P. J. Swart, \"Exploring network structure, dynamics, and function using NetworkX,\" 7th Python in Science Conference (SciPy), 2008."],
        ["[13]", "T. Saito and M. Rehmsmeier, \"The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets,\" PLOS ONE 10(3): e0118432, 2015."],
        ["[14]", "M. Jones, J. Bradley and N. Sakimura, \"JSON Web Token (JWT),\" RFC 7519, IETF, 2015."],
        ["[15]", "OWASP Foundation, \"OWASP Top 10:2021.\" https://owasp.org/Top10/"],
        ["[16]", "Django Software Foundation, Django 5.2 documentation. https://docs.djangoproject.com/"],
        ["[17]", "FinGuard project documents 00-24 (overview, requirements, architecture, database, API, ML methodology, security, deployment, decision log, traceability, test report, user guide, final experiment report) in the repository folder docs/."],
    ], [8, 92]),
    ("h", 2, "1.5 Overview"),
    ("p", "The rest of this document is organised as the template prescribes. **Section 2** puts the product in context (perspective, functions, users, constraints, assumptions). **Section 3** is the largest: 3.1 describes the external interfaces with screenshots of the running application; 3.2 specifies fourteen functional features, each with introduction, inputs, processing, outputs and error handling; 3.5 gives measurable non-functional requirements; 3.7 lists design constraints; 3.9 other requirements. **Section 4** presents the analysis models: data flow diagrams, use cases, the entity relationship model, activity, sequence, class and state models. **Appendix A** adds informative material: declaration and acknowledgement placeholders, implementation details, test and security results, the machine-learning evaluation, deployment, challenges and solutions, limitations and future work, and requirement traceability. The appendices are **informative and are not part of the requirements**; the requirements are sections 3.1 to 3.9."),
)

# ------------------------------------------------------------------------------------------------ 2. GENERAL DESCRIPTION
add(
    ("h", 1, "2. General Description"),
    ("p", "This section describes the factors that shape the requirements. It states no specific requirement; those start in section 3."),
    ("h", 2, "2.1 Product Perspective"),
    ("p", "Banks and payment companies normally run rule- and threshold-based monitoring tools. Such tools miss patterns they were not told about, create many false positives, look at each transaction alone and ignore the relationships between accounts, give no reason for a score, and keep monitoring separate from the investigation that follows. FinGuard is a standalone, self-hosted web application that closes these gaps in one place: detection, explanation, graph context and case handling share one database and one audit trail."),
    ("p", "FinGuard does not replace a core-banking or payment system and has no interface to one. Data enters through file upload (CSV, XLSX) or a batch ingestion API. It depends on four external services only: PostgreSQL (system of record), Redis (task queue and live channel), an SMTP server (account and alert e-mail) and, optionally, Neo4j (a rebuildable copy of the account graph). The architecture is a **modular monolith**: one Django project with fourteen apps, a service layer, and pure-Python libraries for machine learning, graph analysis, duplicate matching and risk scoring that contain no Django code."),
    ("fig", "fig_architecture.png", "Figure 2.1  System architecture", 6.4),
    ("p", "Design decisions behind this perspective (full list in the decision log, doc 15): PostgreSQL is authoritative and Neo4j is a one-way, rebuildable projection; long-running work always runs in Celery, never in a request handler; every model score, explanation and risk assessment records the exact model version, configuration and algorithm version that produced it, so it can be reproduced."),
    ("h", 2, "2.2 Product Functions"),
    ("p", "In summary, the software performs the following functions (specified in detail in section 3.2):"),
    ("bul", [
        "**Accounts:** self-registration with e-mail confirmation, administrator approval with a role, sign-in with rotating tokens, password reset, user and role administration.",
        "**Data:** guided import of CSV and XLSX files with column mapping, validation, duplicate-ID policy, progress, error report and resumable processing; a batch ingestion API.",
        "**Detection:** seven model families trained, evaluated and registered (logistic regression, random forest, XGBoost, Isolation Forest, LOF, one-class SVM, autoencoder); detection runs score platform data with the models built on the PaySim feature set and store the predictions; a model registry keeps versions and offline evaluation.",
        "**Behaviour:** per-account profiles and five deviation components (amount, burst, spend jump, new counterparty, hour of day) computed from earlier history only.",
        "**Graph:** cycles, rapid pass-through chains, fan-in and fan-out, shared beneficiaries and dense clusters; per-account degree, PageRank, clustering and community; an interactive relationship network.",
        "**Duplicates:** invoice OCR, normalisation and fuzzy matching, repeated-payment detection, four match classes, human review of every candidate.",
        "**Risk and explanation:** a six-component risk score with missing-signal policies; SHAP, LIME, behavioural, graph and risk narratives; PDF reports.",
        "**Response:** nine alert rules with deduplication, severity, assignment and e-mail or live notification; investigation cases with a validated status machine, notes, evidence and PDF reports.",
        "**Insight:** analytics dashboards (volume, risk distribution, high-risk accounts, false positives, detection performance, investigations) with CSV and PDF export, and an audit-log viewer.",
    ]),
    ("h", 2, "2.3 User Characteristics"),
    ("p", "FinGuard has five working roles and one holding role. Roles are data, not code: each role is a set of 54 permission codenames (for example `cases.close`, `risk.configure`) that a Super Admin can edit. The defaults below were generated from the permission registry in the code."),
    ("table", "Table 2.1  Roles and their default permissions", ["Role", "Typical user", "Default permissions", "What the role is for"], [
        ["Super Admin", "System owner", "All 54", "Manage users, roles, risk and alert settings, models; approve registrations."],
        ["Financial Analyst", "Monitoring analyst", "37", "Import data, run detection and scoring, triage alerts, open cases, view analytics."],
        ["Fraud Investigator", "Case worker", "33", "Investigate cases, keep notes and evidence, produce reports, review duplicates."],
        ["Auditor", "Compliance reviewer", "20", "Read-only access to investigation history and the audit log."],
        ["Management", "Executive", "4", "High-level counts and analytics only (no record-level data)."],
        ["Pending approval", "Newly registered person", "0", "Holds no access until a Super Admin approves the account with a role."],
    ], [16, 18, 14, 52]),
    ("p", "Users are assumed to be financial-crime analysts or investigators with basic computer literacy; they are not assumed to know machine learning, which is why every score is accompanied by an explanation and a plain-language note that it is an indicator and not proof. Pages are keyboard-navigable and responsive from 360 px width."),
    ("h", 2, "2.4 General Constraints"),
    ("bul", [
        "**Data:** only public, synthetic or anonymised data is used for training and demonstration (PaySim and the ULB credit-card set). No real customer data is processed.",
        "**Labels:** supervised models run only on data sets that carry fraud labels; the public sets have extreme class imbalance (0.12-0.44 % fraud in the test splits), which limits what can be concluded.",
        "**Single organisation:** the system has no tenants; all approved users see the same data. Separate customer workspaces would be a new phase of work.",
        "**Security regulation:** the system is a research prototype and has not been certified against any financial-sector regulation.",
        "**Runtime pinning:** Python 3.12 and Node 22 in containers, PostgreSQL 16, Redis 7, Neo4j 5 Community.",
        "**Hardware:** development and testing were done on one laptop (Docker Desktop, macOS); a production host needs about 4 GB of RAM because of the machine-learning libraries.",
        "**Process:** the project was built phase by phase (phases 0-17) with documentation updated in the same change as the code.",
    ]),
    ("h", 2, "2.5 Assumptions and Dependencies"),
    ("bul", [
        "A modern evergreen browser is used; the interface depends on JavaScript and, for 3D charts, WebGL.",
        "A working SMTP server and a correct `FRONTEND_BASE_URL` are available in production; otherwise account confirmation and password-reset e-mails cannot be delivered. In development, e-mails are printed in the worker log.",
        "Tesseract OCR is installed in the backend image; the test suite fails if it is missing.",
        "Input files are in UTF-8 or a detected encoding, with at least a sender, a receiver (or merchant), an amount and a time reference per row.",
        "The administrator keeps `.env` secrets out of version control; production refuses to start with a short or placeholder secret key.",
        "If any of these assumptions changes (for example a different mail provider or database version), the corresponding requirements in section 3 must be revisited.",
    ]),
)
