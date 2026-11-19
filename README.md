# FinGuard

**An Intelligent Financial Anomaly Detection and Transaction Investigation System using Machine Learning, Graph Analytics and Explainable AI.**

FinGuard is a final-year project to build a financial-intelligence platform that monitors transactions, flags suspicious activity, explains *why* it was flagged, and supports human investigators through alerts and case management. It is built as a product-style system, not a notebook or a CRUD demo.

> **Status: under active development.** Phases 0–4 are complete (planning, project foundation, authentication/RBAC/audit, transaction browsing, and the dataset import pipeline). The detection, graph, risk, explainability, alert and case-management modules described below are **planned and not yet implemented**. See [Project status](#project-status) for exactly what works today.

> **Design principle:** FinGuard never declares a person or transaction criminal. Models and rules produce *risk indicators and review alerts*; authorised human investigators make the final decision. The data model keeps model prediction, anomaly indicator, supporting evidence, investigator assessment and final outcome separate.

> **Data:** academic prototype using public or synthetic datasets only (PaySim, ULB credit-card fraud, Elliptic Bitcoin). It is not connected to real bank accounts or customer data.

---

## What FinGuard will do

For any flagged transaction or account, an investigator can see: what happened, why it was flagged, what is connected to it, how risky it is, what evidence supports the alert, and what to examine next.

| # | Module | What it provides |
|---|---|---|
| 1 | **Transaction monitoring** | CSV/Excel/API ingestion with flexible column mapping, validation, duplicate-ID handling, import history, search/filter/sort, transaction-level audit trail |
| 2 | **ML anomaly detection** | Supervised (Logistic Regression, Random Forest, XGBoost) and unsupervised (Isolation Forest, LOF, One-Class SVM, Autoencoder) detection, with model versioning and performance tracking |
| 3 | **Spending-pattern analysis** | Per-account behavioral profiles and deviation scores (amount, frequency, timing, merchant category where available) |
| 4 | **Graph relationship analysis** | Accounts as nodes, transfers as directed edges: chains, cycles, shared beneficiaries, communities; NetworkX analytics with a Neo4j projection |
| 5 | **Duplicate detection** | Exact and fuzzy matching of transactions and invoices, Tesseract OCR extraction, human verification of candidates |
| 6 | **Alerts** | Deduplicated, evidence-preserving alerts with prioritisation, assignment, acknowledgement, escalation, email and real-time notifications |
| 7 | **Risk scoring** | Configurable weighted score `R = 0.25A + 0.20B + 0.20G + 0.15F + 0.10D + 0.10H`, explicit handling of missing signals (never silently treated as zero risk) |
| 8 | **Explainable AI** | SHAP, LIME, feature importance, behavioral/graph evidence, downloadable PDF reports |
| 9 | **Case management** | Validated case state machine, notes, evidence attachments, timeline, resolution reports, full audit history |
| 10 | **Analytics dashboard** | Volume/value trends, risk distributions, model comparison, false-positive and resolution statistics |

Risk categories (configurable project thresholds, **not** regulatory standards): 0–29 Low · 30–59 Medium · 60–79 High · 80–100 Critical.

### Research questions
The project is also a research study. Results will come only from implemented, reproducible experiments:

1. Does a hybrid framework beat individual classifiers?
2. Do graph-derived features improve detection over transaction-only models?
3. Can unsupervised detection surface suspicious activity absent from labelled data?
4. How well does Explainable AI communicate the factors behind a prediction?
5. Does combined risk scoring improve alert prioritisation and reduce investigation workload?
6. How does performance hold up as transaction behavior changes over time?

---

## Architecture

A **modular monolith**: one Django backend owning APIs, auth, business logic and orchestration, with ML and graph code as separate pure-Python libraries called from service layers and Celery workers (never inside HTTP handlers).

```
React + TypeScript SPA ──REST/WebSocket──► Django (DRF + Channels)
                                              │
              ┌───────────────┬───────────────┼───────────────┐
         PostgreSQL        Redis           Neo4j          Media storage
     (system of record)  (Celery broker,  (rebuildable    (uploads, evidence,
                          cache, channels) graph copy)     model artifacts)
                                              ▲
                                     Celery workers (imports, scoring,
                                     graph builds, OCR, reports, email)
```

- **PostgreSQL is authoritative** for all business and investigation data; Neo4j is a one-way, idempotent, rebuildable projection for graph traversal.
- **Default-deny RBAC:** every endpoint must declare the permission it needs; a test fails the build if any route does not.
- **Append-only audit log**, enforced by a database trigger.

Full diagrams and design: [docs/05-SYSTEM-ARCHITECTURE.md](docs/05-SYSTEM-ARCHITECTURE.md), [docs/06-DATABASE-DESIGN.md](docs/06-DATABASE-DESIGN.md), [docs/07-API-SPECIFICATION.md](docs/07-API-SPECIFICATION.md).

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, TypeScript (strict), Tailwind CSS, TanStack Query, React Router, React Hook Form + Zod; Recharts and React Flow for charts and graphs (planned) |
| Backend | Python 3.12, Django 5.2, Django REST Framework, drf-spectacular (OpenAPI), SimpleJWT, Django Channels |
| Async | Celery, Redis |
| Databases | PostgreSQL 16, Neo4j 5 Community (or Aura) |
| ML / data (planned) | scikit-learn, XGBoost, PyTorch, pandas, NumPy, NetworkX, SHAP, LIME |
| OCR (planned) | Tesseract |
| Infra | Docker, Docker Compose, GitHub Actions CI |

Rationale and versions: [docs/04-TECHNOLOGY-STACK.md](docs/04-TECHNOLOGY-STACK.md). Decisions and trade-offs: [docs/15-DECISION-LOG.md](docs/15-DECISION-LOG.md).

## Roles

| Role | Purpose |
|---|---|
| Super Admin | Manage users, roles, settings, risk parameters and models |
| Financial Analyst | Monitor transactions, triage alerts, examine risk |
| Fraud Investigator | Work cases, review graphs, attach evidence, produce reports |
| Auditor | Read-only access to investigations and audit records |
| Management | High-level analytics and organisational reports |

The permission matrix is in [docs/10-SECURITY-AND-RBAC.md](docs/10-SECURITY-AND-RBAC.md). Roles and permissions are data, editable by a Super Admin in the app.

---

## Project status

| Phase | Scope | State |
|---|---|---|
| 0 | Requirements, architecture, roadmap, traceability matrix | ✅ Done |
| 1 | Docker stack, Django/DRF/Celery/Channels skeleton, frontend shell, CI, health endpoints | ✅ Done |
| 2 | JWT auth (rotating httpOnly refresh cookie, lockout, throttling), RBAC, user & role management, audit log | ✅ Implemented and tested |
| 3 | Transaction/account/dataset schema, transaction & account APIs (search, filter, sort, pagination), transactions UI, 1M-row query check | ✅ Implemented and tested |
| 4 | Dataset import pipeline: CSV/Excel upload, column mapping, validation, duplicate-ID policies, background jobs with live progress, resume/cancel, API ingestion | ✅ Implemented and tested |
| 5 | ML research and detection: real PaySim/ULB data pipeline, 7 algorithms evaluated, model registry, detection runs and pages | ✅ Implemented and tested |
| 6 | Behavioral analysis: as-of account profiles, trends, robust deviation scoring with component breakdown, batch runs, Account Behavior page | ✅ Implemented and tested |
| 7 | Graph analytics: cycle/chain/fan-in/shared-beneficiary detection, graph risk score, Neo4j projection (sync, drift check), Relationship Graph pages | ✅ Implemented and tested |
| 8 | Duplicate detection: repeated payments, invoice upload with Tesseract OCR, fuzzy/image matching, human review workflow, PDF report | ✅ Implemented and tested |
| 9–16 | Risk scoring, XAI, alerts, cases, analytics, deployment | 📋 Planned |

**Works today:** login/logout/refresh, user management, role/permission editing, audit log viewer, browsing/searching/filtering/sorting transactions and accounts, transaction status changes with an audit trail, health endpoints, OpenAPI docs. importing CSV/Excel files (validated, mapped, de-duplicated, in the background with live progress and a row-error report) and submitting transactions through an ingestion API. Test data: `seed_mock_transactions` and `generate_mock_paysim_csv` create random, clearly labelled MOCK data; real PaySim rows can be imported through the normal import page (a 343k-row slice was imported and scored as a check).
**Also works:** account behavior profiles and per-transaction behavioral deviation (validated on a synthetic scenario; not applicable to PaySim, where every transaction is cold start), and scoring a dataset's transactions with a registered model (Anomaly Detection page) and comparing registered models' offline results (Model Performance page). Research results on the real PaySim and ULB data are in [docs/08](docs/08-ML-RESEARCH-AND-METHODOLOGY.md) (PaySim balance fields saturate the problem; the cautious figure is the `core` feature set).
**Verified so far:** 258 backend tests and 51 frontend tests pass; ruff, mypy, `tsc` and the production build are clean. The UI pages have not yet been exercised in a browser (browser E2E tests are planned).

Per-requirement status (219 tracked requirements, none yet marked Verified): [docs/18-REQUIREMENTS-TRACEABILITY.md](docs/18-REQUIREMENTS-TRACEABILITY.md). Phase plan and acceptance criteria: [docs/12-IMPLEMENTATION-ROADMAP.md](docs/12-IMPLEMENTATION-ROADMAP.md). Known limitations: [docs/17-KNOWN-LIMITATIONS.md](docs/17-KNOWN-LIMITATIONS.md).

---

## Getting started

Requires **Docker** (all development runs in containers: Python 3.12, Node 22).

```bash
git clone https://github.com/Ajayrazz/FINGUARD-Intelligent-Financial-Anomaly-Detection-and-Transaction-Investigation-System.git
cd FINGUARD-Intelligent-Financial-Anomaly-Detection-and-Transaction-Investigation-System

cp .env.example .env          # then replace every "change-me" with your own random value
docker compose up -d --build  # db, redis, backend (:8000), worker, frontend (:5173)

docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py create_superadmin --email you@example.com
```

Then open:
- App: http://localhost:5173 (sign in with the admin you just created)
- API docs (Swagger): http://localhost:8000/api/docs/
- Health: `/api/v1/health/` and `/api/v1/health/ready/`

> The backend (Daphne) does not auto-reload: run `docker compose restart backend worker` after changing backend code.

### Run the checks

```bash
docker compose exec backend ruff check .
docker compose exec backend mypy .
docker compose exec backend pytest -q
docker compose exec frontend sh -c "npx tsc -b && npm run lint && npm test"
```

## Repository layout

```
backend/
  config/          Django settings (base/development/production), ASGI, Celery, URLs
  apps/accounts/   Users, roles, permissions, JWT auth, RBAC
  apps/audit/      Append-only audit log
  apps/datasets/   Datasets, mapping profiles, import jobs and the ingestion pipeline (sources, cleaning, loader)
  apps/transactions/ Accounts, transactions, per-transaction events, APIs
  apps/model_registry/ Registered models, versions, offline evaluations (read-only API)
  apps/graph_engine/ Graph snapshots, findings, Neo4j sync, neighborhood APIs
  graph_engine_lib/ Pure-Python graph detectors (cycles, chains, fan-in/out, shared beneficiaries, communities)
  apps/duplicates/  Invoice upload + OCR, duplicate candidates, review workflow, PDF report
  duplicates_lib/   Pure-Python normalisation, extraction, matching, synthetic invoice generator
  apps/behavior/    As-of account profiles, trends, deviation engine, behavior runs
  apps/detection/   Detection runs, per-transaction predictions, hash-verified model loading
  shared/          Health checks, error handling, middleware
  tests/           pytest suite (incl. generated RBAC matrix)
frontend/src/      React app: api client, auth, pages, UI components
docker/            Dockerfiles        docker-compose.yml   Dev stack
docs/              Requirements, architecture, DB/API design, ML methodology, roadmap,
                   decision log, progress tracker, traceability matrix, session handoff
datasets/          Git-ignored raw/ and processed/ data (see datasets/README.md, docs/19)
  backend/ml_engine/ ML research package: dataset validation, cleaning, chronological splits (Phase 5)
```
More apps (`detection`, `graph_engine`, `risk_engine`, `alerts`, `investigations`, …) and the `ml_engine/` and graph libraries are created in the phase that implements them.

## Datasets

| Dataset | Use |
|---|---|
| **PaySim** (~6.36M synthetic mobile-money transactions) | Primary development: classification, behavior, graph, hybrid experiments |
| **ULB credit-card fraud** (284,807 rows, 492 frauds) | Independent imbalanced-classification benchmark |
| **Elliptic Bitcoin** (~203k nodes) | Graph-learning experiments |

They have different schemas and fraud meanings and are **never merged**. Raw files are not stored in this repo. Strategy, leakage risks and caveats: [docs/09-DATASET-STRATEGY.md](docs/09-DATASET-STRATEGY.md), [docs/08-ML-RESEARCH-AND-METHODOLOGY.md](docs/08-ML-RESEARCH-AND-METHODOLOGY.md).

## Security

JWT with short-lived in-memory access tokens and rotating httpOnly refresh cookies, bcrypt password hashing, account lockout and rate limiting, default-deny role-based permissions enforced on the backend, an append-only audit log, secrets only via environment variables. Details and threat considerations: [docs/10-SECURITY-AND-RBAC.md](docs/10-SECURITY-AND-RBAC.md).

## Documentation index

[00 Overview](docs/00-PROJECT-OVERVIEW.md) · [01 Product requirements](docs/01-PRODUCT-REQUIREMENTS.md) · [02 Functional](docs/02-FUNCTIONAL-REQUIREMENTS.md) · [03 Non-functional](docs/03-NON-FUNCTIONAL-REQUIREMENTS.md) · [04 Stack](docs/04-TECHNOLOGY-STACK.md) · [05 Architecture](docs/05-SYSTEM-ARCHITECTURE.md) · [06 Database](docs/06-DATABASE-DESIGN.md) · [07 API](docs/07-API-SPECIFICATION.md) · [08 ML & research](docs/08-ML-RESEARCH-AND-METHODOLOGY.md) · [09 Datasets](docs/09-DATASET-STRATEGY.md) · [10 Security & RBAC](docs/10-SECURITY-AND-RBAC.md) · [11 UI/UX](docs/11-UI-UX-PLAN.md) · [12 Roadmap](docs/12-IMPLEMENTATION-ROADMAP.md) · [13 Testing](docs/13-TESTING-STRATEGY.md) · [14 Deployment](docs/14-DEPLOYMENT-GUIDE.md) · [15 Decisions](docs/15-DECISION-LOG.md) · [16 Progress](docs/16-PROGRESS-TRACKER.md) · [17 Limitations](docs/17-KNOWN-LIMITATIONS.md) · [18 Traceability](docs/18-REQUIREMENTS-TRACEABILITY.md) · [19 Dataset profile](docs/19-DATASET-PROFILE-AND-PREPROCESSING.md) · [Session handoff](docs/SESSION-HANDOFF.md)

## Limitations

Public/synthetic data does not represent real banking fraud; no result is claimed until produced by an executed experiment; risk weights and thresholds are research proposals, not regulatory standards; ML predictions and explanations (SHAP/LIME) are indicators, not proof of wrongdoing.
