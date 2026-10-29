# Accountant Daily Independent Audit — 2026-10-29

- Audit time: 2026-10-29 02:51–03:20 EDT (America/New_York, UTC−4), Thursday. Daily routine, run 22.
- EDGAR calendar: business day. A bounded read of the public SEC `daily-index/2026/QTR4/index.json` at 02:57 EDT shows `master.20261028.idx` as the newest index. Today's index is not yet published. US DST ends Sun 2026-11-01.
- Repository: `main` moved `deec292` → **`7bf2012`** (2026-10-28 10:09 EDT, "Promote reviewed audit storage, health and quote-status safeguards"; selective promotion of `Claude-Gpt-audit` e1fe8b0/a096821). CI run 40703139804 is green. Working branch `claude/charming-hopper-dwuas6` = `7bf2012` before this artifact; worktree clean.
- Deployed commit: **SHA UNVERIFIED** (no SSH/DB; no endpoint reports it). Deployed *behaviour* matches `7bf2012`: the API restarted at 2026-10-28T14:11:13Z (two minutes after the CI run finished), `/health/nonexistent` returns 404, buy-board status uses the new "degraded … quotes" text, and readiness now fails `machine_running` while storage-blocked. These three behaviours exist only in `7bf2012`.
- Scope: **REPOSITORY + LIMITED LIVE** (read-only, unauthenticated public GETs over HTTP to the Accountant host). Endpoints: `/health`, `/health/nonexistent`, `/api/deployment/readiness`, `/api/reports/status` (×2), `/api/cache/status` (×2), `/api/buy-board/status`, `/api/buy-board`. No token, no mutation.
- Tools: git, uv + Python 3.11 venv, GitHub Actions API (read-only), curl. No Docker daemon, no SSH, no DB.

## 1. Operational verdict

**DEGRADED (live-confirmed).** The research pipeline is still halted at the database cap — now about 6.4 days (since API start on 10-22T20:51Z; the restart at 10-28T14:11Z did not clear it).
- Research-only readiness: **not ready**. Live gates: `machine_running=false`, `source_integrity=FAILED`, `blocked_companies=false`, `stability_window=false`, `ready_for_next_phase=false`.
- Execution is prohibited by design (`execution_allowed=false`, `terminal_handoff_allowed=false`), verified live.

## 2. Dashboard

| Metric | Value | Evidence |
|---|---|---|
| Liveness | `/health` 200 `{"status":"ok"}` | 06:52:21Z |
| Report machine | `running=true`, started 2026-10-28T14:11:13Z, `processed_cycles=0`, `last_cycle_at=null`, `storage_blocked=true`, `storage_block_reason=database_cap_reached` | 06:52:28Z, 06:56:54Z |
| Reports persisted | **2,134 / 4,473** (47.7%) — same as 10-28 (same endpoint, comparable) | |
| Throughput | **0 net new reports in 266 s** (06:52:28Z → 06:56:54Z). No completion events (0 cycles since restart) | 2 samples |
| Pending | report machine `pending_companies=0` (still misleading, MED-021); cache warmer "deferred until report backlog drains (2339 pending)" | |
| Workers | all 8 roles `standby`, ticker null — cause is the storage block, not an empty queue | |
| Readiness | `machine_running` **fails** ("database_cap_reached"), `blocked_companies` **fails** — new behaviour since 7bf2012 | `/api/deployment/readiness` 06:52:28Z |
| Freshness | newest SEC index 2026-10-28; newest processed filing 2026-10-22 (operator record 10-28); no ingest since | |
| Storage | DB 14,909,774,871 B vs 14 GiB cap; 28.84 GB free FS (operator record in `docs/audits/2026-10-28-selective-promotion.md`; not independently measured). WAL/logs/backups UNVERIFIED | |
| Buy board | `last_action="degraded buy board (0/127 quotes)"`, `last_error=quote_refresh_incomplete`, last refresh 10-28T20:00Z; `/api/buy-board` = `[]` | |
| CI | main 7bf2012 run 40703139804 success | |
| Backup/restore | no new evidence | |

## 3. New or regressed findings

