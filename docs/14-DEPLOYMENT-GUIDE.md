# 14 — Deployment guide

Status: the production stack below was **built and rehearsed locally** (Phase 16, results in §9). It has **not** been deployed to Render or AWS: that needs your account, budget and domain (decision D-015, §7).

## 1. Environments

| | Development | Production |
|---|---|---|
| Compose file | `docker-compose.yml` | `docker-compose.prod.yml` |
| Settings | `config.settings.development` | `config.settings.production` (refuses placeholder/short secrets, SSL redirect, HSTS, secure cookies) |
| Secrets | `.env` | `.env.prod` (git-ignored; template `.env.prod.example`) |
| Web | Vite dev server :5173, Django :8000 | **Caddy** container: serves the built SPA, proxies `/api`, `/ws`, `/admin`, automatic HTTPS, security headers incl. CSP |
| Images | `docker/backend/Dockerfile` (dev tools) | `docker/backend/Dockerfile.prod` (no test tools, non-root user, health check), `docker/caddy/Dockerfile` (multi-stage: builds the SPA) |
| Published ports | db, redis, backend, frontend, neo4j (localhost) | **only** `web` (80/443; configurable) |
| Services | db, redis, neo4j, backend, worker, beat, frontend | db, redis, backend, worker, beat, web (+ `neo4j` with `--profile graph`) |

## 2. Requirements for a host (fresh machine)
Docker Engine 24+ with Compose v2, **≥ 4 GB RAM** (measured idle use: backend ≈ 250 MB, worker ≈ 0.4–1.1 GB while scoring, Postgres ≈ 0.4 GB, Neo4j ≈ 0.9 GB if enabled, beat ≈ 0.3 GB → plan 4 GB without Neo4j, 6 GB with it), 20 GB disk plus your datasets, a DNS name pointing at the host and ports 80/443 open (for real HTTPS).

## 3. First deployment

