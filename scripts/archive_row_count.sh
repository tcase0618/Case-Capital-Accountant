#!/usr/bin/env bash
# Counts come from COPY records in the immutable dump, never the live source.
set -euo pipefail
dump_path="${1:?dump required}"
table="${2:?table required}"
case "$table" in companies|filings|raw_facts) ;; *) exit 1 ;; esac
pg_restore --data-only --table="$table" --file=- "$dump_path" | awk '
  /^COPY .* FROM stdin;$/ { copying=1; seen++; next }
  copying && $0 == "\\." { copying=0; next }
  copying { count++ }
  END { if (seen != 1 || copying) exit 1; print count+0 }
'
