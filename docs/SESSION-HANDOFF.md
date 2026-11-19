# Session Handoff

**Date:** 2026-11-19 · **Current phase:** 3 (DB foundation & transactions) — implemented & checked, awaiting approval · **Next:** Phase 4, Task 4.1

## Completed
- **Phases 1–2** (approved): Docker stack, Django/DRF/Celery/Channels skeleton, JWT auth, default-deny RBAC, audit log, users/roles/audit UI.
- **Phase 3:**
  - Schema + migrations: `datasets` (Dataset, ColumnMappingProfile, ImportJob, ImportRowError), `transactions` (Account, Transaction with CHECK/unique constraints + 7 indexes, TransactionEvent with append-only trigger), `model_registry` (tables only).
  - New permissions in `apps/accounts/registry.py`: datasets.read/create, transactions.read/update_status, accounts.read (defaults per docs/10; Management has none).
  - APIs: datasets (list/create/detail), transactions (list with filters/search/sort/hybrid pagination, detail, status change, events, related), accounts (list, detail with totals, transactions by direction).
  - `seed_mock_transactions` management command (MOCK data generated in SQL; `--purge`).
  - Frontend: Transactions page (dataset selector, exact search, filters, sort, pagination, URL-synced state), Transaction detail (accounts, related, activity, status change dialog), Account page, nav + routes.
  - Measured 1M-row performance (docs/06): normal queries 2–34 ms; OFFSET page 20,000 = 832 ms; keyset flat ~5 ms.

## Verified (actually executed)
- Backend `pytest` **70 passed**; `ruff`, `ruff format --check`, `mypy` clean; `makemigrations --check` no drift. RBAC matrix extended to all new endpoints.
- Frontend `tsc -b` clean, `vitest` **20 passed**, `vite build` OK, oxlint 0 errors / 3 warnings.
- Live through the Vite proxy as a real analyst: dataset list, filtered/sorted list, status change + event written.
- **Not verified:** pages opened in a browser; PaySim-scale (6.36M) performance; import throughput (Phase 4).

## Local dev data (not in git)
The dev database has throwaway users (a Super Admin, an auditor and an analyst) created locally via `create_superadmin` and the users API. Credentials are intentionally not recorded in the repo; create your own with `docker compose exec backend python manage.py create_superadmin --email you@example.com`.

## Open items / decisions
- D-021: oxlint vs ESLint (needs your answer). Git: still no commit (waiting for your go-ahead).
- `/ws/echo/` and `shared.tasks.ping` remain as Phase 1 smoke items.
- `FR-ROLE-*` stay In Progress: permissions for later resources get added to `registry.py` as each phase adds endpoints.

## Open items / decisions
- D-021: oxlint vs ESLint still unconfirmed (kept oxlint). `/ws/echo/` and `shared.tasks.ping` remain Phase 1 smoke items.
- Dev DB contains the `MOCK demo (random data)` dataset (20,000 rows) for UI work; recreate with `seed_mock_transactions`.

## Exact next steps
1. User approves Phase 3.
2. Phase 4 Task 4.1: upload endpoint + file validation, then preview/mapping, chunked CSV/Excel readers, cleaning, duplicate-ID policy, bulk load (staging + COPY), Celery job with progress + WebSocket, import history/error UI, API ingestion, benchmarks 100k → 1M → 6.36M.

## Resume commands
```
cd "/Users/ajayrazz/Desktop/Django Project/FinGuard"
open -a Docker   # if the daemon is not running
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend pytest -q
docker compose restart backend worker   # Daphne does not auto-reload after code changes
```
