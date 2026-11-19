# Session Handoff

**Date:** 2026-11-19 · **Current phase:** 4 (import pipeline) — implemented & checked, awaiting approval · **Next:** Phase 5, Task 5A (EDA + baseline)

## Completed
- **Phases 1–2** (approved): Docker stack, Django/DRF/Celery/Channels skeleton, JWT auth, default-deny RBAC, audit log, users/roles/audit UI.
- **Phase 3** (approved): schema (datasets/transactions/model_registry), transaction/account/dataset APIs, Transactions UI, 1M-row query check (docs/06).
- **Phase 4:**
  - Pipeline in `apps/datasets/ingestion/`: `mapping.py` (canonical fields, paysim preset, suggestion, validation), `cleaning.py` (vectorised per-chunk validation; first-failing-check error codes), `sources.py` (`IngestionSource` protocol: CSV via `csv` module so malformed rows are detected, Excel read-only streaming, in-memory records for the API), `loader.py` (account upsert, `COPY`, advisory locks, first/last seen), `pipeline.py` (chunk transactions, duplicate policies reject/skip/flag, resume from `rows_processed`, cancel, per-job lock), `api.py` (<=1000 records sync ingestion). Upload validation in `uploads.py`; services/views for upload, preview, history, errors (+CSV export), cancel, resume(force), mapping profiles. Celery task `datasets.run_import`.
  - Realtime: `POST /ws/ticket/` + `/ws/events/` (`shared/consumers.py`); progress pushed to the job owner (`realtime.py`). `/ws/echo/` removed.
  - Frontend: import wizard, history, detail (progress bar, counters, row errors, download, cancel/resume, stalled-job force resume), `useEvents` WebSocket hook, multipart + download support in the API client, nav + routes.
  - New deps: pandas, numpy, openpyxl (constraints re-pinned). Ruff line length now 120.
  - Commands: `seed_mock_transactions` (`--purge` also removes import jobs), `generate_mock_paysim_csv --rows N --out path` (random MOCK PaySim-format file).
  - Measured (docs/06): 100k rows 6.8 s (~14.7k/s), 1M rows 83.6 s (~12k/s, target 20k missed, DB-bound); API stayed responsive during import.

## Verified (actually executed)
- Backend `pytest` **120 passed**; `ruff`, `ruff format --check`, `mypy` clean; `makemigrations --check` no drift. Includes upload attacks, mapping validation, row validation codes, duplicate policies (in-file, cross-chunk, vs database), Excel, resume after simulated crash, cancel, error cap, CSV-injection-safe export, API ingestion idempotency, WebSocket ticket + owner-only push, RBAC matrix for all new endpoints.
- Frontend `tsc -b` clean, `vitest` **32 passed**, `vite build` OK, oxlint 0 errors / 4 warnings.
- **Live** through the Vite proxy as a real analyst with the real worker: 100k and 1M uploads completed with exact counts; WebSocket progress events received; forced resume of a deliberately killed job completed; API latency measured during import.
- **Bugs found live and fixed:** a badly planned account-activity UPDATE (minutes for 100k rows); jobs orphaned by a killed worker (now lock + force resume); CSV row estimate off by one without trailing newline; latin-1 detection heuristic.
- **Not verified:** pages opened in a browser; 6.36M-row import; real PaySim file; Excel files beyond small ones.

## Local dev data (not in git)
The dev database has throwaway users (a Super Admin, an auditor and an analyst) created locally via `create_superadmin` and the users API. Credentials are intentionally not recorded in the repo; create your own with `docker compose exec backend python manage.py create_superadmin --email you@example.com`.

## Open items / decisions
- D-021: oxlint vs ESLint (needs your answer). Git: still no commit (waiting for your go-ahead).
- `/ws/echo/` and `shared.tasks.ping` remain as Phase 1 smoke items.
- `FR-ROLE-*` stay In Progress: permissions for later resources get added to `registry.py` as each phase adds endpoints.

## Open items / decisions
- D-021: oxlint vs ESLint still unconfirmed (kept oxlint). `/ws/echo/` and `shared.tasks.ping` remain Phase 1 smoke items.
- Dev DB contains the `MOCK demo (random data)` dataset (20,000 rows) for UI work; recreate with `seed_mock_transactions`. Benchmark datasets were purged.
- Real PaySim download (Kaggle, needs the user's account) is needed before Phase 5 produces meaningful results; Phase 5 can start on the mock/ULB data for pipeline plumbing only.

## Exact next steps
1. User approves Phase 4 and (ideally) downloads PaySim/ULB into `datasets/`.
2. Phase 5A: EDA report, preprocessing, time-respecting feature engineering, chronological splits, logistic-regression baseline, evaluation harness, `model_registry` writes, leakage tests. Add ML dependencies (scikit-learn, xgboost, torch CPU, shap, lime) one at a time with justification.

## Resume commands
```
cd "/Users/ajayrazz/Desktop/Django Project/FinGuard"
open -a Docker   # if the daemon is not running
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend pytest -q
docker compose up -d --build backend worker   # rebuild/recreate after code or dependency changes (restart alone keeps the old image)
```
