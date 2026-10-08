#!/usr/bin/env bash
# Restore ONLY into an existing, empty scratch database. No dropdb is used.
set -euo pipefail
umask 077

dump_path="${1:?usage: verify_backup_restore.sh /path/to/accountant_timestamp.dump}"
scratch_url="${ACCOUNTANT_RESTORE_TEST_URL:?provide an isolated scratch database URL}"
scratch_name="$(psql "$scratch_url" -Atqc 'select current_database()')"
case "$scratch_name" in
  accountant_restore_test_*) ;;
  *) echo "restore refused: database name must start with accountant_restore_test_" >&2; exit 1 ;;
esac
table_count="$(psql "$scratch_url" -Atqc "select count(*) from information_schema.tables where table_schema = 'public'")"
if [ "$table_count" -ne 0 ]; then
  echo "restore refused: scratch database must be empty" >&2
  exit 1
fi

(cd "$(dirname "$dump_path")" && sha256sum --check "$(basename "$dump_path").sha256")
pg_restore --list "$dump_path" >/dev/null
pg_restore --exit-on-error --no-owner --no-acl --dbname="$scratch_url" "$dump_path"
psql "$scratch_url" -v ON_ERROR_STOP=1 -c 'select count(*) as companies from companies; select count(*) as filings from filings; select count(*) as raw_facts from raw_facts;'
if [ -n "${DATABASE_URL:-}" ]; then
  for table in companies filings raw_facts; do
    source_count="$(psql "$DATABASE_URL" -Atqc "select count(*) from $table")"
    restored_count="$(psql "$scratch_url" -Atqc "select count(*) from $table")"
    if [ "$source_count" -ne "$restored_count" ]; then
      echo "restore validation failed: row count mismatch for $table" >&2
      exit 1
    fi
  done
fi
date -u +"restore_verified_at=%Y-%m-%dT%H:%M:%SZ" > "${dump_path}.restore_verified"