None verified. I reviewed the full `deec292..7bf2012` diff (config validators, exit-75 pause, readiness gates, reserved paths, buy-board degraded status, `record_cycle` exit-75 handling) and found no new defect. `record_cycle` accepts exit 75 only with a matching `paused_storage` summary; exit 75 with `blocked=false` stays `failed` — correct.

## 4. Prior findings — status changes

| ID | Change | Evidence |
|---|---|---|
| ACC-MED-008 | Open → **RESOLVED (repository level)** | `config.py:97-103` strips/lowercases `ACCOUNTANT_ENV` and rejects anything except development/test/production. Reproduced locally: `prod`, ` production `, `staging` → `ValidationError` at settings construction. `tests/test_oct27_selected.py:50-60` parametrized cases pass. Live mutation auth not probed (no POSTs allowed) |
| ACC-LOW-012 | Partially addressed → **RESOLVED (repository level; deployed behaviour consistent)** | `config.py:85-95` model validator; production with missing/zero/non-finite limits fails startup. Deployed API is running after the 10-28 restart, so its limits passed the validator (operator note: 14/25/1 GiB + 128 MiB reserve) |
| ACC-LOW-013 | Partially addressed → **RESOLVED (live)** | `app.py:1961` first-segment check; live `GET /health/nonexistent` → 404 `{"detail":"Not found"}` at 06:52:28Z |
| ACC-LOW-014 | Open → **Partially addressed** | `buy_board.py:714-719` sets `last_error=quote_refresh_incomplete` on incomplete refresh; live status shows it. Still open: `candidate_count=127` counts and quotes quarantined rows while `/api/buy-board` returns `[]`; the cause of 0/127 quotes is UNVERIFIED |
| ACC-MED-021 | Open → **Partially addressed** | `app.py:1416,1418` readiness gates now fail while storage-blocked (live-confirmed). Still open: `pending_companies/runnable/blocked=0` during the halt vs 2,339 pending in the cache warmer (live 06:52Z, 06:56Z) |
| ACC-CRIT-001 | Open — **re-confirmed live**, halt ≈6.4 days; restart did not resume work | |
| ACC-MED-010 | Open — re-confirmed: HTTP on 80 only; HTTPS connection reset | |
| ACC-MED-019 | Resolved — still holds; pause now exits 75 and is recorded as `paused_storage` only with matching summary | `scripts/vps_readiness_check.py:210-233` |
| ACC-HIGH-003 | Open (unchanged): worker reserve on main; mid-cycle overshoot not addressed | |

All other items unchanged. Totals: **45 items** (Critical 1, High 9, Medium 21, Low 14) · CONFIRMED 25, SUSPECTED 4, UNVERIFIED 0, RESOLVED 16.

## 5. Tests (main @ 7bf2012, Python 3.11, `ACCOUNTANT_ENV=test`, offline)

| Command | Result |
|---|---|
| `uv sync --extra dev`; `pytest -p no:cacheprovider` | exit 0; **566 passed / 0 failed / 0 skipped**, 1 warning (Starlette TestClient deprecation) |
| `ruff check src tests` | All checks passed (scripts/ not in scope — LOW-005) |
| `python scripts/check_mypy_baseline.py` | 236 existing errors, no new diagnostics (not type-clean) |
| Settings env reproduction (MED-008) | `prod`/` production `/`staging` rejected |

Not run: Docker build/compose (no daemon), coverage, restore test, alembic drift re-check (no schema change in the diff; MED-014 unchanged), authenticated endpoints, logs, DB size/WAL.

## 6. Next actions

1. **Urgent operations — CRIT-001.** Capacity decision + capacity-safe catch-up. Six-plus days of filings are now unprocessed; the restart alone did not help. Verify the report count rises across two samples ≥60 s apart.
2. **Status truthfulness — MED-021 remainder.** Publish a real (bounded/precomputed) backlog count or `null` + `paused_storage` instead of 0.
3. **Recovery — HIGH-009 / MED-005.** Scheduled systemd backup with off-host copy, and one isolated full restore.

## 7. Not run / blocked

- SSH, database, logs, WAL, disk, deployed SHA, authenticated routes, backup inventory: BLOCKED (no credentials provisioned to this routine).
- Scoring/valuation recomputation on live samples: BLOCKED (packets not accepted; no DB access).
