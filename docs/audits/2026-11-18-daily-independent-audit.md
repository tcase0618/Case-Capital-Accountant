# Accountant Daily Independent Audit — 2026-11-18

Run 40. Read-only. This file contains no secrets, tokens, DSNs or environment files.

## Evidence contract

| Item | Value |
|---|---|
| Audit time | 2026-11-18 01:51–02:20 EST (America/New_York, UTC−5), Wednesday. Today's EDGAR index is not yet published (pre-open) |
| Local / GitHub `main` | `6b7d6f1`, unchanged since 11-09. `Claude-Gpt-audit` `5c055cb` unchanged (`git ls-remote`) |
| Audit branch | `claude/charming-hopper-f0d6cz` (at `6b7d6f1`). Worktree was clean before this artifact |
| Deployed commit | SHA UNVERIFIED. API `started_at=2026-11-09T12:36:53Z` (no restart). `SOURCE_INTEGRITY_V2_EXACT_COHORTS` is live: evidence of the 6b7d6f1 lineage, not proof of the SHA |
| Previous audit | 2026-11-17 run 39, `docs/audits/2026-11-17-daily-independent-audit.md` (branch `claude/charming-hopper-wv5brz`, commit `5df6c53`) |
| Access | Unauthenticated read-only HTTP GETs to the public Accountant host (port 80), the GitHub Actions API, and isolated local tests. No SSH, database, logs, token or mutation. HTTPS: no response (curl code 000) |

## Verdict

**DEGRADED (live-confirmed).** Research-only readiness is **not ready**. `/api/deployment/readiness` at 06:52:45Z and 06:54:09Z failed four gates: `machine_running` (`database_cap_reached`), `source_integrity` (`FAILED`), `blocked_companies` (`database_cap_reached`) and `stability_window` (seven-day evidence not persisted). Execution is prohibited by design (`research_only` gate passes; Accountant has no execution authority).

## Dashboard (live)

| Metric | Value | Evidence |
|---|---|---|
| `/health`, `/ready` | 200 / 200 | 06:51:53Z |
| Storage gate | `last_action="storage gate blocked: database_cap_reached"`, `processed_cycles=0` since the 11-09 restart, `last_cycle_at=null`, `last_error=null`, `recent_errors=[]` | `/api/reports/status` 06:51:53Z and 06:54:08Z |
| Reports (distinct companies) | 2,134 / 4,473 (47.71%). Report cards: 2,105. Statement snapshots: 4,002 | same + `/api/source-integrity` |
| Net coverage change | **0 over 135 s** (2 samples, byte-identical payloads). Companies/minute cannot be computed: there are no completion events | — |
| Workers | 8/8 `standby`, no ticker, no `last_completed_ticker`. Pending/runnable/blocked = 0/0/0 while the gate blocks all work (MED-021) | — |
| Newest processed filing | 2026-10-22, accepted 2026-10-22T20:39:57Z. `days_since_latest_filing=27`, `source_grade=FAILED` | `/api/source-integrity` 06:51:53Z |
| EDGAR business days missed | **17** completed days (10-23 → 11-17, excluding 11-11 Veterans Day). Today, 11-18, will be the 18th | calendar |
| Halt duration | **day 27** | CRIT-001 |
| Catch-up window | The default 30-day `HISTORY_DAYS` window is exceeded on 11-21, **3 days** from now | HIGH-001 note |
| Endpoint latency | readiness **6.85 s** and **7.14 s**; source-integrity **6.42 s** (11-17: readiness 4.5–5.9 s, source-integrity 0.06 s). Unauthenticated; worsening | MED-022 |
| Canonical lineage | 6,004,837 / 6,028,448 exact (99.61%). Mapping coverage `NOT_MEASURED`. Estimates: 3,858,445 filings, 5,619,130 raw facts (planner estimates, not exact) | source-integrity |
| Buy board | Tuesday 11-17 21:00Z refresh `degraded buy board (0/127 quotes)`, `last_error=quote_refresh_incomplete`. Next refresh 2026-11-18T14:30Z. Calendar `NYSE_CASH_2026_2028_V1` | `/api/buy-board/status` 06:53:00Z, LOW-014 |
| Database / disk / WAL / backup / restore | UNVERIFIED (no host access) | HIGH-009 |

## New findings

None verified. `main` is unchanged, so there is no new code to review.

## Prior findings

- **CRIT-001:** re-confirmed live (day 27). Open.
- **MED-022:** re-confirmed and worse: source-integrity took 6.42 s on the first request (30 s snapshot cache was cold), readiness 6.85–7.14 s. Partially addressed.
- **LOW-014:** re-confirmed: second consecutive weekday 21:00Z refresh with 0/127 quotes, reported `degraded`. Quote-failure cause UNVERIFIED.
- **LOW-015:** unchanged; holiday criterion pending (Thanksgiving 11-26 closed, 11-27 early close).
- **MED-010** (HTTP only), **MED-021**: re-confirmed.
- **Register:** 48 items (Critical 1, High 9, Medium 22, Low 16). 27 CONFIRMED / 4 SUSPECTED / 0 UNVERIFIED / 17 RESOLVED. No status changes.

## Tests (isolated, offline, `ACCOUNTANT_ENV=test`, `env -i` with proxy only, no credentials, Python 3.11, scratch clone of 6b7d6f1)

| Command | Result |
|---|---|
| `uv sync --locked --extra dev --python 3.11` | exit 0 |
| `ruff check src tests` | exit 0 |
| `python -m pytest -q` | exit 0. 601 passed, 0 failed, 0 skipped, 1 warning (starlette TestClient deprecation) |
| `python scripts/check_mypy_baseline.py` | exit 0. 236 existing errors across the full source tree, none new. A ratchet, not a clean type check |
| CI `main` | no new runs since 11-09. Latest run #92 (audit branch, 11-17) succeeded |

Not run: Docker build/compose, Alembic on PG16, coverage, restore drill.

## Next actions

1. **Urgent operations:** capacity decision and a capacity-safe catch-up (CRIT-001/HIGH-003) before 11-21; after that an explicit catch-up range is required.
2. **Recovery:** scheduled backup plus isolated restore test on the systemd topology (HIGH-009/MED-005) before any archival.
3. **Correctness:** fix the valuation basis (HIGH-002) before reports resume.

## Not checked / unproven

Deployed SHA; database size, WAL, disk and logs; scheduler unit; SEC listing; restore; scoring recomputation (no new reports since 10-22); TLS.
