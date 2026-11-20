# Accountant Daily Independent Audit — 2026-11-20

Run 42. Read-only. This file contains no secrets, tokens, DSNs or environment files.

## Evidence contract

| Item | Value |
|---|---|
| Audit time | 2026-11-20 01:51–02:20 EST (America/New_York, UTC−5), Friday. Today's EDGAR index is not yet published |
| Local / GitHub `main` | `6b7d6f1`, unchanged since 11-09 (verified with `git ls-remote`). `Claude-Gpt-audit` is `5c055cb`, unchanged |
| Audit branch | `claude/charming-hopper-l0wl2u` (at `6b7d6f1`). The worktree was clean before this artifact |
| Deployed commit | UNVERIFIED. No live sample was possible today (see Access) |
| Previous audit | 2026-11-19 run 41 (`claude/charming-hopper-6qpf8g`, `18fc16b`) |
| Access | **REPOSITORY-ONLY.** This run did not have the Accountant host address used by earlier runs for public GETs. It is not in the repository, the Terminal configuration or Notion. No SSH, database, logs or token. Isolated local tests ran |

## Verdict

**DEGRADED (carried forward; live UNVERIFIED today).** Research-only readiness: **not ready**. No commit touches the storage cap, so the CRIT-001 halt is presumed to continue (day 29), but it was not observed today. Execution is prohibited by design.

## Dashboard

| Metric | Value |
|---|---|
| Reports, workers, gate, freshness | UNVERIFIED today. The last live values (11-19 06:55Z) were 2,134 / 4,473 reports, net 0 over 78 s, `database_cap_reached`, 8/8 standby, newest processed filing 2026-10-22 |
| EDGAR business days missed (calendar estimate) | 19 (10-23 → 11-19, excluding 11-11), assuming the halt continues |
| Catch-up window (refined from source) | `discovery_state.py:16` `HISTORY_DAYS = 30`; `:109` `floor = end - timedelta(days=HISTORY_DAYS - 1)`. 10-23 is still inside the default window on a run dated 11-21. **From 11-22 onward the default catch-up drops one missed day per calendar day.** The retry path at `:116-120` only covers days already recorded as failed in the checkpoint. Whether 10-23 onward are recorded is UNVERIFIED. Previous runs said "exceeded on 11-21"; the exact boundary is the 11-22 run |
| Database / disk / WAL / backup / restore | UNVERIFIED |

## New findings
None. `main` is unchanged and no live evidence was obtainable.

## Prior findings
All 48 items are unchanged (no code change). CRIT-001 evidence was updated with the source-derived catch-up boundary above. Live-dependent items (CRIT-001, MED-010, MED-021, MED-022, LOW-014, LOW-015) were **not re-observed** today.
Register: 48 items (Critical 1, High 9, Medium 22, Low 16). 27 CONFIRMED / 4 SUSPECTED / 0 UNVERIFIED / 17 RESOLVED.

## Tests
Environment: offline, `ACCOUNTANT_ENV=test`, `env -i`, no credentials, Python 3.11, scratch clone of 6b7d6f1.

| Command | Result |
|---|---|
| `uv sync --locked --extra dev --python 3.11` | exit 0 |
| `ruff check src tests` | exit 0 |
| `python -m pytest -q` | exit 0. 601 tests, 0 failed, 0 errors, 0 skipped (junit). 1 warning (Starlette `httpx` TestClient deprecation) |
| `python scripts/check_mypy_baseline.py` | exit 0. 236 existing errors, none new. This is a ratchet, not a clean type check |

CI: no new runs on `main` since 11-09. The latest run, #94 on the 11-19 audit branch, passed.
Not run: Docker build/compose, Alembic on PG16, coverage, restore drill, any live check.

## Next actions
1. **Urgent operations (deadline 11-22):** make a capacity decision and run a capacity-safe catch-up (CRIT-001/HIGH-003). From the 11-22 run onward, catch-up needs an explicit start date of 2026-10-23.
2. **Recovery:** add a scheduled backup and an isolated restore test on the systemd topology (HIGH-009/MED-005).
3. **Correctness:** fix the valuation basis (HIGH-002) before reports resume.

## Not checked or unproven
Everything live: health, readiness, report counts, workers, freshness, buy board, deployed SHA, DB/WAL/disk, logs, TLS and restore. Scoring recomputation (no new reports since 10-22). To restore live checks, give the routine the Accountant host address or a read-only monitoring path.
