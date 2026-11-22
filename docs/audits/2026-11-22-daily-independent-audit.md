# Case Capital Accountant — Daily Independent Audit 2026-11-22

Run 44. Read-only. No secrets, connection strings or environment files appear here. Nothing in production was mutated.

## Ground truth

| Item | Value |
|---|---|
| Audit time | 2026-11-22 01:50–02:25 EST (America/New_York, UTC−5), Sunday. No EDGAR filing day today |
| Previous audit | 2026-11-21, run 43 (repository-only) |
| `main` | `6b7d6f1`, unchanged since 2026-11-09 (`git ls-remote`). `Claude-Gpt-audit` `5c055cb` unchanged |
| Audit branch | `claude/charming-hopper-ah2blt` |
| Deployed commit | UNVERIFIED |
| Scope | **REPOSITORY-ONLY.** No Accountant host address, SSH, database, logs, monitoring path or token available to this run |
| CI | No new `main` runs. Latest run #96 (audit-doc branch) green |

## Verdict

**DEGRADED (carried forward; live UNVERIFIED today).** Research-only readiness: **not ready**. Execution is prohibited by design.

- ACC-CRIT-001 (storage-cap halt): no repairing commit. If the halt continues, today is presumed **day 31**; **20 EDGAR business days** (2026-10-23 → 2026-11-20, excluding the 11-11 holiday) are unprocessed. Not observed live.
- **Catch-up window loss has begun.** `src/accountant/sec/discovery_state.py:16` (`HISTORY_DAYS = 30`) and `:109` (`floor = end − 29 days`): on today's run the floor is 2026-10-24, so **2026-10-23 (a filing day) is outside the default discovery window**. The next filing day to drop out is 2026-10-26, on the 2026-11-25 run. The retry path (`:116-120`) only covers days already recorded as failed in the checkpoint; whether 10-23 is recorded is UNVERIFIED. Catch-up now requires an explicit start date of 2026-10-23.

## Pass summaries

1. Live operations — UNVERIFIED (no access). No throughput, worker, queue, scheduler or log observation.
2. Freshness/pipeline — UNVERIFIED live. Last live observation (11-19): newest processed filing 2026-10-22; 2,134 / 4,473 reports (47.71%); net 0 over 78 s.
3. Scoring/valuation — no code change; ACC-HIGH-002 and ACC-MED-001 unchanged.
4. Storage/archive/recovery — UNVERIFIED live. ACC-HIGH-009 unchanged. No restore-test evidence.
5. Security/deployment/tests — below.

## Tests (main @ 6b7d6f1, isolated `uv sync --locked --extra dev`, Python 3.11, `env -i`, `ACCOUNTANT_ENV=test`, offline)

| Command | Result |
|---|---|
| `pytest -q` | exit 0 — **601 tests, 0 failed, 0 errors, 0 skipped** (junit), 1 warning (Starlette/httpx deprecation) |
| `ruff check src tests` | All checks passed |
| `python scripts/check_mypy_baseline.py` | exit 0 — 236 existing errors, no new diagnostics |

Not run: Docker build/compose validation, Alembic on PostgreSQL 16, coverage, restore, any live check.

## Findings

- **New:** none. **Status changes:** none.
- **Evidence updated:** ACC-CRIT-001 (10-23 now outside the default discovery window).
- **Not re-observed (no live access):** CRIT-001, MED-010, MED-021, MED-022, LOW-014, LOW-015.
- **Register:** 48 items (Critical 1, High 9, Medium 22, Low 16). CONFIRMED 27, SUSPECTED 4, UNVERIFIED 0, RESOLVED 17.

## Top actions

1. **Operations (urgent):** capacity decision for ACC-CRIT-001; when catch-up starts, pass an explicit discovery start of 2026-10-23 (default window no longer reaches it). Do it before 11-25 to avoid losing 10-26 as well.
2. **Correctness:** ACC-HIGH-002 (valuation basis) before catch-up repopulates reports.
3. **Recovery:** ACC-HIGH-009 — repository-managed backup on the real systemd topology plus an isolated restore test, before any archival.

## Checks not run / access needed

Accountant host address or read-only monitoring path; database size, WAL, disk, backup footprint; logs; deployed SHA.
