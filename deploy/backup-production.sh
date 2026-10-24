#!/usr/bin/env bash
set -euo pipefail

umask 077
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
backup_root="${AI_COMPANION_BACKUP_DIR:-/home/appadmin/ai-companion-backups}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p -- "$backup_root"
pending_dir="$(mktemp -d "$backup_root/.pending-XXXXXXXX")"
cd -- "$project_dir"

docker compose --env-file .env.production -f compose.production.yml exec -T db \
  pg_dump -U ai_companion -d ai_companion -Fc > "$pending_dir/database.dump"
docker compose --env-file .env.production -f compose.production.yml exec -T api \
  tar -czf - -C /app/data . > "$pending_dir/app_data.tar.gz"
docker compose --env-file .env.production -f compose.production.yml exec -T db \
  pg_restore -l < "$pending_dir/database.dump" > /dev/null
tar -tzf "$pending_dir/app_data.tar.gz" > /dev/null
git rev-parse HEAD > "$pending_dir/commit.txt"
(cd -- "$pending_dir" && sha256sum database.dump app_data.tar.gz commit.txt > SHA256SUMS)

snapshot_dir="$backup_root/$stamp"
mv -- "$pending_dir" "$snapshot_dir"
printf 'Backup ready: %s\n' "$snapshot_dir"
