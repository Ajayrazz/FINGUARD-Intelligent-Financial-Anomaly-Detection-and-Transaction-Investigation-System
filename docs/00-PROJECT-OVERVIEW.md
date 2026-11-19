# 00 — Project Overview

**FinGuard: An Intelligent Financial Anomaly Detection and Transaction Investigation System Using Machine Learning, Graph Analytics and Explainable Artificial Intelligence.**

Status: **Phase 0 (planning) — awaiting approval.** No application code exists yet. See [16-PROGRESS-TRACKER.md](16-PROGRESS-TRACKER.md).

## 1. Problem
Rule/threshold-based monitoring misses unseen patterns, produces many false positives, ignores relationships between accounts, offers opaque ML scores, and splits monitoring from investigation. Large datasets (millions of rows) add a processing challenge.

## 2. Vision
One platform that answers, for any flagged transaction or account:
1. What happened? 2. What is suspicious? 3. Why was it flagged? 4. What is connected to it? 5. How risky is it? 6. What evidence supports the alert? 7. What should be examined next? 8. What was the final outcome?

**Guiding principle:** FinGuard produces *indicators and review alerts*. It never declares a person or transaction criminal. Humans decide. The UI and data model keep five things separate: *model prediction*, *anomaly indicator*, *supporting evidence*, *investigator assessment*, *final investigation outcome*.

## 3. The ten modules
| # | Module | Django app(s) |
|---|---|---|
| 1 | Financial Transaction Monitoring (ingest, store, search, audit) | `transactions`, `datasets` |
| 2 | AI Transaction Anomaly Detection (supervised + unsupervised) | `detection`, `model_registry`, `ml_engine/` |
| 3 | Unusual Spending Pattern Detection (behavioral profiles) | `behavioral` |
| 4 | Graph Relationship Analysis (NetworkX + Neo4j) | `graph_engine`, `graph_engine/` library |
| 5 | Duplicate Invoice & Transaction Identification (OCR, fuzzy) | `duplicates` |
| 6 | Suspicious Account Activity Alerts | `alerts` |
| 7 | Intelligent Risk Scoring Engine | `risk_engine` |
| 8 | Explainable AI Fraud Reports (SHAP, LIME, PDF) | `explainability` |
| 9 | Investigation Case Management | `investigations` |
| 10 | Visualization & Analytics Dashboard | `analytics`, React frontend |
| — | Cross-cutting: users/RBAC, audit | `accounts`, `audit` |

## 4. How the engines interact
```
Ingest (CSV/Excel/API) → validate/clean/map → PostgreSQL (authoritative)
   ├─► ML detection (supervised + unsupervised)  → scores
   ├─► Behavioral analysis (per-account profile)  → deviation score
   ├─► Graph analytics (NetworkX; Neo4j persisted)→ graph risk + findings
   └─► Duplicate detection (exact/fuzzy/OCR)      → duplicate score
                    ▼
        Risk engine (configurable weighted combination, missing-signal aware)
                    ▼
        Explainability (SHAP/LIME/behavioral/graph evidence, versioned)
                    ▼
        Alerts (deduplicated, evidence-preserving) → Cases (human review, audit)
                    ▼
        Analytics & reports (dashboards, PDFs, model performance)
```

## 5. Role of each platform component
- **Django/DRF** — single backend: APIs, auth, RBAC, business logic, orchestration of ML/graph, reports, audit, admin. ML runs as Python modules (`ml_engine/`, `graph_engine/`) called from service layers and Celery workers — never inside request handlers.
- **PostgreSQL** — system of record for everything (users, transactions, predictions, risk, alerts, cases, audit, model metadata).
- **Neo4j** — derived, rebuildable projection of the account/transaction graph for traversal queries and visualisation; never authoritative.
- **ML + XAI** — produce scores and explanations bound to a specific model version and prediction; explanations are not proof of fraud.
- **Celery/Redis** — all long-running work (imports, scoring, graph builds, OCR, PDFs, email) with user-visible task status. **Channels/WebSockets** — pushes alerts, import progress, case updates.

## 6. End-to-end workflow
Analyst uploads dataset → mapping & validation → import job (progress via WebSocket) → detection/behavioral/graph/duplicate runs → risk scores → alerts for High/Critical → case auto-created/linked → investigator reviews transaction, accounts, graph, explanation → notes/evidence → status transitions → resolution & closure report → dashboards update, false-positive stats feed model/threshold calibration.

## 7. Research framing
Contribution is *integration and measurement*, not invention of the techniques. Six research questions (RQ1–RQ6) are in [08-ML-RESEARCH-AND-METHODOLOGY.md](08-ML-RESEARCH-AND-METHODOLOGY.md). **No result will be stated unless produced by an executed experiment.**

## 8. Document index
01 Product requirements · 02 Functional · 03 Non-functional · 04 Stack · 05 Architecture · 06 Database · 07 API · 08 ML · 09 Datasets · 10 Security/RBAC · 11 UI/UX · 12 Roadmap · 13 Testing · 14 Deployment · 15 Decision log · 16 Progress · 17 Limitations · 18 Traceability · SESSION-HANDOFF.
