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
  cycle_generation="${started_at//:/}-$$-${RANDOM}"
  export ACCOUNTANT_CYCLE_SUMMARY_FILE="$status_dir/automation_cycle_${cycle_generation}.json"
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
  else
    cycle_exit_code=$?
    cycle_status="failed"
    if [ "$cycle_exit_code" -eq 75 ]; then
      echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] storage pause returned; validating cycle evidence" >&2
    else
      echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] automation cycle failed; will retry on the next poll" >&2
    fi
  fi

  finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  # Classify the matching automation JSON, not just its process exit code.
  if ! "$python_bin" scripts/vps_readiness_check.py --record-cycle \
    "$status_dir/scheduler_cycle_status.json" "$ACCOUNTANT_CYCLE_SUMMARY_FILE" \
    "$cycle_exit_code" "$started_at" "$finished_at" "$cycle_generation" \
    > "$status_dir/scheduler_cycle_status.json.partial" || \
    [ ! -s "$status_dir/scheduler_cycle_status.json.partial" ]; then
    # Fail closed even when the status helper itself is unavailable.
    cycle_status="failed"
    printf '{"last_cycle_at":"%s","status":"failed","exit_code":%s,"reason":"status_writer_unavailable","generation":"%s","last_success_at":null}\n' \
      "$finished_at" "$cycle_exit_code" "$cycle_generation" > "$status_dir/scheduler_cycle_status.json.partial"
  fi
  mv -- "$status_dir/scheduler_cycle_status.json.partial" "$status_dir/scheduler_cycle_status.json"
  # The generation-specific scratch summary is already persisted in status.
  # Do not accumulate a second copy on every poll indefinitely.
  rm -f -- "$ACCOUNTANT_CYCLE_SUMMARY_FILE"
  cycle_status="$(sed -n 's/.*"status": *"\([^"]*\)".*/\1/p' "$status_dir/scheduler_cycle_status.json")"
  echo "[$finished_at] accountant automation cycle $cycle_status"
  sleep "$active_interval_seconds"
done
