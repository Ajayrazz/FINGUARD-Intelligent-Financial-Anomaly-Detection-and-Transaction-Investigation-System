# 13 — Testing Strategy

No claim of "tests passed" without actually running them and reading output (Part 8.5).

| Layer | Tooling | Scope |
|---|---|---|
| Backend unit | pytest, pytest-django, factory_boy | domain logic, services, risk math, state machine, normalisers |
| API | DRF `APIClient` | every endpoint: success, validation, 401/403/404/409, pagination/filter |
| RBAC | generated test iterating registry of endpoints × 5 roles vs matrix | prevents silent permission regressions |
| Database | pytest-django with real Postgres (Compose) | constraints, indexes (EXPLAIN checks), migrations apply/rollback, append-only audit |
| Tasks | Celery eager for logic; real worker integration test | import, detection, graph, OCR, PDF, email |
| ML | pytest + small fixtures | determinism with seed, schema check, **leakage perturbation tests**, artifact hash/round-trip, metric sanity (e.g., all-negative predictor gets ~0 PR-AUC) |
| Graph | pytest with planted graphs | cycle/chain/fan-in detection, as-of correctness, Neo4j sync idempotency, rebuild equivalence |
| OCR/duplicates | synthetic invoice set | Tesseract really invoked; classification of exact/strong/potential/legit-repeat |
| Frontend | Vitest + Testing Library; Playwright E2E | components, route guards, forms, role journeys |
| Security | pytest + manual checklist | IDOR, mass-assignment, upload abuse, CSV injection, throttling, token rotation/blacklist |
| Performance | locust/scripts, `pg_stat_statements`, timing harness | import throughput, list latency, inference latency/throughput, graph build time |
| Static | ruff, mypy, import-linter, ESLint, `tsc --strict` | CI gate |

**Per-task loop:** write tests → run → inspect failures → fix → re-run → document. Test names are recorded in the traceability matrix "Tests" column when written.
**Fixtures:** all mock data lives in `tests/fixtures/` and is labelled; production code paths never read it.
**Coverage goal:** ≥ 80% on services/domain/ml_engine/graph lib; reported, not gamed.

## How to run everything (verified Phase 15)
* Backend: `docker compose exec backend python -m pytest tests -q` (add `--cov=apps --cov=graph_engine_lib --cov=duplicates_lib --cov=risk_engine_lib --cov=ml_engine --cov=shared --cov-report=term` for coverage); `ruff check .`; `mypy .`.
* Frontend: `npm run lint`, `npx tsc -b` (plain `tsc --noEmit` checks nothing here: the root tsconfig has no files), `npm test`, `npx vite build`.
* Browser E2E: see `e2e/README.md` (isolated `e2e` Compose profile, seeded users, 27 specs).
* Security checks: `tests/test_security.py` (mapped to OWASP in doc 20); N+1 guard: `tests/test_query_counts.py`; latency: `python manage.py benchmark_api`.
