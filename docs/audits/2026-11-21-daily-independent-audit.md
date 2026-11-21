# Case Capital Accountant — Daily Independent Audit 2026-11-21

Run 43. Read-only. No secrets, connection strings or environment files appear here. Nothing in production was mutated.

## Ground truth

| Item | Value |
|---|---|
| Audit time | 2026-11-21 01:51–02:20 EST (America/New_York, UTC−5), Saturday. No EDGAR filing day today |
| Previous audit | 2026-11-20, run 42 (repository-only) |
| `main` | `6b7d6f1`, unchanged since 2026-11-09 (`git ls-remote`). `Claude-Gpt-audit` `5c055cb` unchanged |
| Audit branch | `claude/charming-hopper-zef5i5` (worktree clean before this artifact) |
| Deployed commit | UNVERIFIED |
| Scope | **REPOSITORY-ONLY.** The Accountant host address is not available to this run (not in the repository, the Terminal config or Notion). No SSH, database, logs, monitoring path or token |
| CI | No new `main` runs. Latest runs (#93–#95) are audit-doc branches, all green |

## Verdict

**DEGRADED (carried forward; live UNVERIFIED today).** Research-only readiness: **not ready**. Execution is prohibited by design.

- ACC-CRIT-001 (storage-cap halt) has no repairing commit. If the halt continues, today is presumed **day 30**, and **20 EDGAR business days** (2026-10-23 → 2026-11-20, excluding the 11-11 holiday) are unprocessed. Not observed live today.
- **Catch-up boundary reached.** `src/accountant/sec/discovery_state.py:16` (`HISTORY_DAYS = 30`) and `:109` (`floor = end − 29 days`) mean 2026-10-23 is the oldest day inside the default discovery window on today's (11-21) run. From the 11-22 run onward, one missed EDGAR day falls out of the default window per calendar day. The retry path (`:116-120`) covers only days already recorded as failed in the checkpoint; whether 10-23 onward are recorded is UNVERIFIED. Any catch-up started after today needs an explicit start date of 2026-10-23.

## Pass summaries

1. Live operations and progress — UNVERIFIED (no access). Throughput, worker state, queue, scheduler and logs not observed.
2. Freshness/pipeline — UNVERIFIED live. Last live observation (11-19): newest processed filing 2026-10-22; 2,134 / 4,473 reports (47.71%); net 0 over 78 s.
3. Scoring/valuation — no code change; ACC-HIGH-002 and ACC-MED-001 unchanged.
4. Storage/archive/recovery — UNVERIFIED live. ACC-HIGH-009 (no repository-managed backup on the systemd topology) unchanged. No restore test evidence.
5. Security/deployment/tests — see below.

## Tests (main @ 6b7d6f1, isolated `uv sync --locked --extra dev`, Python 3.11, `env -i`, `ACCOUNTANT_ENV=test`, offline)

| Command | Result |
|---|---|
| `pytest` | exit 0 — **601 tests, 0 failed, 0 errors, 0 skipped** (junit), 1 warning (Starlette/httpx deprecation) |
| `ruff check src tests` | All checks passed |
| `python scripts/check_mypy_baseline.py` | exit 0 — 236 existing errors, no new diagnostics |

Not run: Docker build/compose validation, Alembic on PostgreSQL 16, coverage, restore, any live check.

## Findings

- **New:** none. **Status changes:** none.
- **Evidence updated:** ACC-CRIT-001 (catch-up boundary reached today).
- **Not re-observed (no live access):** CRIT-001, MED-010, MED-021, MED-022, LOW-014, LOW-015.
- **Register:** 48 items (Critical 1, High 9, Medium 22, Low 16). Evidence status: CONFIRMED 27, SUSPECTED 4, UNVERIFIED 0, RESOLVED 17.

## Top actions

1. **Operations (urgent, today):** make the capacity decision for ACC-CRIT-001 (grow the volume, or verified off-host archive before any cleanup). If catch-up starts on or after 11-22, pass an explicit discovery start of 2026-10-23.
2. **Correctness:** fix ACC-HIGH-002 (valuation basis) before catch-up repopulates reports.
3. **Recovery:** ACC-HIGH-009 — repository-managed backup on the real systemd topology plus an isolated restore test, before any archival.

## Checks not run / access needed

The Accountant host address or a read-only monitoring path; database size, WAL, disk, backup footprint; logs; deployed SHA.
