# Accountant Daily Independent Audit — 2026-11-19

Run 41. Read-only. This file contains no secrets, tokens, DSNs or environment files.

## Evidence contract

| Item | Value |
|---|---|
| Audit time | 2026-11-19 01:52–02:30 EST (America/New_York, UTC−5), Thursday. Today's EDGAR index is not yet published |
| Local / GitHub `main` | `6b7d6f1`, unchanged since 11-09. `Claude-Gpt-audit` is unchanged |
| Audit branch | `claude/charming-hopper-6qpf8g` (at `6b7d6f1`). The worktree was clean before this artifact |
| Deployed commit | SHA UNVERIFIED. API `started_at=2026-11-09T12:36:53Z`, so no restart. `SOURCE_INTEGRITY_V2_EXACT_COHORTS` is live |
| Previous audit | 2026-11-18 run 40 (`claude/charming-hopper-f0d6cz`, `3b466a8`) |
| Access | Unauthenticated read-only HTTP GETs (port 80) and isolated local tests. No SSH, database, logs or token. HTTPS: no response |

## Verdict

**DEGRADED (live-confirmed).** Research-only readiness is **not ready**. `/api/deployment/readiness` failed four gates at 06:54:23Z and 06:55:40Z:
- `machine_running`: `database_cap_reached`
- `source_integrity`: `FAILED`
- `blocked_companies`: `database_cap_reached`
- `stability_window`: not persisted

Execution is prohibited by design.

## Dashboard (live, 06:54:16–06:55:40Z)

| Metric | Value |
|---|---|
| `/health`, `/ready` | 200 / 200 |
| Storage gate | `storage gate blocked: database_cap_reached`, `processed_cycles=0`, `storage_blocked=true` |
| Reports (distinct companies) | 2,134 / 4,473 (47.71%). Report cards: 2,105. Statement snapshots: 4,002 |
| Net coverage change | **0 over 78 s** (byte-identical status payloads). There are no completion events, so companies/minute cannot be computed |
| Workers | 8/8 `standby`. Pending/runnable/blocked = 0/0/0 while the gate blocks all work (MED-021) |
| Newest processed filing | Accepted 2026-10-22T20:39:57Z. `days_since_latest_filing=28`, `source_grade=FAILED` |
| EDGAR business days missed | **18** (10-23 → 11-18, excluding 11-11) |
| Halt duration | **day 28** |
| Catch-up window | The default 30-day `HISTORY_DAYS` window is exceeded on 11-21, **2 days** from now |
| Endpoint latency | Source-integrity **7.17 s** and **5.42 s**, both cold because each sample's `generated_at` equals the request time. Readiness 0.064 s on both samples (it was 6.85–7.14 s on 11-18). The cause of the readiness change is UNVERIFIED |
| Canonical lineage | 6,004,837 / 6,028,448 exact (99.61%) |
| Buy board | Wednesday 11-18 21:00Z refresh: `degraded buy board (0/127 quotes)`, `quote_refresh_incomplete`. **Third consecutive weekday**. Next refresh 2026-11-19T14:30Z |
| Database / disk / WAL / backup / restore | UNVERIFIED (no host access) |

## New findings
None verified. `main` is unchanged.

## Prior findings
- **CRIT-001:** re-confirmed live (day 28). Open.
- **MED-022:** source-integrity is still 5.4–7.2 s and unauthenticated. Readiness was fast in both samples today. Partially addressed. Cause UNVERIFIED.
- **LOW-014:** re-confirmed, third consecutive weekday at 0/127.
- **LOW-015:** unchanged. The holiday criterion is pending (11-26/11-27).
- **MED-010** and **MED-021:** re-confirmed.
- **Register:** 48 items (Critical 1, High 9, Medium 22, Low 16). 27 CONFIRMED / 4 SUSPECTED / 0 UNVERIFIED / 17 RESOLVED.

## Tests
Environment: offline, `ACCOUNTANT_ENV=test`, `env -i`, no credentials, Python 3.11, scratch clone of 6b7d6f1.

| Command | Result |
|---|---|
| `uv sync --locked --extra dev --python 3.11` | exit 0 |
| `ruff check src tests` | exit 0 |
| `python -m pytest -q` | exit 0. 601 tests, 0 failed, 0 errors, 0 skipped (junit). 1 warning |
| `python scripts/check_mypy_baseline.py` | exit 0. 236 existing errors, none new. This is a ratchet, not a clean type check |

Not run: Docker build/compose, Alembic on PG16, coverage, restore drill.

## Next actions
1. **Urgent operations:** a capacity decision and a capacity-safe catch-up (CRIT-001/HIGH-003) before 11-21. After that date, catch-up needs an explicit range.
2. **Recovery:** a scheduled backup plus an isolated restore test on the systemd topology (HIGH-009/MED-005).
3. **Correctness:** fix the valuation basis (HIGH-002) before reports resume.

## Not checked or unproven
The deployed SHA; database size, WAL, disk and logs; the scheduler unit; restore; scoring recomputation (no new reports since 10-22); TLS.
