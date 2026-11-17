# Accountant Daily Independent Audit — 2026-11-17

Run 39. Read-only. This file contains no secrets, tokens, DSNs or environment files.

## Evidence contract

| Item | Value |
|---|---|
| Audit time | 2026-11-17 01:51–02:15 EST (America/New_York, UTC−5), Tuesday. Today's EDGAR index is not yet published (pre-open) |
| Local / GitHub `main` | `6b7d6f1`, unchanged since 11-09. `Claude-Gpt-audit` `5c055cb` unchanged (`git ls-remote`) |
| Audit branch | `claude/charming-hopper-wv5brz` (at `6b7d6f1`). Worktree was clean before this artifact |
| Deployed commit | SHA UNVERIFIED. API `started_at=2026-11-09T12:36:53Z` (no restart). `SOURCE_INTEGRITY_V2_EXACT_COHORTS` is live. That is evidence of the 6b7d6f1 lineage, not proof of the SHA |
| Previous audit | 2026-11-16 run 38, `docs/audits/2026-11-16-daily-independent-audit.md` (commit `b815b94`) |
| Access | Unauthenticated read-only HTTP GETs to the public Accountant host (port 80), the GitHub Actions API and isolated local tests. No SSH, database, logs, token or mutation. HTTPS: no response (curl code 000) |

## Verdict

**DEGRADED (live-confirmed).** Research-only readiness is **not ready**. `/api/deployment/readiness` at 06:52:37Z failed four gates: `machine_running` (`database_cap_reached`), `source_integrity` (`FAILED`), `blocked_companies` (`database_cap_reached`) and `stability_window` (0/7). Execution is prohibited by design (`execution_allowed=false`, `terminal_handoff_allowed=false`).

## Dashboard (live)

| Metric | Value | Evidence |
|---|---|---|
| `/health`, `/ready` | 200; `ready`, 4,473 companies | 06:52:30Z, 06:53:52Z |
| Storage gate | `storage_blocked=true`, `database_cap_reached`. `processed_cycles=0` since the 11-09 restart; `last_cycle_at=null` | `/api/reports/status` 06:52:31Z and 06:53:52Z |
| Reports (distinct companies) | 2,134 / 4,473 (47.71%). Report cards: 2,105 | same |
| Net coverage change | **0 over 81 s** (2 samples, byte-identical payloads). Companies/minute cannot be computed because there are no completion events | — |
| Workers | 8/8 `standby`, no ticker. Pending/runnable/blocked = 0/0/0 while the gate blocks all work (MED-021) | — |
| Newest processed filing | 2026-10-22, accepted 2026-10-22T20:39:57Z. `days_since_latest_filing=26`, `source_grade=FAILED` | `/api/source-integrity` 06:52:31Z |
| EDGAR business days missed | **16** completed days (10-23 → 11-16, excluding 11-11). Today, 11-17, will be the 17th | calendar |
| Halt duration | **day 26** | CRIT-001 |
| Catch-up window | The default 30-day `HISTORY_DAYS` window is exceeded on 11-21, **4 days** from now | HIGH-001 note |
| Readiness latency | 5.91 s, then 4.52 s. Source-integrity responded in 0.06 s, but its `generated_at` matched the request time, so cache warmth is unknown | MED-022 |
| Canonical lineage | 6,004,837 / 6,028,448 exact (99.61%). Mapping coverage `NOT_MEASURED` | source-integrity |
| Buy board | Monday 11-16 21:00Z refresh was `degraded (0/127 quotes)`, `quote_refresh_incomplete`. There was no weekend refresh (Fri 11-13 21:00Z → Mon). Next refresh is 2026-11-17T14:30Z | LOW-014, LOW-015 |
| Database / disk / WAL / backup / restore | UNVERIFIED (no host access) | HIGH-009 |

## New findings

None verified. `main` is unchanged, so there is no new code to review.

## Prior findings

- **CRIT-001:** re-confirmed live (day 26). Open.
- **LOW-014:** re-confirmed on a weekday session: the Monday 21:00Z refresh got 0/127 quotes and was reported as `degraded`, not success.
- **LOW-015:** the weekend criterion is now met live: no refresh ran on 11-14 or 11-15, and the next refresh after Friday was on Monday. The item stays Partially addressed until the Thanksgiving (11-26) closure and the 11-27 early close are observed.
- **MED-010** (HTTP only), **MED-021** and **MED-022** (readiness 4.5–5.9 s): re-confirmed.
- **Register reconciliation:** 27 CONFIRMED / 4 SUSPECTED / 0 UNVERIFIED / 17 RESOLVED. HIGH-001, MED-019 and LOW-006 are RESOLVED (repository level) according to their latest dated updates, even though their original header lines still read Open. The LOW-003 entry concerns only a resolved calendar sub-issue; the item itself stays Partially addressed.
- All other items are unchanged (no code change).

## Tests (isolated, offline, `ACCOUNTANT_ENV=test`, `env -i`, no credentials, Python 3.11, scratch clone)

| Command | Result |
|---|---|
| `uv sync --locked --extra dev --python 3.11` | exit 0 |
| `ruff check src tests` | exit 0 |
| `python -m pytest -q` | exit 0. 601 collected, 601 passed, 0 failed, 0 skipped, 1 warning (starlette TestClient deprecation) |
| `python scripts/check_mypy_baseline.py` | exit 0. 236 existing errors across the full source tree, none new. This is a ratchet, not a clean type check |
| CI `main` | no new runs since 11-09. Latest run #91 (audit branch, 11-16) succeeded |

Not run: Docker build/compose, Alembic on PG16, coverage, restore drill.

## Next actions

1. **Urgent operations:** make a capacity decision and run a capacity-safe catch-up (CRIT-001/HIGH-003) before 11-21. After that date the default catch-up window is exceeded and an explicit catch-up range is needed.
2. **Recovery:** set up a scheduled backup and an isolated restore test on the systemd topology (HIGH-009/MED-005) before any archival.
3. **Correctness:** fix the valuation basis (HIGH-002) before reports resume.

## Not checked / unproven

Deployed SHA; database size, WAL, disk and logs; the scheduler unit; the SEC listing; restore; scoring recomputation (no new reports since 10-22); TLS.
