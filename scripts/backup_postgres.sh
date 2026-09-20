#!/usr/bin/env bash
set -euo pipefail

backup_dir="${ACCOUNTANT_BACKUP_DIR:-/backups}"
retention_days="${ACCOUNTANT_BACKUP_RETENTION_DAYS:-14}"
timestamp="$(date -u +"%Y%m%dT%H%M%SZ")"
mkdir -p "$backup_dir"

database_url="${DATABASE_URL:?DATABASE_URL is required}"
output_path="$backup_dir/accountant_${timestamp}.dump"

pg_dump "$database_url" --format=custom --no-owner --file="$output_path"
find "$backup_dir" -name "accountant_*.dump" -type f -mtime +"$retention_days" -delete

echo "$output_path"
