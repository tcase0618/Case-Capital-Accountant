#!/usr/bin/env bash
set -euo pipefail
umask 077

backup_dir="${ACCOUNTANT_BACKUP_DIR:-/backups}"
retention_days="${ACCOUNTANT_BACKUP_RETENTION_DAYS:-14}"
keep_verified="${ACCOUNTANT_BACKUP_KEEP_VERIFIED:-2}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ "$retention_days" =~ ^[0-9]+$ && "$keep_verified" =~ ^[1-9][0-9]*$ ]] || exit 1
timestamp="$(date -u +"%Y%m%dT%H%M%SZ")"
mkdir -p "$backup_dir"

output_path="$backup_dir/accountant_${timestamp}.dump"
partial_path="${output_path}.partial"
last_success_at=""
if [ -f "$backup_dir/last_success_at" ]; then
  read -r last_success_at < "$backup_dir/last_success_at"
fi
error_code="backup_failed"
write_status() {
  local backup_bytes
  backup_bytes="$(du -sk "$backup_dir" | awk '{printf "%.0f", $1 * 1024}')"
  printf '{"last_success_at":"%s","last_error":"%s","backup_bytes":%s}\n' \
    "$last_success_at" "$error_code" "$backup_bytes" > "$backup_dir/status.json.partial"
  mv -- "$backup_dir/status.json.partial" "$backup_dir/status.json"
}
cleanup() {
  local exit_code=$?
  rm -f -- "$partial_path" "${output_path}.counts.partial"
  if [ "$exit_code" -ne 0 ]; then write_status; fi
}
trap cleanup EXIT

# Do not expire archives unless the verified recovery-copy floor is met.
# Select protected copies before deleting anything, regardless of file order.
mapfile -t dumps < <(find "$backup_dir" -maxdepth 1 -type f -name 'accountant_*.dump' | sort -r)
protected_dumps=()
for dump in "${dumps[@]}"; do
  name="$(basename -- "$dump")"
  [[ "$name" =~ ^accountant_[0-9]{8}T[0-9]{6}Z\.dump$ ]] || continue
  if [ "${#protected_dumps[@]}" -lt "$keep_verified" ] && [ -f "$dump.sha256" ] && \
    (cd "$backup_dir" && sha256sum --check "$name.sha256" >/dev/null 2>&1); then
    protected_dumps+=("$dump")
  fi
done
for dump in "${dumps[@]}"; do
  [[ "$(basename -- "$dump")" =~ ^accountant_[0-9]{8}T[0-9]{6}Z\.dump$ ]] || continue
  [ "${#protected_dumps[@]}" -ge "$keep_verified" ] || continue
  protected=false
  for recovery_copy in "${protected_dumps[@]}"; do
    if [ "$dump" = "$recovery_copy" ]; then protected=true; break; fi
  done
  if "$protected"; then continue; fi
  if [ -n "$(find "$dump" -mtime +"$retention_days" -print)" ]; then
    rm -f -- "$dump" "$dump.sha256" "$dump.counts" "$dump.restore_verified"
  fi
done
# Also collect sidecars orphaned by the old retention implementation.
for sidecar in "$backup_dir"/accountant_*.dump.{sha256,counts,restore_verified}; do
  [ -f "$sidecar" ] || continue
  dump="${sidecar%.*}"
  [[ "$(basename -- "$dump")" =~ ^accountant_[0-9]{8}T[0-9]{6}Z\.dump$ ]] || continue
  if [ ! -f "$dump" ]; then rm -f -- "$sidecar"; fi
done

database_url="${DATABASE_URL:?DATABASE_URL is required}"

# Reserve space for an uncompressed database-sized dump plus operating headroom.
database_bytes="$(psql "$database_url" -Atqc 'select pg_database_size(current_database())')"
free_bytes="$(df -Pk "$backup_dir" | awk 'NR == 2 {printf "%.0f\n", $4 * 1024}')"
minimum_free_bytes="${ACCOUNTANT_BACKUP_MIN_FREE_BYTES:-1073741824}"
if [ "$free_bytes" -lt "$((database_bytes + minimum_free_bytes))" ]; then
  echo "backup blocked: insufficient disk headroom" >&2
  error_code="insufficient_disk_headroom"
  exit 1
fi

pg_dump "$database_url" --format=custom --no-owner --file="$partial_path"
pg_restore --list "$partial_path" >/dev/null
# Reading the archive ensures counts describe exactly pg_dump's snapshot.
for table in companies filings raw_facts; do
  count="$(bash "$script_dir/archive_row_count.sh" "$partial_path" "$table")"
  printf '%s\t%s\n' "$table" "$count" >> "${output_path}.counts.partial"
done
mv -- "$partial_path" "$output_path"
mv -- "${output_path}.counts.partial" "${output_path}.counts"
(cd "$backup_dir" && sha256sum "$(basename "$output_path")" "$(basename "$output_path").counts" > "$(basename "$output_path").sha256")
last_success_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
printf '%s\n' "$last_success_at" > "$backup_dir/last_success_at.partial"
mv -- "$backup_dir/last_success_at.partial" "$backup_dir/last_success_at"
error_code=""
write_status

echo "$output_path"
