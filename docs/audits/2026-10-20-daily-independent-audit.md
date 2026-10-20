# Accountant daily independent audit — 2026-10-20

Run 13 of the daily routine. Read-only. No production change. No secrets recorded.

## Evidence header

| Item | Value |
|---|---|
| Audit time | 2026-10-20 02:51–03:20 EDT (America/New_York, UTC−4), Tuesday. A regular EDGAR business day. |
| Local commit / branch | `main` @ `e234b26` (2026-10-19 08:12 EDT, "Promote reviewed governance evidence and scheduler readiness fixes"). Clean worktree. The designated branch equals `main`. |
| Change since last audit | `7785df7` → `e234b26`: 8 files, +295/−25. Covers filing_signal_engine, report_machine (as-of date), vps_readiness_check (scheduler status reader), compose poll variable, and new tests. |
| Deployed commit | **UNVERIFIED.** This session has no SSH, monitoring, API, DB or production credentials. |
| Previous audit | 2026-10-19 02:53–03:30 EDT (run 12). It is recorded in the Notion backlog, and the artifact is on `claude/charming-hopper-wqukqm` @ `1dd8a44`. |
| Scope | **REPOSITORY-LEVEL ONLY.** Every live pass (operations, freshness, storage and restore) is UNVERIFIED. |
| Tools | git, uv 0.x with Python 3.11 venv, ruff, GitHub Actions (read). There was no Docker daemon run and no PostgreSQL instance. |

## Verdict

- **Operations: UNVERIFIED.** No production access, as in every run since 10-08.
- **Code level: DEGRADED (unchanged).** The six High defects in discovery, valuation, storage, failure visibility, lane rotation and the SEC limiter (ACC-HIGH-001…006) are untouched on `main`.
- **Research-only readiness:** not established.
- **Execution:** prohibited by design. No order or broker paths were added; the diff touches only research signals, readiness and compose.

## Dashboard

| Metric | Value |
|---|---|
| Report coverage, throughput, pending/blocked work, filing freshness, stage lag | UNVERIFIED (no production access) |
| DB, disk, WAL, headroom, backups, restore | UNVERIFIED |
| CI on `main` HEAD | **Green.** Run 39250282861 on `e234b26` was a success. It is the first green `main` CI since `cedd614` on 10-08. |
| Local tests (`main` @ `e234b26`) | `ACCOUNTANT_ENV=test uv run --frozen pytest -p no:cacheprovider` returned exit 0: **408 passed, 0 failed, 0 skipped, 1 warning** (Starlette/httpx deprecation). |
| Lint | `uv run --frozen ruff check src tests` reported "All checks passed!" with exit 0. |
| Focused | `tests/test_oct19_selected.py` + `tests/test_filing_signal_engine.py`: 15 passed. |
| Not run | Docker/compose validation (no daemon), whole-package mypy, coverage, PG16 migration acceptance (ACC-MED-014). |

The 408 count is not comparable to yesterday's 401. The suite composition changed: tests were added and one was renamed.

## Status changes this run (evidence)

1. **ACC-MED-017: RESOLVED (repository level).** The date-expired test was rewritten as `test_build_governance_signals_counts_form4_without_inventing_buy_direction` with a fixed `as_of=date(2026, 8, 1)`. `tests/test_oct19_selected.py::test_signal_windows_do_not_depend_on_wall_clock` monkeypatches the wall clock. The full suite passes (408/408), and CI 39250282861 is green.
2. **ACC-MED-018: RESOLVED (repository level; stored report cards not rewritten; deployment unverified).**
   - `filing_signal_engine.py` `build_governance_signals(..., as_of=...)` now returns `insider_buy_cluster_flag=None` and `insider_net_shares_bought_90d=None`.
   - It publishes `form4_filing_count_90d`, `insider_direction_status="unknown_transaction_codes_not_parsed"`, `source_accessions`, `as_of_date` and `rule_version=GOVERNANCE_AS_OF_V2_FORM4_COUNT_ONLY`.
   - Future-dated filings are excluded (`filing_date <= as_of`).
   - `report_machine.py:1190` captures one `report_as_of` per report, and `:1610-1611` records the rule versions.
   - Grep finds no scoring consumer of the governance flags.
   - Regression tests: `test_governance_count_includes_cutoff_but_not_older_or_future_filings` and `test_event_windows_exclude_future_and_use_most_recent_disclosure` pass.
   - Remaining limits, documented in the promotion note and not reissued as a new finding: transaction direction is still unparsed (UNKNOWN), and heuristic auditor/dual-class detection is unchanged.
