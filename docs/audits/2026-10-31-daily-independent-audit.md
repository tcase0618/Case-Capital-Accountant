# Accountant Daily Independent Audit — 2026-10-31

- Audit time: 2026-10-31 02:51–03:20 EDT (America/New_York, UTC−4), Saturday. Daily routine, run 24. Previous audit: 2026-10-30 02:53 EDT.
- EDGAR calendar: weekend (no filings accepted today). A bounded read of the SEC `daily-index/2026/QTR4/index.json` at ≈06:58Z shows `master.20261030.idx` as newest. DST ends Sun 2026-11-01 (next audit at UTC−5).
- Repository: `main` @ **`7bf2012`**, unchanged since 10-28 (third audit on this SHA). Working branch `claude/charming-hopper-ec94cs` = `7bf2012` before this artifact; worktree clean.
- `Claude-Gpt-audit` moved `a096821` → **`97d3c5d`** (2026-10-30 23:51 EDT, "coalesce public source integrity scans"). 17 ahead / 14 behind `main`; not promoted.
- Deployed commit: SHA **UNVERIFIED** (no SSH/DB; no endpoint exposes it). Deployed behaviour still matches `7bf2012`; API process start unchanged at 2026-10-28T14:11:13Z.
- Scope: **REPOSITORY + LIMITED LIVE**. Read-only, unauthenticated public GETs over HTTP: `/health`, `/api/reports/status` (×2, 74 s apart), `/api/deployment/readiness` (×2), `/api/cache/status`, `/api/buy-board/status`, `/openapi.json`. No token, no mutation.
- Tools: git, uv + Python 3.11 venv, curl. No Docker daemon, SSH, DB, logs or GitHub Actions API.

## 1. Operational verdict

**DEGRADED (live-confirmed).** The pipeline is still halted at the database cap: ≈8.4 days since 10-22T20:51Z, and `processed_cycles=0` since the 10-28 restart.
- Research-only readiness: **not ready**. Failing gates: `machine_running`, `source_integrity=FAILED`, `blocked_companies`, `stability_window`.
- Execution is prohibited by design (`execution_allowed=false`, `terminal_handoff_allowed=false`); verified live.

## 2. Dashboard

| Metric | Value | Evidence |
|---|---|---|
| Liveness | `/health` 200 in 0.06 s | 06:52:35Z |
| Report machine | `running=true`, `processed_cycles=0`, `last_cycle_at=null`, `storage_blocked=true` (`database_cap_reached`) | 06:52:35Z, 06:53:49Z |
| Reports persisted | **2,134 / 4,473** (47.7%), the same since 10-28 on the same endpoint | |
| Throughput | **0 net new reports in 74 s**; no completion events, so companies/min cannot be computed | 2 samples |
| Pending | report machine `pending_companies=0` (MED-021 remainder); cache warmer "deferred … (2339 pending)" | |
| Workers | all 8 roles `standby`, ticker null; the cause is the storage block, not an empty queue | |
| Freshness | newest SEC index 10-30; newest processed filing 10-22 (operator record); **6 EDGAR business days unprocessed** (10-23, 26, 27, 28, 29, 30) | |
| Storage | DB 14.91 GB vs a 14 GiB cap; 28.84 GB free (operator record 10-28; not re-measured). WAL, logs and backups UNVERIFIED | |
| Buy board | "degraded buy board (0/127 quotes)", `quote_refresh_incomplete`, last refresh 10-30T20:00Z. **`next_refresh_at=2026-10-31T13:30Z` (Saturday)**, new LOW-015 | |
| Readiness latency | **6.78 s, 3.55 s** (MED-022 still live; fix not deployed) | 06:52:42Z, 06:52:46Z |
| TLS | HTTPS :443 gives no response (MED-010) | |
| Backup/restore | no new evidence | |

## 3. New findings

