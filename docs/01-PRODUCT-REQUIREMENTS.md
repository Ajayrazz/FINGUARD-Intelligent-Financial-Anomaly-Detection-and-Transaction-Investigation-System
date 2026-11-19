# 01 — Product Requirements

## Users and goals
| Role | Primary goals |
|---|---|
| Super Admin | Manage users/roles, system/risk/model configuration, monitor system activity |
| Financial Analyst | Monitor transactions, triage alerts, examine risk and account behavior |
| Fraud Investigator | Work cases, review account graphs, add notes/evidence, update status, produce reports |
| Auditor | Read-only access to investigation history, audit records, system actions |
| Management | High-level analytics, risk trends, investigation statistics, permitted reports |

## Product principles
1. **Human in the loop** — detection yields indicators; people decide.
2. **Evidence preserved** — every alert/score/explanation stores the signals, model version and config version that produced it.
3. **Honest about missing data** — unavailable signals are *unavailable*, not zero risk.
4. **No fake functionality** — dashboards read real data; unfinished features are marked as such.
5. **Reproducible** — models, experiments and risk scores can be regenerated from stored metadata.
6. **Synthetic/public data only** for the academic prototype.

## Scope tiers
- **MVP (end-to-end thin slice):** auth+RBAC, CSV import (PaySim subset), transactions UI, Isolation Forest + RF/XGBoost baseline, basic risk score, alerts, cases, audit.
- **Core:** everything in Parts 2–6 of the master prompt (all 10 modules, 14 pages, 5 roles).
- **Advanced / future (architecture-ready only):** Kafka, GNN/temporal GNN (gated by experiment, see D-012), federated learning, biometrics, device fingerprints, privacy-preserving analysis, drift detection/adaptive ML, LLM summaries, multimodal analysis, automated prioritisation with human approval.

## Success criteria
- Every requirement in [18-REQUIREMENTS-TRACEABILITY.md](18-REQUIREMENTS-TRACEABILITY.md) reaches **Verified** or is documented in [17-KNOWN-LIMITATIONS.md](17-KNOWN-LIMITATIONS.md) with approval.
- Experiments answer RQ1–RQ6 with real, reproducible numbers.
- The demo workflow (Part 13 of roadmap, Phase 16) runs from clean checkout via Docker Compose.
- Developer (project owner) can explain every model, algorithm, API and decision — documentation exists for each.