3. **ACC-LOW-006: RESOLVED (repository level).** The two items left open on 10-10 are fixed.
   - The status file now has a reader: `scripts/vps_readiness_check.py:20-24, 98-114`. `scheduler_recent_and_successful` rejects missing, failed, naive, future-dated and >36 h-old status.
   - The dead compose variable is gone. `docker-compose.prod.yml:63` now sets `ACCOUNTANT_ACTIVE_POLL_INTERVAL_SECONDS`, which `scripts/run_vps_scheduler.sh:5` consumes.
   - Tests `test_readiness_reads_scheduler_status_and_rejects_missing_failed_stale` and `test_compose_passes_the_scheduler_poll_variable` pass.
   - The 36 h window is valid because polling windows run every day, including weekends (`polling_schedule.py`).
   - This is a readiness ceiling, not proof that polls ran every 15 minutes.
4. **ACC-MED-016: Partially addressed.** `main` HEAD now has green CI (run 39250282861: `test` and `docker` jobs). The fragility remains: `ci.yml:10-12` still pulls `postgres:16` anonymously from Docker Hub, and images are not pinned by digest.

No other status changes. ACC-HIGH-001…006 evidence was re-checked on `e234b26`:

- `scripts/import_stale_sec_filings.py:133-141` (global `max(filing_date)+1` watermark) is unchanged.
- `report_machine.py:2723` (`divisor = ... else 1.0`) is unchanged. The line moved from 2713 because of +10 lines above it.
- `report_machine.py:358` (`last_error = None`) and `:384` (`cycle_start_database_bytes=database_bytes`) are unchanged.
- `report_machine.py:1881` (amendment → `event_flag_severity=95`) and `:1898-1899` (`going_concern_flag=False`, `big_r_restatement_flag=False`) are unchanged. ACC-MED-001 is still Open.
- `api/auth.py:25` + `config.py:102-103`: auth fails open unless env is exactly "production" (case-insensitive). ACC-MED-008 is still Open.

## New findings

None verified. Zero new defects is reported rather than padding the list.

## Totals

37 items: Critical 0 · High 8 · Medium 18 · Low 11.
Finding status: CONFIRMED 23 · SUSPECTED 3 · UNVERIFIED 0 · RESOLVED 11.

## Top three next actions

1. **Operations:** restore any read-only production visibility, such as an SSH read-only user or the monitoring endpoint. This is the 13th run with zero runtime evidence. The report count, freshness, disk and backup status are unknown.
2. **Correctness: ACC-HIGH-002.** Fix the valuation/EPS quarterly-vs-TTM and share-basis mixing. These numbers are wrong for most companies with a recent 10-Q.
3. **Freshness: ACC-HIGH-001 + ACC-HIGH-005.** A durable per-index-date checkpoint and filings-lane rotation are needed before any freshness claim.

These outrank cosmetic work because they decide whether any published research number or freshness claim is true.

## Checks not run / unproven

- Every live pass: workers, two-timestamp throughput, scheduler logs, `accepted_at` lag, DB/WAL/disk, backup age, off-host copy, restore. Status: UNVERIFIED.
- Docker image build and compose validation were not run locally. CI shows a docker job success on `e234b26`, which is not proof of a runtime or compose smoke test.
- Pass 3 sample recomputation (bank, REIT, energy, biotech) needs a populated DB and was not possible.
- Migration acceptance on a populated legacy schema (ACC-MED-014) was not re-run.
