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
