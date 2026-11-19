# 14 — Deployment Guide (skeleton; completed in Phases 1 and 16)

## Environments
| | Development | Production |
|---|---|---|
| Compose file | `docker-compose.yml` | `docker-compose.prod.yml` |
| Settings | `config.settings.development` | `config.settings.production` |
| Secrets | `.env` (git-ignored) from `.env.example` | platform secret store / env-file outside repo |
| Services | postgres, redis, neo4j, backend (runserver/daphne), worker, beat, frontend (Vite) | postgres (managed preferred), redis, neo4j, backend (uvicorn/daphne), worker(s), beat, static SPA via reverse proxy |
| TLS | none | Caddy/Nginx with Let's Encrypt, HSTS |

## Required environment variables (will be listed in `.env.example`)
`DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, DATABASE_URL, REDIS_URL, NEO4J_URI/USER/PASSWORD, CORS_ALLOWED_ORIGINS, EMAIL_*, MEDIA_ROOT/S3_*, JWT lifetimes, SENTRY_DSN (optional)`.

## Target choice (D-015)
Render: simplest (managed Postgres/Redis; Neo4j and workers as private services; cost accumulates with memory-heavy workers). AWS: EC2/ECS + RDS + ElastiCache; more control, more work. Neo4j Aura Free is an alternative but has size limits. Decide in Phase 16 using measured memory needs.

## Procedures to be written in Phase 16
Migrations on deploy · seed roles/config · create first Super Admin (management command) · backup/restore drill (`pg_dump`, media volume, Neo4j rebuild) · log access · rollback · scaling workers · demo-data loading.

## Neo4j (Phase 7)
Compose runs `neo4j:5-community` (heap 1 GB, page cache 512 MB; ports bound to 127.0.0.1). Set `NEO4J_PASSWORD` in `.env` (compose refuses to start without it). To use a managed Neo4j Aura instance instead set `NEO4J_TARGET=aura` and `NEO4J_AURA_URI/USERNAME/PASSWORD/DATABASE`; recreate the backend and worker containers so they read the new environment. Aura Free limits (about 200k nodes / 400k relationships) are smaller than the 343k-transaction / 642k-account PaySim slice, so large datasets need the local container or a paid tier. Sync from the UI/API or `python manage.py rebuild_neo4j <dataset_id>`; PostgreSQL remains the source of truth and the projection can always be rebuilt.

## Tesseract (Phase 8)
The backend image installs the `tesseract-ocr` system package (English language data) and the Python packages `pytesseract`, `Pillow`, `pypdfium2` (PDF rendering without Poppler), `rapidfuzz`, `imagehash` and `reportlab` (`requirements/ml.txt`). Uploaded invoices are stored under `MEDIA_ROOT/invoices/` and must live on storage shared by the web and worker containers in production. `INVOICE_MAX_BYTES` (default 10 MB) and `DUPLICATE_MAX_ROWS` (2M) are configurable. Generate demo invoices with `python manage.py generate_synthetic_invoices --email <user>`.
