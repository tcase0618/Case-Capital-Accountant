#!/usr/bin/env bash
set -euo pipefail

poll_windows="${ACCOUNTANT_POLL_WINDOWS:-06:00-09:30,16:00-22:00}"
active_interval_seconds="${ACCOUNTANT_ACTIVE_POLL_INTERVAL_SECONDS:-900}"
python_bin="${ACCOUNTANT_PYTHON_BIN:-.venv/bin/python}"
status_dir="${DATA_DIR:-data}"
mkdir -p "$status_dir"

while true; do
  sleep_seconds="$("$python_bin" scripts/scheduler_timing.py \
    --windows "$poll_windows" \
    --active-interval-seconds "$active_interval_seconds")"
  if [ "$sleep_seconds" -gt 0 ]; then
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] scheduler sleeping ${sleep_seconds}s until the next SEC poll"
    sleep "$sleep_seconds"
    continue
  fi

  started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "[$started_at] accountant automation cycle starting"

  if "$python_bin" scripts/run_accountant_automation.py \
    --import-workers "${ACCOUNTANT_IMPORT_WORKERS:-4}" \
    --refresh-workers "${ACCOUNTANT_REFRESH_WORKERS:-4}" \
    --score-workers "${ACCOUNTANT_SCORE_WORKERS:-2}" \
    ${ACCOUNTANT_SKIP_IMPORT:+--skip-import} \
    ${ACCOUNTANT_SKIP_STALE_REFRESH:+--skip-stale-refresh} \
    ${ACCOUNTANT_REFRESH_ALL_SCORES:+--refresh-all-scores}; then
    cycle_status="complete"
    cycle_exit_code=0
    cycle_reason="none"
  else
    cycle_exit_code=$?
    if [ "$cycle_exit_code" -eq 75 ]; then
      cycle_status="paused_storage"
      cycle_reason="storage_budget_exhausted"
    else
      cycle_status="failed"
      cycle_reason="automation_error"
    fi
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] automation cycle $cycle_status; will retry on the next poll" >&2
  fi

  finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  printf '{"last_cycle_at":"%s","status":"%s","exit_code":%s,"reason":"%s"}\n' \
    "$finished_at" "$cycle_status" "$cycle_exit_code" "$cycle_reason" > "$status_dir/scheduler_cycle_status.json.partial"
  mv -- "$status_dir/scheduler_cycle_status.json.partial" "$status_dir/scheduler_cycle_status.json"
  echo "[$finished_at] accountant automation cycle $cycle_status"
  sleep "$active_interval_seconds"
done