### ACC-LOW-015 — Buy-board scheduler refreshes quotes on weekends and market holidays
- Severity Low · CONFIRMED (source + live) · Open
- Evidence: `src/accountant/research/buy_board.py:737-746` (`_next_refresh_time`) always returns tomorrow 09:30 ET after the close, with no weekday or holiday check. The `_run` loop at `:667-680` then refreshes. Live: `/api/buy-board/status` at 06:52:46Z (Saturday) reports `next_refresh_at=2026-10-31T13:30:00Z`.
- Consequence: Saturday, Sunday and holiday refreshes spend outbound quote calls (MED-010) and stamp `last_refresh_at` with a non-session time. Prior-session prices then look like a fresh scheduled refresh, and a weekend failure overwrites Friday's status.
- Repair: skip non-session days with an exchange calendar (weekends + NYSE holidays; early closes at 13:00), and label the snapshot with the session date.
- Acceptance: `_next_refresh_time(Fri 16:01 ET)` returns Mon 09:30 ET, and `_next_refresh_time` on the day before a holiday skips that holiday.
- Test: parametrized unit test across Fri→Mon, the US Thanksgiving 2026-11-26 holiday and DST end 2026-11-01.

## 4. Prior findings — status changes

| ID | Change | Evidence |
|---|---|---|
| ACC-MED-022 | Open → **Partially addressed (remediation branch only; not on main; not deployed)** | `97d3c5d`: `source_integrity.py` adds a single-flight, engine-scoped 30 s TTL cache (`SourceIntegrityCache`). Failures are not cached, and the cache is aliased into `app.py` for both public routes. `tests/test_oct30_source_cache.py` (3 tests) passes in the branch run. Live readiness still takes 6.78 s / 3.55 s. Residual: cache misses still run exact `count(*)` scans; the cache is per process. |
| ACC-CRIT-001 | Open, live re-confirmed | halt ≈8.4 days; 6 EDGAR business days unprocessed |
| ACC-MED-010 | Open, live re-confirmed | no HTTPS; `/openapi.json` 200 publicly |
| ACC-MED-021 | Partially addressed, remainder re-confirmed | `pending_companies=0` while the cache warmer reports 2,339 pending |
| ACC-LOW-014 | Partially addressed, remainder re-confirmed | 0/127 quotes; 127 counted while the list is empty |

Totals: **47 items** (Critical 1, High 9, Medium 22, Low 15) · CONFIRMED 27, SUSPECTED 4, UNVERIFIED 0, RESOLVED 16.

## 5. Tests (offline, Python 3.11, `ACCOUNTANT_ENV=test`)

| Target | Command | Result |
|---|---|---|
| `main` @ 7bf2012 | `uv sync --frozen --all-extras` then `uv run pytest -p no:cacheprovider -o addopts="" -q` | exit 0; **566 passed / 0 failed / 0 skipped**, 1 warning (Starlette TestClient) |
| `main` | `uv run ruff check src tests` | All checks passed (scripts/ out of scope, LOW-005) |
| `main` | `uv run python scripts/check_mypy_baseline.py` | 236 existing errors, no new (not type-clean) |
| `Claude-Gpt-audit` @ 97d3c5d | same pytest (worktree) | exit 0; **535 passed**, 1 warning (branch is 14 commits behind main, hence the lower count) |

Note: a plain `uv sync --frozen` omits the `dev` extra, so the first attempt failed at conftest import (`sqlalchemy` missing in that minimal env). The results above are from the corrected run.

Not run: Docker build/compose (no daemon), coverage, restore test, alembic drift, authenticated endpoints, logs, DB size/WAL, CI API.

## 6. Next actions

1. **Urgent operations — CRIT-001.** An operator capacity decision plus a capacity-safe catch-up. Six EDGAR business days are now unprocessed; the backlog will grow on Monday.
2. **Recovery — HIGH-009 / MED-005.** A scheduled systemd backup with an off-host copy and one isolated restore, required before any archival that frees space.
3. **Promote MED-022 cache** (after review against main's 14 newer commits) to stop anonymous full-table scans on the capped DB; then MED-021 status truthfulness.

## 7. Not run / blocked

SSH, database, logs, WAL, disk, deployed SHA, authenticated routes and backup inventory are BLOCKED: no credentials are provisioned to this routine. Scoring/valuation recomputation on live samples is BLOCKED (no DB; packets not accepted). The cause of the 0/127 quote failures is UNVERIFIED.
