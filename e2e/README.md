# End-to-end browser tests

Playwright tests run in a real Chromium against an **isolated** stack (own database `finguard_e2e`, own Redis DBs and media), so they never touch development data.

```bash
# once
docker compose exec db psql -U finguard -d finguard -c "CREATE DATABASE finguard_e2e"
cd e2e && npm install && npx playwright install chromium
echo "E2E_PASSWORD=$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')" > .env.local   # git-ignored

# every run
docker compose --profile e2e up -d backend-e2e worker-e2e frontend-e2e
set -a; . ./.env.local; set +a
docker compose --profile e2e exec -T -e E2E_PASSWORD="$E2E_PASSWORD" backend-e2e python manage.py seed_e2e   # users + demo data (idempotent)
npx playwright test            # all
npx playwright test a11y       # accessibility scan only
npx playwright show-report
```

`seed_e2e` refuses to run unless the database name ends in `_e2e` and `DEBUG` is on. The e2e settings (`config.settings.e2e`) relax the login/refresh throttles so the suite can sign in repeatedly; never use them with real data.
