# 16 — Progress Tracker

Last updated: 2026-11-19 · Current phase: **4 — Dataset import & processing pipeline (implemented & checked; awaiting your approval)**

| Phase | Name | Status | Notes |
|---|---|---|---|
| 0 | Requirement analysis & architecture | **Approved** (2026-11-19) | Docs 00–18 |
| 1 | Environment & foundation | **Done (approved)** | Remaining deferred items: prod compose (16), Neo4j (7), import-linter |
| 2 | Auth, users, RBAC, audit | **Done (approved)** | |
| 3 | DB foundation & transactions | **Done (approved)** | |
| 4 | Import pipeline | **Implemented & checked — awaiting approval for Phase 5** | Backend 120 tests, frontend 32 tests pass; 1M-row import measured (~12k rows/s, target 20k missed); 6.36M and real PaySim not run |
| 5 | ML research & detection | **5A in progress** — data stage done: real PaySim + ULB profiled, cleaned, split chronologically, leakage-checked (17 tests); features, baseline and evaluation harness not started | Backend 137 tests pass; see doc 19. Awaiting go-ahead for the 5A feature/baseline stage |
| 6 | Behavioral analysis | Not Started | |
| 7 / 7B | Graph + Neo4j / graph experiments | Not Started | |
| 8 | Duplicates & OCR | Not Started | |
| 9 | Risk scoring | Not Started | |
| 10 | Explainable AI | Not Started | |
| 11 | Alerts | Not Started | |
| 12 | Case management | Not Started | |
| 13 | Frontend completion | Not Started | |
| 14 | Analytics & reporting | Not Started | |
| 15 | Integration/testing/optimisation | Not Started | |
| 16 | Deployment & final docs | Not Started | |

Requirement-level status lives in [18-REQUIREMENTS-TRACEABILITY.md](18-REQUIREMENTS-TRACEABILITY.md). Nothing is "Implemented", "Tested" or "Verified" yet.
