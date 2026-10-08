#!/usr/bin/env bash
set -euo pipefail
umask 077

backup_dir="${ACCOUNTANT_BACKUP_DIR:-/backups}"
retention_days="${ACCOUNTANT_BACKUP_RETENTION_DAYS:-14}"
timestamp="$(date -u +"%Y%m%dT%H%M%SZ")"
mkdir -p "$backup_dir"

database_url="${DATABASE_URL:?DATABASE_URL is required}"
output_path="$backup_dir/accountant_${timestamp}.dump"
partial_path="${output_path}.partial"
trap 'rm -f -- "$partial_path"' EXIT

# Reserve space for an uncompressed database-sized dump plus operating headroom.
database_bytes="$(psql "$database_url" -Atqc 'select pg_database_size(current_database())')"
free_bytes="$(df -Pk "$backup_dir" | awk 'NR == 2 {printf "%.0f\n", $4 * 1024}')"
minimum_free_bytes="${ACCOUNTANT_BACKUP_MIN_FREE_BYTES:-1073741824}"
if [ "$free_bytes" -lt "$((database_bytes + minimum_free_bytes))" ]; then
  echo "backup blocked: insufficient disk headroom" >&2
  exit 1
fi

pg_dump "$database_url" --format=custom --no-owner --file="$partial_path"
pg_restore --list "$partial_path" >/dev/null
mv -- "$partial_path" "$output_path"
(cd "$backup_dir" && sha256sum "$(basename "$output_path")" > "$(basename "$output_path").sha256")
find "$backup_dir" -name "accountant_*.dump" -type f -mtime +"$retention_days" -delete

echo "$output_path"
