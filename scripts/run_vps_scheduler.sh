#!/usr/bin/env bash
set -euo pipefail

poll_windows="${ACCOUNTANT_POLL_WINDOWS:-06:00-09:30,16:00-22:00}"
active_interval_seconds="${ACCOUNTANT_ACTIVE_POLL_INTERVAL_SECONDS:-900}"

while true; do
  sleep_seconds="$(python scripts/scheduler_timing.py \
    --windows "$poll_windows" \
    --active-interval-seconds "$active_interval_seconds")"
  if [ "$sleep_seconds" -gt 0 ]; then
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] scheduler sleeping ${sleep_seconds}s until the next SEC poll"
    sleep "$sleep_seconds"
  fi

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
  echo "[$finished_at] accountant automation cycle complete"
done
