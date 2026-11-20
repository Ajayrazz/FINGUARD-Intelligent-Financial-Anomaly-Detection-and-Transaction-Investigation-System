#!/usr/bin/env bash
# Restore a backup made by scripts/backup.sh.
#   scripts/restore.sh <db-dump> <media-tar>             replaces the production database and overlays the media files
#   scripts/restore.sh <db-dump> <media-tar> <database>  restores into a separate scratch database (restore drill)
# The database restore is DESTRUCTIVE for the target database. Media files are extracted over the volume; nothing is
# deleted from it, so files created after the backup stay (they are referenced by hash and harmless).
set -euo pipefail
cd "$(dirname "$0")/.."
DB_DUMP="${1:?db dump file}"; MEDIA_TAR="${2:?media tar file}"; TARGET="${3:-}"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"
STAMP="$(basename "$DB_DUMP" .dump)"; STAMP="${STAMP#db-}"
( cd "$(dirname "$DB_DUMP")" && shasum -a 256 -c "SHA256SUMS-$STAMP.txt" )
if [ -z "${FORCE:-}" ]; then
  read -r -p "This REPLACES data in '${TARGET:-the production database}'. Type 'restore' to continue: " answer
  [ "$answer" = restore ] || exit 1
fi
if [ -n "$TARGET" ]; then
  $COMPOSE exec -T db sh -c "dropdb -U \"\$POSTGRES_USER\" --if-exists '$TARGET' && createdb -U \"\$POSTGRES_USER\" '$TARGET'"
  $COMPOSE exec -T db sh -c "pg_restore -U \"\$POSTGRES_USER\" -d '$TARGET' --no-owner" < "$DB_DUMP"
  echo "Restored into scratch database '$TARGET'."
  exit 0
fi
$COMPOSE stop backend worker beat
$COMPOSE exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < "$DB_DUMP"
$COMPOSE run --rm -T --no-deps backend tar -C /app/media -xf - < "$MEDIA_TAR"
$COMPOSE up -d backend worker beat
echo "Restored. If Neo4j is in use, rebuild the projection: $COMPOSE exec backend python manage.py rebuild_neo4j <dataset-id>  (once per dataset)"
