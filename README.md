# FinGuard

Intelligent financial anomaly detection and transaction investigation platform (ML + graph analytics + Explainable AI). Academic prototype using public/synthetic data only. Start with [docs/00-PROJECT-OVERVIEW.md](docs/00-PROJECT-OVERVIEW.md); current status in [docs/16-PROGRESS-TRACKER.md](docs/16-PROGRESS-TRACKER.md).

## Development quick start (Docker required)
```bash
cp .env.example .env          # then replace the change-me values
docker compose up -d --build  # db, redis, backend (8000), worker, frontend (5173)
```
- Frontend: http://localhost:5173 (shows live dependency status)
- API docs: http://localhost:8000/api/docs/ · health: `/api/v1/health/`, `/api/v1/health/ready/`

## Checks
```bash
docker compose exec backend ruff check .
docker compose exec backend mypy .
docker compose exec backend pytest -q
docker compose exec frontend sh -c "npx tsc -b && npm run lint && npm test"
```
Dependencies: loose ranges in `backend/requirements/*.txt`, resolved versions pinned in `constraints.txt`. All development runs in containers (Python 3.12, Node 22) — see decision D-002.
