# Accountant daily independent audit — 2026-10-23

- Audit time: 2026-10-23 02:53–04:10 EDT (America/New_York, UTC−4), Friday. Regular EDGAR business day.
- Repository: `main` @ `deec292` (clean worktree; audit branch `claude/charming-hopper-uln4gl` = `main`).
  New since the 10-22 audit (`6486343`): `573aa64`, `85656b3`, `f074775`, `f5a39e8`, `3fa7816`, `363fd7c`, `ea15ac1`, `deec292`.
  CI runs 55–60 on main (latest 39852371657 on `deec292`): all success.
- Deployed commit: UNVERIFIED. `docs/audits/2026-10-22-readiness-hardening.md` records a VPS baseline at `6486343` and post-release live checks, but does not name the SHA deployed after the follow-ups. No SSH, database or API access in this session.
- Previous audit: 2026-10-22 02:51 EDT (run 15).
- Tools available: local clone, uv/Python 3.11, local PostgreSQL 16 binaries (scratch cluster), GitHub Actions read access. Docker daemon not used. No production access.
- Scope: REPOSITORY-LEVEL, plus review of operator-recorded VPS evidence dated 2026-10-22. No live observation.

## Verdict

- Operations: **DEGRADED / UNVERIFIED**. Operator-recorded evidence (10-22) shows the report loop running again and a bounded SEC test advancing the latest filing to 2026-10-22, but the database remains at the 14 GiB cap and 2,193 companies / 11,063 accessions were pending. Current state not observed.
- Research-only readiness: **NOT READY**. All new cards are deliberately labelled `UNVALIDATED`; the producer returns packet V2 `accepted=false` (operator-recorded). This is the correct fail-closed behaviour.
- Execution: prohibited by design; no order paths found.

## Dashboard

| Item | 10-22 audit | 10-23 audit | Source |
|---|---|---|---|
| Reports (distinct companies) | 2,121 / 4,473 | 2,126 (cached) | operator-recorded 10-22 |
| Throughput | 0 (blocked) | +5 reports over an unstated window; no companies/minute can be computed | operator-recorded |
| Latest filing | 2026-10-06 | 2026-10-22 (latest acceptance 18:29:31 UTC), from an 8-company bounded test only | operator-recorded |
| Pending work | n/a | 2,193 companies / 11,063 accessions; one unpublished 10-22 index | operator-recorded |
| Database | 14.90 GB vs 14 GiB cap | ~14.6 GB after 303,464,448 bytes reclaimed by index rebuilds; cap still binding | operator-recorded |
| Disk free | 27 G | ~28.87 GB | operator-recorded |
| WAL / logs | UNVERIFIED | UNVERIFIED | — |
| Backup | none evidenced | one-off off-host snapshot 1,643,353,544 bytes, checksum reread and matched; full restore started, completion not recorded | operator-recorded |
| Restore test | none | Oct 7 raw-facts archive restored into isolated scratch DB (15,907,880 rows, 1,156 companies; table data only) | operator-recorded |

## Tests (main @ deec292; `uv sync --locked --extra dev`; Python 3.11; `ACCOUNTANT_ENV=test`)

- `uv run --frozen pytest -p no:cacheprovider`: exit 0, **526 passed / 0 failed / 0 skipped**, 1 warning (Starlette TestClient deprecation).
- `uv run --frozen ruff check src tests`: clean.
- `uv run --frozen python scripts/check_mypy_baseline.py`: 236 existing errors (was 308), no new diagnostics. Not type-clean.
- Scratch PG16: `alembic upgrade head` passes; `alembic check` **FAILS** (`buy_board_candidates` and other ORM tables missing; extra index on `statement_snapshots`). ACC-MED-014 re-reproduced.
- Not run: Docker build/compose, coverage, live endpoints.

## New findings

### ACC-MED-020 — Today's not-yet-published SEC daily index makes every in-window discovery run PARTIAL, so the scheduler records "failed" on normal business days

- Severity: Medium · Status: CONFIRMED (code path + existing tests); runtime effect supported by operator evidence ("one unpublished October 22 daily index") · Current status: Open
- Evidence:
  - `scripts/run_accountant_automation.py:137-145` runs `import_stale_sec_filings.py` without `--to-date` unless supplied, so `to_date = today`.
  - `src/accountant/sec/discovery_state.py:92-121` always includes `end` (today) when it is a filing day.
  - `scripts/import_stale_sec_filings.py:252-255` raises on any HTTP error (403/404 included); `:111` marks the day not ok and `:166-175` return exit 1 (`PARTIAL`).
  - `scripts/run_accountant_automation.py:193, 221` marks the cycle `failed` / exit 1 when any step is non-zero; `scripts/vps_readiness_check.py:173-174` treats anything but `complete`/0 as not ready.
  - Default poll windows `06:00-09:30,16:00-22:00` ET (`scripts/run_vps_scheduler.sh:4`). The morning window always precedes publication of today's index.
- Consequence: on a normal business day nearly every cycle is classified `failed`, and scheduler readiness is red, which hides genuine failures behind routine noise. The retry ordering is unaffected (failed days are retried), so this is a status-truthfulness defect, not data loss.
- Repair: treat the current EDGAR day's index as `not_yet_published` (pending, not failed) until a configurable publication cut-off; report it separately from failed indexes; return 0 when the only unresolved item is an unpublished current-day index.
- Acceptance: with a 404 for today's index and all earlier days complete, the run returns 0 with `pending_unpublished=1`, the cycle is `complete`, and the date is retried next run; a 404 for a past business day still yields `PARTIAL`.
- Test: extend `tests/test_discovery_recovery.py::test_http_failures_are_not_empty_success` with a current-day case and a past-day case.

