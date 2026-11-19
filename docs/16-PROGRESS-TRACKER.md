# 16 — Progress Tracker

Last updated: 2026-11-19 · Current phase: **4 — Dataset import & processing pipeline (implemented & checked; awaiting your approval)**

| Phase | Name | Status | Notes |
|---|---|---|---|
| 0 | Requirement analysis & architecture | **Approved** (2026-11-19) | Docs 00–18 |
| 1 | Environment & foundation | **Done (approved)** | Remaining deferred items: prod compose (16), Neo4j (7), import-linter |
| 2 | Auth, users, RBAC, audit | **Done (approved)** | |
| 3 | DB foundation & transactions | **Done (approved)** | |
| 4 | Import pipeline | **Implemented & checked — awaiting approval for Phase 5** | Backend 120 tests, frontend 32 tests pass; 1M-row import measured (~12k rows/s, target 20k missed); 6.36M and real PaySim not run |
| 5 | ML research & detection | **5A–5D implemented and checked — awaiting approval for Phase 6** — 7 algorithms evaluated on real PaySim and ULB; detection runs, predictions, model registry API, Anomaly Detection and Model Performance pages | Backend 179 tests, frontend 37 tests pass; platform scoring verified equal to the research pipeline on 343k real PaySim rows. Not done: RQ1 hybrid, RQ3 overlap analysis, rolling-window drift (RQ6), browser testing |
| 6 | Behavioral analysis | **Implemented and checked — awaiting approval for Phase 7** | Backend 206 tests, frontend 41 tests pass; 5×40,000-in-10-min scenario scores 77–84; real PaySim is 100% cold start (not applicable); weights uncalibrated |
| 7 / 7B | Graph + Neo4j / graph experiments | **7 implemented and checked — awaiting approval for Phase 8; 7B not started** | Backend 237 tests (incl. real Neo4j), frontend 46 pass; planted cycle/chain/fan-in/shared beneficiaries found; real PaySim slice: 84 weak fan-in findings only; Neo4j slower than PostgreSQL for neighborhoods (measured); Aura verified; diagram not browser-tested |
| 8 | Duplicates, OCR | **Implemented and checked — awaiting approval for Phase 9** | Backend 258 tests (Tesseract really executed), frontend 51 pass; 40/40 OCR fields and 10/10 pair classes on the clean synthetic set, 50–68% under heavy rotation/noise; real PaySim slice has no repeats; UI not browser-tested |
| 9 | Risk scoring engine | **Implemented and checked — awaiting approval for Phase 10; F/H definitions need your confirmation (D-067)** | Backend 281 tests, frontend 56 pass; 64 availability combinations x 3 policies tested; real slice scored in 44 s; RQ5 calibration: combined score no better than model score on this data; UI not browser-tested |
| 10 | Explainable AI | **Implemented and checked — awaiting approval for Phase 11** | Backend 301 tests, frontend 62 pass; SHAP exact/faithful, LIME unstable (measured on real PaySim); version binding + staleness tested; usability review not done; UI not browser-tested |
| 11 | Alerts & notifications | **Implemented and checked — awaiting approval for Phase 12** | Backend 321 tests (real SMTP wire test, WebSocket push), frontend 67 pass; dedup acceptance cases tested; real slice exposed an alert flood (8,225) → per-rule cap; thresholds uncalibrated; UI not browser-tested |
| 12 | Case management | Not Started | |
| 13 | Frontend completion | Not Started | |
| 14 | Analytics & reporting | Not Started | |
| 15 | Integration/testing/optimisation | Not Started | |
| 16 | Deployment & final docs | Not Started | |

Requirement-level status lives in [18-REQUIREMENTS-TRACEABILITY.md](18-REQUIREMENTS-TRACEABILITY.md). Nothing is "Implemented", "Tested" or "Verified" yet.
