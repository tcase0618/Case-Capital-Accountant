# Accountant Daily Independent Audit — 2026-10-28

- Audit time: 2026-10-28 02:52–03:20 EDT (America/New_York, UTC−4), Wednesday. Daily routine, run 21.
- EDGAR calendar: business day. One bounded read of the public SEC `daily-index/2026/QTR4/index.json` at 03:02 EDT shows `master.20261027.idx` as the newest index. Today's (10-28) index is not yet published, so ACC-MED-020 recurrence is expected. US DST ends Sun 2026-11-01.
- Repository: `main` @ `deec292` (unchanged since 2026-10-22; sixth consecutive audit on this SHA). Working branch `claude/charming-hopper-0qcqaw` = `deec292` before this artifact. Worktree clean.
- Other branches: `Claude-Gpt-audit` moved `da3dbd0` → `e1fe8b0` (2026-10-27 22:03 EDT, "enforce storage and health readiness safeguards"). It is 15 ahead / 13 behind `main`, and its CI run 40618678025 is green. It is **not promoted** to `main`.
- Deployed commit: **UNVERIFIED**. There is no SSH or database access, and no public endpoint reports the commit.
- Scope: **REPOSITORY + LIMITED LIVE (read-only, unauthenticated public GETs)**. This is the first audit with live evidence since 2026-10-22. Host `129.121.138.129` (from `docs/audits/2026-10-22-readiness-hardening.md`), plain HTTP on port 80. Endpoints read: `/health`, `/api/deployment/readiness`, `/api/reports/status`, `/api/cache/status`, `/api/buy-board/status`, `/api/buy-board`. No mutation request was made and no token was used.
- Tools: git, uv with a Python 3.11 venv, isolated scratch PostgreSQL 16 (non-production), GitHub Actions API (read-only), curl. The Docker CLI is present but there is no daemon.

## 1. Operational verdict

**DEGRADED (live-confirmed).** The research pipeline has been halted at the database cap for at least 5 days.
- Research-only readiness: **not ready**. The readiness gates `source_integrity=FAILED` and `stability_window` are not met, and `ready_for_next_phase=false`.
- Execution is prohibited by design (`execution_allowed=false`, `terminal_handoff_allowed=false`), and this was verified live.

## 2. Dashboard

| Metric | Value | Evidence |
|---|---|---|
| Liveness | `/health` = `{"status":"ok"}` (HTTP 200) | 07:00Z |
| Report machine | `running=true`, started 2026-10-22T20:51:32Z, `processed_cycles=0`, `last_cycle_at=null`, `last_action="storage gate blocked: database_cap_reached"` | `/api/reports/status`, 07:01:10Z / 07:01:49Z / 07:02:07Z / 07:03:34Z |
| Reports persisted | **2,134 of 4,473** companies (47.7%) | same endpoint; the 10-22 operator note said 2,126 (a different collection method, so only roughly comparable) |
| Throughput | **0 net new reports in 144 s** (07:01:10Z → 07:03:34Z). No distinct-company completion events exist, because zero cycles have run since API start | 4 samples |
| Pending | `pending_companies=0`, `runnable=0`, `blocked=0` on the report machine (**misleading**; see MED-021). The cache warmer on the same API reports "deferred until report backlog drains (2339 pending)" | `/api/cache/status` |
| Workers | all 8 roles `standby`, ticker null. The cause is the storage block, not an empty queue | `/api/reports/status` |
| Storage | `storage_blocked=true`, `database_cap_reached`. DB size / disk / WAL are UNVERIFIED (no DB/SSH access) | |
| Freshness | newest SEC index 2026-10-27. Newest processed accepted_at UNVERIFIED, but no ingest cycle has run since 10-22 | |
| Buy board | status `candidate_count=127`, last refresh 2026-10-27T20:00Z "refreshed buy board (0 quotes)", `last_success_count=0`, `last_error=null`. `/api/buy-board` returns `[]` (all 127 rows are quarantined legacy rows) | see LOW-014 |
| Backup / restore | no new evidence. Last record: one off-host 1.64 GB snapshot, checksum only; partial raw_facts archive restore on 10-22 | operator note |

## 3. New or regressed findings

### ACC-MED-021 — Storage-blocked report machine reports an empty queue, and readiness counts it as "running" (NEW, CONFIRMED)
- Evidence (code):
  - `src/accountant/research/report_machine.py:323-337`. The storage-blocked branch of `_run_cycle` refreshes only `reports_cached`/`total_companies` and returns before `_refresh_progress_snapshot` (`:1017`). `pending_companies`, `runnable_companies` and `blocked_companies` therefore stay at their default 0.
  - `src/accountant/api/app.py:1416`. The `machine_running` readiness gate passes on `bool(machine.get("running"))` alone.
- Evidence (live, 07:01–07:03Z): `pending_companies=0, runnable_companies=0, blocked_companies=0, processed_cycles=0, storage_blocked=true`. `/api/deployment/readiness` gate `machine_running: passed=true` with detail "storage gate blocked: database_cap_reached". `/api/cache/status` simultaneously says 2,339 pending.
- Consequence: a dashboard or monitor reading the report machine sees "queue drained / running" during a 5-day halt. The `blocked_companies` gate also passes. This hides ACC-CRIT-001 from any automated check that does not parse `last_action`.
- Repair: compute the backlog (a read-only count) in the storage-blocked branch, or publish `pending=null` with `state="paused_storage"`. Fail `machine_running` when `storage_blocked` is true or when `processed_cycles==0` beyond a grace window.
- Acceptance test: a unit test with a storage preflight returning `allowed=False` and N companies without reports. It should assert `pending_companies==N` (or null with an explicit paused state) and `machine_running.passed is False`. Live: readiness reports the gate failed while `storage_blocked=true`.

