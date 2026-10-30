# Accountant Daily Independent Audit — 2026-10-30

- Audit time: 2026-10-30 02:53–03:25 EDT (America/New_York, UTC−4), Friday. Daily routine, run 23.
- EDGAR calendar: business day. A bounded read of the public SEC `daily-index/2026/QTR4/index.json` at 02:57 EDT shows `master.20261029.idx` as newest; today's index not yet published. US DST ends Sun 2026-11-01 (next audit at UTC−5).
- Repository: `main` @ **`7bf2012`**, unchanged since 10-28 (second audit on this SHA). Working branch `claude/charming-hopper-a2qic8` = `7bf2012` before this artifact; worktree clean. `Claude-Gpt-audit` @ `a096821`, unchanged.
- Deployed commit: SHA **UNVERIFIED** (no SSH/DB; no endpoint exposes it). Deployed behaviour still matches `7bf2012` (reserved-path 404, storage-aware readiness gates, degraded buy-board text). API process start unchanged at 2026-10-28T14:11:13Z.
- Scope: **REPOSITORY + LIMITED LIVE** — read-only, unauthenticated public GETs over HTTP: `/health`, `/health/nonexistent`, `/api/deployment/readiness` (×3), `/api/reports/status` (×3), `/api/cache/status` (×2), `/api/buy-board/status`, `/api/buy-board`. No token, no mutation.
- Tools: git, uv + Python 3.11 venv, curl. No Docker daemon, SSH, DB, logs or GitHub Actions read this run.

## 1. Operational verdict

**DEGRADED (live-confirmed).** Pipeline still halted at the database cap — ≈7.4 days since 10-22T20:51Z; `processed_cycles=0` since the 10-28 restart.
- Research-only readiness: **not ready** (`machine_running`, `source_integrity=FAILED`, `blocked_companies`, `stability_window` fail).
- Execution prohibited by design (`execution_allowed=false`, `terminal_handoff_allowed=false`), verified live.

## 2. Dashboard

| Metric | Value | Evidence |
|---|---|---|
| Liveness | `/health` 200 | 06:55:11Z |
| Report machine | `running=true`, `processed_cycles=0`, `last_cycle_at=null`, `storage_blocked=true` (`database_cap_reached`) | 06:55:18Z, 06:56:09Z, 06:57:09Z |
| Reports persisted | **2,134 / 4,473** (47.7%), same as 10-28 and 10-29 (same endpoint) | |
| Throughput | **0 net new reports in 111 s** (06:55:18Z→06:57:09Z); no completion events, companies/min not computable | 3 samples |
| Pending | report machine `pending_companies=0` (MED-021 remainder); cache warmer "deferred … (2339 pending)" | |
| Workers | all 8 roles `standby`, ticker null — storage block, not empty queue | |
| Freshness | newest SEC index 10-29; newest processed filing 10-22 (operator record); ≈5 EDGAR business days unprocessed | |
| Storage | DB 14.91 GB vs 14 GiB cap; 28.84 GB free (operator record 10-28; not re-measured). WAL/logs/backups UNVERIFIED | |
| Buy board | "degraded buy board (0/127 quotes)", `quote_refresh_incomplete`, last refresh 10-29T20:00Z; list `[]` | |
| Readiness latency | **6.30 s, 4.99 s, 3.34 s** for an unauthenticated GET (new ACC-MED-022) | 06:55:12Z–06:58Z |
| TLS | HTTPS :443 no response/reset (MED-010) | |
| Backup/restore | no new evidence | |

## 3. New findings

### ACC-MED-022 — Unauthenticated readiness/source-integrity endpoints run exact full-table counts per request
- Severity Medium · CONFIRMED (source + live latency) · Open
- Evidence: `src/accountant/api/app.py:1409-1413` (`/api/deployment/readiness`) and `:1513-1515` (`/api/source-integrity`) have no auth dependency and call `build_source_integrity_snapshot`; `src/accountant/research/source_integrity.py:35` and `:37` run `count(*)` on `canonical_facts` (one with an OR predicate) plus exact counts on statement_snapshots/company_reports/report_cards (`:38-41`) on every call, even though `:31` already uses an estimate on PostgreSQL. Live: 6.30 s / 4.99 s / 3.34 s responses on a 14.9 GB database.
- Consequence: any anonymous client on the public HTTP port can drive repeated sequential scans against a DB already at its cap, competing with catch-up ingestion and monitoring; readiness polling itself is slow.
- Repair: cache the snapshot with a short TTL (or persist it from the scheduler), use estimates for large tables, keep exact counts behind auth.
- Acceptance: readiness p95 < 500 ms; N concurrent anonymous calls issue ≤1 exact canonical_facts scan per TTL window.
- Test: unit test counting SQL executions across two calls within the TTL; live timing of two GETs.

## 4. Prior findings — status changes

No code changed, so no repository-level status change. Live re-confirmations: CRIT-001 (halt now ≈7.4 days), MED-010 (HTTP only), MED-021 remainder (pending=0 vs 2,339), LOW-014 remainder (0/127 quotes, 127 counted while list is empty), LOW-013 resolved still holds (404).

Totals: **46 items** (Critical 1, High 9, Medium 22, Low 14) · CONFIRMED 26, SUSPECTED 4, UNVERIFIED 0, RESOLVED 16.

## 5. Tests (main @ 7bf2012, Python 3.11, `ACCOUNTANT_ENV=test`, offline)

| Command | Result |
|---|---|
| `uv run pytest -p no:cacheprovider -o addopts="" -q` | exit 0; **566 passed / 0 failed / 0 skipped**, 1 warning (Starlette TestClient) |
| `uv run ruff check src tests` | All checks passed (scripts/ out of scope — LOW-005) |
| `uv run python scripts/check_mypy_baseline.py` | 236 existing errors, no new (not type-clean) |

Not run: Docker build/compose (no daemon), coverage, restore test, alembic drift, authenticated endpoints, logs, DB size/WAL, CI API.

## 6. Next actions

1. **Urgent operations — CRIT-001.** Operator capacity decision + capacity-safe catch-up; a restart has not helped. Five EDGAR business days are now unprocessed.
2. **Recovery — HIGH-009 / MED-005.** Scheduled systemd backup with off-host copy and one isolated restore, required before any archival that frees space.
3. **Status truthfulness / load — MED-021, MED-022.** Report a real backlog and stop running full-table counts on anonymous requests.

## 7. Not run / blocked

SSH, database, logs, WAL, disk, deployed SHA, authenticated routes, backup inventory: BLOCKED (no credentials provisioned to this routine). Scoring/valuation recomputation on live samples: BLOCKED (no DB; packets not accepted).