## Prior findings — status changes

- **ACC-CRIT-001 → Partially addressed** (operator-recorded 10-22): index rebuilds reclaimed 303 MB without deleting facts; report loop observed running (2,126 vs 2,121); bounded SEC test advanced latest filing to 10-22. Cap still binding; universe catch-up not done. Current state UNVERIFIED.
- **ACC-HIGH-001 → RESOLVED (repository level)**: the global `max(filing_date)+1` watermark is gone; per-day checkpoints with 3-business-day overlap and retry of failed days (`discovery_state.py:92-121`); 403/404/5xx raise and keep the date pending (`import_stale_sec_filings.py:252-255`). Regression tests pass: `test_default_poll_ignores_future_global_filing`, `test_http_failures_are_not_empty_success[403|404|500]`, `test_failed_index_survives_restart`. Deployment UNVERIFIED (operator says scheduler restarted with checkpoints). Residual noted as ACC-MED-020 and a 30-day catch-up cap (`HISTORY_DAYS`, `discovery_state.py:16, 109`).
- **ACC-HIGH-002 → Partially addressed**: flows are annual only with an exact shared window (`report_machine.py:1294-1304`); EPS uses annual weighted-average diluted shares (`:1305-1312, 1418`); valuation uses instant shares at the fiscal year end (`:1313-1316, 1424-1429`); `_scenario_valuations` returns None when shares are missing (`:2733-2745`). Residual: no TTM (annual figures can be ~3 quarters stale), `dei:EntityCommonStockSharesOutstanding` is dated at the cover page, not FY end, so it rarely matches the filter; no golden-file reconciliation; stored cards not re-scored.
- **ACC-HIGH-003 — still Partially addressed**: SEC import now rechecks storage before each company commit (`import_stale_sec_filings.py:343-430`, `test_each_company_admission_honors_storage_reserve`). Report-machine lanes still use one preflight with `cycle_start_database_bytes=database_bytes` (`report_machine.py:399`); no cross-process reservation.
- **ACC-HIGH-004 — unchanged**: `self._snapshot.last_error = None` now at `report_machine.py:373`; lane handlers still swallow exceptions.
- **ACC-HIGH-005 — unchanged**: sort key at `report_machine.py:2319-2320`.
- **ACC-HIGH-006 — unchanged**: `SecClient()` per worker at `report_machine.py:713, 740, 901`; `fetch_filing_text` `@lru_cache` + `except Exception` at `filing_signal_engine.py:361-374`.
- **ACC-HIGH-009 → Partially addressed**: one-off off-host snapshot streamed and checksum re-verified (operator-recorded). Still no repository-managed systemd API unit or backup timer (`deploy/` has only the scheduler unit), no scheduled off-host copy, restore completion not recorded.
- **ACC-MED-001 → Partially addressed**: amendment no longer sets event severity 95; going-concern/material-weakness/late-filer are `None`, restatement `unknown`; every new card is forced to `UNVALIDATED`/`WATCH`/size 0 (`report_machine.py:2026-2051`). Residual: `grading_engine.py:176-177` still maps missing severities to 0 inside the grade score; no going-concern/Item 4.02 detection.
- **ACC-MED-008 — unchanged, scope widened**: `is_production` is still `accountant_env.lower() == "production"` (`config.py:105-106`); the new `require_research_token` (`api/auth.py:13-31`) inherits the same fail-open rule.
- **ACC-MED-014 — re-reproduced** on PG16 at `deec292`.
- **ACC-MED-019 → RESOLVED (repository level)**: a storage-blocked run publishes `status=paused_storage` (`run_accountant_automation.py:110-132`), the shell loop classifies via `vps_readiness_check.py --record-cycle` (`run_vps_scheduler.sh:41-56`), and readiness rejects paused cycles (`vps_readiness_check.py:173, 225`). Tests in `tests/test_readiness_operations.py` pass. Deployment UNVERIFIED.
- **ACC-LOW-005 — Partially addressed (progress)**: mypy debt 308 → 236.
- All other items: unchanged, carried forward without independent re-validation beyond the line checks above.

## Three highest-impact next actions

1. **Operations (urgent):** finish the full-universe SEC catch-up under the cap (or after an operator capacity decision) and record completion of the off-host snapshot restore with row counts. Without this the research handoff stays stale and archival stays unsafe (CRIT-001, HIGH-009).
2. **Correctness:** fix ACC-HIGH-004 (swallowed lane errors) and ACC-MED-020 (false "failed" cycles) together, so status reflects real failures. Both are small and make every later operational signal trustworthy.
3. **Correctness:** finish ACC-HIGH-002 with TTM flows and a golden-file reconciliation for an operating company, a bank and a REIT before any card leaves `UNVALIDATED`.

## Checks not run / unproven

- No live API, scheduler, PostgreSQL, worker, log, WAL, disk, backup or firewall observation; every runtime number above is operator-recorded.
- Deployed SHA after the 10-22 follow-ups is not recorded.
- Docker build/compose validation, coverage, and the representative-family scoring reconciliation (Pass 3) were not run.
- No crash-recovery exercise beyond the offline unit tests.