```bash
git clone <repo> finguard && cd finguard
cp .env.prod.example .env.prod          # then edit it:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # run 3 times: DJANGO_SECRET_KEY, POSTGRES_PASSWORD, NEO4J_PASSWORD
#   SITE_ADDRESS=finguard.example.com  DJANGO_ALLOWED_HOSTS / CORS_ALLOWED_ORIGINS / CSRF_TRUSTED_ORIGINS to that name (https://…)
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod ps          # wait until backend is healthy
FINGUARD_ADMIN_PASSWORD='<strong password>' docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec -e FINGUARD_ADMIN_PASSWORD backend python manage.py create_superadmin --email you@example.com --full-name "Your Name"
CURL_OPTS= scripts/smoke.sh https://finguard.example.com
```
* The backend runs `migrate` on every start; migrations also seed the five roles, their permissions and the default risk configuration. Nothing else has to be seeded.
* Caddy obtains and renews the certificate itself when `SITE_ADDRESS` is a public name reachable on 80/443. For a rehearsal use `SITE_ADDRESS=localhost` (Caddy's local CA; browsers warn, `curl -k` works) and set `HTTP_PORT`/`HTTPS_PORT` (e.g. 8080/8443).
* Sign in as the Super Admin, create the other users in **User Management**.
* **Neo4j is optional** (the graph pages read PostgreSQL). To enable it add `--profile graph` to every compose command, set `NEO4J_URI=bolt://neo4j:7687`, then project a dataset: `exec backend python manage.py rebuild_neo4j <dataset-id>`. For Aura set `NEO4J_TARGET=aura` and the `NEO4J_AURA_*` variables.
* **Model artifacts** are not in git. Copy `datasets/artifacts/` (trained models, hash-verified on load) to the host's `./datasets/artifacts` before using Anomaly Detection; `./datasets` is mounted at `/datasets`. Without artifacts the platform runs but lists no scorable models.
* **Account emails:** self-registration and password reset send email (verification link, reset link, approval notice). Set `FRONTEND_BASE_URL=https://your-domain` (links point there) and the SMTP variables (`EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`) in `.env.prod`, or nobody can finish signing up. The worker sends the mail, so check `docker compose ... logs worker` if emails do not arrive. Test it once with a real address after deploying.
* **Alert email**: set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` and the `EMAIL_*` variables for alert notifications (the default prints to the container log).

## 4. Updating (deploy a new version)
```bash
scripts/backup.sh                                  # always back up first
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
scripts/smoke.sh https://finguard.example.com
```
Migrations apply automatically on the backend start. **Rollback:** check out the previous tag, rebuild, and, if a migration changed the schema, restore the pre-deploy backup (§5). Migrations here are additive (new tables/columns/indexes); none drop data.

## 5. Backup and restore
* **What is backed up:** the PostgreSQL database (`pg_dump --format=custom`) and the uploaded-files volume (case evidence, invoices, import files). **Not** backed up: Neo4j (a rebuildable projection of PostgreSQL), model artifacts (kept in `./datasets`, hash-recorded in the registry), `.env.prod` (store it in your secret manager).
* `scripts/backup.sh [dir]` writes `db-<stamp>.dump`, `media-<stamp>.tar` and `SHA256SUMS-<stamp>.txt`. Run it from cron (e.g. nightly) and copy the files off the host.
* **Restore drill (safe, no downtime):** `FORCE=1 scripts/restore.sh backups/db-<stamp>.dump backups/media-<stamp>.tar finguard_restore_check` restores into a scratch database; compare row counts with production, then drop the scratch database. The result of the last drill is in §9.
* **Real restore:** `scripts/restore.sh <dump> <tar>` stops the app, replaces the database, overlays the media files (nothing is deleted from the volume), restarts. Afterwards rebuild Neo4j if used.
* Retention (NFR-17): keep at least 7 daily and 4 weekly backups; encrypt the off-site copy (the dump contains pseudonymous account ids and case notes). Uploaded evidence and imports are kept until a Super Admin removes them; there is no automatic deletion.

## 6. Operations
* **Logs:** `docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f backend worker beat web` (structured JSON with request ids). Audit trail: **Audit Logs** page.
* **Health:** `/api/v1/health/` (liveness), `/api/v1/health/ready/` (database, redis; Neo4j reported when configured). The backend container has a Docker health check; `web` waits for it.
* **Scaling workers:** `docker compose … up -d --scale worker=3` (each runs 4 processes; mind Postgres `max_connections=250`).
* **Rollup refresh:** the `beat` service rebuilds the analytics rollup hourly; Analytics → *Rebuild rollup* does it on demand.
* **Rotate the secret key:** changing `DJANGO_SECRET_KEY` signs everyone out (JWTs are invalidated); restart backend, worker and beat.
* **Admin site** `/admin/` is available to superusers over HTTPS only; day-to-day administration uses the app.

## 7. Choosing a hosting target (D-015)
Measured needs: ≈ 4 GB RAM (6 GB with Neo4j), 2 vCPUs, ~1.3 GB of images, Postgres data ≈ 1 GB per 350k transactions plus indexes (the dev database holds 363k transactions in roughly that range).
| Option | Fit | Notes (not tested here) |
|---|---|---|
| **Single VM + this Compose file** (any provider: a 4 GB/2 vCPU instance) | **Recommended for the project/demo**: identical to what was rehearsed, one bill, Caddy handles HTTPS | You own patching and backups |
| Render | Possible: web service from `docker/backend/Dockerfile.prod`, background worker, cron for beat, managed Postgres and Redis, static site for the SPA with rewrites | Needs a blueprint (`render.yaml`) not written here; the worker needs ≥ 2 GB; ML artifacts need a persistent disk |
| AWS (ECS/EC2 + RDS + ElastiCache) | Most control and cost | Most work; not attempted |
No cloud deployment was performed; the decision needs your budget and account.

## 8. Required environment variables
`SITE_ADDRESS, HTTP_PORT, HTTPS_PORT, DJANGO_ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS, CSRF_TRUSTED_ORIGINS, DJANGO_SECRET_KEY (≥ 32 random chars), POSTGRES_DB/USER/PASSWORD/HOST/PORT, REDIS_URL, NEO4J_TARGET/URI/USER/PASSWORD (optional), FINGUARD_DATASETS_DIR, EMAIL_* (optional)`. The app refuses to start in production with a short or placeholder secret.

## 9. Rehearsal record (2026-11-20, one machine, `SITE_ADDRESS=localhost`, ports 8080/8443, Docker Desktop on macOS/arm64)
Followed §3 literally: generated secrets into `.env.prod`, `up -d --build`, `create_superadmin`, `scripts/smoke.sh`. Measured and found:
* **Image build:** ~12 minutes cold (the ML wheels incl. torch and CUDA libraries dominate; a CPU-only torch pin would shrink the image, not done). Services reach healthy in ~45 s.
* **Smoke test:** passed (HTTPS app, 4 security headers, liveness, readiness, anonymous API → 401, SPA deep-link fallback).
* **Real browser over HTTPS** (Playwright, Caddy's local CA): landing → sign in → dashboard, Analytics, Users, Audit, Models render; **no console errors and no CSP violations**; refresh cookie is `Secure; HttpOnly; SameSite=Strict`.
* **Backup/restore drill:** 481 transactions, 183 accounts, 2 datasets in a fresh production database; backup 0.3 s (276 KB dump + 10 KB media archive, SHA-256 file); restore into a scratch database matched exactly; after adding a dataset post-backup, a **real restore** (4.3 s) removed it and matched the backup again; the app was healthy and the smoke test passed afterwards. Scale caveat: this is a tiny database; time grows with data.
* **Defects found by the rehearsal and fixed:** (1) the non-root backend could not write the shared static-files volume, so the stack never became healthy; (2) with no `.dockerignore` the image contained 185 MB of development uploads (the media archive was 193 MB), now excluded; (3) the 3D charts failed under the strict CSP because echarts-gl builds shaders with `new Function`; fixed with a build-time patch of that one parser (D-104), covered by unit tests and checked in the production bundle (no `new Function` left).
* **Not tested here:** a public DNS name with real Let's Encrypt issuance, a cloud host, Neo4j in the production profile, SMTP delivery, scaling workers, behaviour under real traffic.
