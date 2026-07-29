#!/usr/bin/env bash
# Nightly database dump. Point BACKUP_DIR at whatever your existing backup job
# already picks up, then add a cron entry such as:
#   30 2 * * * /mnt/docker-storage/compose/kolektor/deploy/backup.sh
set -euo pipefail

STACK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${KOLEKTOR_BACKUP_DIR:-/mnt/immich-backup/kolektor}"
KEEP_DAYS="${KOLEKTOR_BACKUP_KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
stamp="$(date +%Y%m%d-%H%M)"
target="$BACKUP_DIR/kolektor-$stamp.sql.gz"

docker exec kolektor-db pg_dump -U "${POSTGRES_USER:-kolektor}" -d "${POSTGRES_DB:-kolektor}" \
    | gzip -9 > "$target"

# Media lives on disk; a manifest keeps restores honest without duplicating gigabytes.
find "$STACK_DIR/media" -type f -printf '%P\t%s\n' 2>/dev/null | gzip -9 \
    > "$BACKUP_DIR/kolektor-media-$stamp.manifest.gz" || true

find "$BACKUP_DIR" -name 'kolektor-*.gz' -mtime "+$KEEP_DAYS" -delete

echo "Wrote $target ($(du -h "$target" | cut -f1))"
