#!/usr/bin/env bash
# Back up the production database and uploaded files. Usage: scripts/backup.sh [output-dir]
# Neo4j is not backed up: it is a rebuildable projection (manage.py rebuild_neo4j). Model artifacts live in ./datasets.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"
echo "Dumping PostgreSQL..."
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' > "$OUT/db-$STAMP.dump"
echo "Archiving uploaded files (media volume)..."
$COMPOSE exec -T backend tar -C /app/media -cf - . > "$OUT/media-$STAMP.tar"
( cd "$OUT" && shasum -a 256 "db-$STAMP.dump" "media-$STAMP.tar" > "SHA256SUMS-$STAMP.txt" )
echo "Done: $OUT/db-$STAMP.dump, $OUT/media-$STAMP.tar (+ SHA256SUMS-$STAMP.txt)"
