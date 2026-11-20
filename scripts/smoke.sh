#!/usr/bin/env bash
# Post-deploy smoke test. Usage: CURL_OPTS=-k scripts/smoke.sh https://localhost:8443   (-k only for a local CA)
set -euo pipefail
BASE="${1:?base url}"
C() { curl -fsS ${CURL_OPTS:-} "$@"; }
echo "1. Web app over HTTPS";          C -o /dev/null "$BASE/"
echo "2. Security headers present"
H="$(C -D - -o /dev/null "$BASE/")"
for h in strict-transport-security content-security-policy x-content-type-options x-frame-options; do
  echo "$H" | grep -qi "^$h:" || { echo "missing header: $h"; exit 1; }
done
echo "3. API liveness";                C "$BASE/api/v1/health/" > /dev/null
echo "4. Readiness (database, redis)"; C "$BASE/api/v1/health/ready/" | grep -q '"database": *"ok"'
echo "5. Anonymous API access refused"
test "$(curl -s ${CURL_OPTS:-} -o /dev/null -w '%{http_code}' "$BASE/api/v1/users/")" = 401
echo "6. SPA deep link falls back to the app"
C "$BASE/some/deep/link" | grep -qi "<div id=\"root\""
echo "Smoke test passed."