### ACC-LOW-014 — Buy-board refresh reports success with 0/127 quotes; status counts quarantined rows the list hides (NEW, CONFIRMED; quote-failure cause UNVERIFIED)
- Evidence:
  - `src/accountant/research/buy_board.py:449-458`: per-candidate failures go only to row `last_price_error`.
  - `:713-718`: the snapshot `last_action="refreshed buy board (N quotes)"` and `last_error=None` regardless of `successes`.
  - `:594-599`: `candidate_count` counts all ACTIVE rows.
  - `src/accountant/api/app.py:1896` filters to validated reports only.
  - Live: 127 candidates, 0 successes at 2026-10-27T20:00Z, `last_error=null`. `/api/buy-board` = `[]`.
- Consequence: a total market-data outage (or a credential rejection) looks healthy. External quote calls are spent on 127 quarantined rows nobody can see.
- Repair: set `last_error`/degraded status when `successes < candidate_count`. Count and refresh only candidates whose report passes `_validated_report`.
- Acceptance test: a fake `alpaca_quote` returning `ok=False` for all rows gives `last_error` non-null and a degraded state. A quarantined candidate is not quoted or counted.

## 4. Prior findings

- **ACC-CRIT-001 — re-confirmed LIVE.** The storage gate (`database_cap_reached`) has blocked every cycle since the API started at 2026-10-22T20:51Z. Zero cycles, 2,134/4,473 reports, and roughly 2,339 companies pending per the cache warmer. Status: Open.
- **ACC-MED-010 — live evidence added.** The API is publicly reachable over plain HTTP (`http://<accountant-host>/health` → 200 via port 80). Port 443 returned 503 on one attempt and then failed. TLS is not served. Port 8000 is not publicly reachable. Status: Open.
- **ACC-MED-014 — re-reproduced.** On a fresh scratch PG16, `alembic upgrade head` exit 0 (→011) and `alembic check` exit 255. It reports added tables `buy_board_candidates`, `buy_board_snapshots`, `company_reports`, `report_cards` plus 24 indexes.
- **ACC-LOW-012** (storage limits default to 0) → **Partially addressed on `Claude-Gpt-audit` only**. At `e1fe8b0`, a `config.py` `model_validator` rejects missing, zero, negative or non-finite limits in production.
  - Precondition: the production env must set all three limits before deployment, or startup fails. HIGH-003 noted the cycle-growth cap may be 0 in production.
- **ACC-LOW-013** (unknown `/health/*` serves the SPA) → **Partially addressed on `Claude-Gpt-audit` only**: `e1fe8b0`, `app.py` first-segment check including `health`.
- **ACC-HIGH-003** — branch `e1fe8b0` also adds the worker reserve to `run_accountant_automation.py` preflight and an exit-75 `paused_storage` status. Mid-cycle overshoot is still unaddressed. Status: Open (branch progress noted).
- **ACC-MED-020** — today's index is unpublished at audit time, so recurrence is expected. It is not observable without logs.
- All other items are unchanged. The source on `main` is byte-identical to 10-22. RESOLVED stays at 13 (repository level).

Totals: **45 items** (Critical 1, High 9, Medium 21, Low 14) · CONFIRMED 28, SUSPECTED 4, UNVERIFIED 0, RESOLVED 13.

## 5. Tests (main @ deec292, Python 3.11, `ACCOUNTANT_ENV=test`, offline)

| Command | Result |
|---|---|
| `uv sync --extra dev`; `uv run --extra dev pytest -p no:cacheprovider -rs` | exit 0; **526 passed / 0 failed / 0 skipped**, 1 warning (Starlette TestClient deprecation) |
| `uv run --extra dev ruff check src tests` | All checks passed. (`ruff check .` over scripts too reports 12 errors; CI gates `src tests` only — see LOW-005) |
| `uv run --extra dev python scripts/check_mypy_baseline.py` | 236 existing errors, no new diagnostics (not type-clean) |
| `alembic upgrade head` / `alembic check` (scratch PG16) | 0 / 255 (MED-014) |
| `Claude-Gpt-audit` @ e1fe8b0 pytest | exit 0, 524 passed |

Not run: Docker build/compose (no daemon), coverage, restore test, authenticated endpoints, logs, DB size/WAL.

## 6. Next actions

1. **Urgent operations — CRIT-001.** Make a capacity decision and run a capacity-safe catch-up. Verify the report count rises across two samples at least 60 s apart, using the same public `/api/reports/status`.
2. **Status truthfulness — MED-021.** Make the paused state visible to monitors, so the next halt is caught automatically rather than by a daily audit.
3. **Recovery — HIGH-009 / MED-005.** Set up a scheduled systemd backup with an off-host copy, and complete one isolated full restore.

## 7. Not run / blocked

- SSH, database, logs, WAL, disk, deployed SHA, authenticated routes, and backup inventory: BLOCKED (no credentials provisioned to this routine).
- Scoring and valuation recomputation on live samples: BLOCKED. Packets are `accepted=false` and there is no DB access.
- TLS: the HTTPS attempt failed through the agent proxy, so it is treated as "not served" (UNVERIFIED beyond that single attempt).
