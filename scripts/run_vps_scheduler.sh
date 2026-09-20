#!/usr/bin/env bash
set -euo pipefail

interval_seconds="${ACCOUNTANT_AUTOMATION_INTERVAL_SECONDS:-21600}"

while true; do
  started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "[$started_at] accountant automation cycle starting"

  python scripts/run_accountant_automation.py \
    --import-workers "${ACCOUNTANT_IMPORT_WORKERS:-4}" \
    --refresh-workers "${ACCOUNTANT_REFRESH_WORKERS:-4}" \
    --score-workers "${ACCOUNTANT_SCORE_WORKERS:-2}" \
    ${ACCOUNTANT_SKIP_IMPORT:+--skip-import} \
    ${ACCOUNTANT_SKIP_STALE_REFRESH:+--skip-stale-refresh} \
    ${ACCOUNTANT_REFRESH_ALL_SCORES:+--refresh-all-scores}

  finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "[$finished_at] accountant automation cycle complete; sleeping ${interval_seconds}s"
  sleep "$interval_seconds"
done
