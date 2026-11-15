# Accountant Daily Independent Audit — 2026-11-15

Run 37. Read-only. No secrets, tokens, DSNs or environment files are reproduced here.

## Evidence contract

| Item | Value |
|---|---|
| Audit time | 2026-11-15 01:50–02:05 EST (America/New_York, UTC−5), Sunday (EDGAR closed; no SEC daily index expected) |
| Local / GitHub `main` | `6b7d6f1`, unchanged since 11-09 (`origin/main` = `6b7d6f1`); `Claude-Gpt-audit` `5c055cb` unchanged |
| Audit branch | `claude/charming-hopper-w23nur` (at `6b7d6f1`), clean worktree before this artifact |
| Deployed commit | SHA UNVERIFIED. API `started_at=2026-11-09T12:36:53Z` (no restart). `/api/source-integrity` returns `SOURCE_INTEGRITY_V2_EXACT_COHORTS` (6b7d6f1 lineage; feature evidence, not SHA proof) |
| Previous audit | 2026-11-14 run 36, `docs/audits/2026-11-14-daily-independent-audit.md` on `claude/charming-hopper-mtetaw` @ `3606ed0` |
| Access | Unauthenticated read-only HTTP GETs to the public Accountant host (port 80); GitHub Actions API; isolated local tests. No SSH, DB, logs, token or mutation. HTTPS: no response |

## Verdict

**DEGRADED (live-confirmed).** Research-only readiness: **not ready**. `/api/deployment/readiness` 06:52:09Z: `machine_running` fail (`database_cap_reached`), `source_integrity` fail (`FAILED`), `blocked_companies` fail, `stability_window` 0/7. Execution prohibited by design (`execution_allowed=false`, `terminal_handoff_allowed=false`).

## Dashboard (live)

| Metric | Value | Evidence |
|---|---|---|
| `/health`, `/ready` | 200 (0.07–0.08 s); `ready`, 4,473 companies | 06:52:03Z |
| Storage gate | `storage_blocked=true`, `database_cap_reached`; `processed_cycles=0` since restart 11-09T12:36:53Z; `last_cycle_at=null` | `/api/reports/status` 06:52:03Z, 06:52:48Z, 06:53:42Z |
| Reports (distinct companies) | 2,134 / 4,473 (47.71%); report cards 2,105; statement snapshots 4,002 | same |
| Net coverage change | **0 over 99 s** (3 samples). Companies/minute not computable (no completion events) | — |
| Workers | 8/8 `standby`, no ticker; pending/runnable/blocked 0/0/0 while gate blocks everything (MED-021) | — |
| Newest processed filing | 2026-10-22, accepted 2026-10-22T20:39:57Z; `days_since_latest_filing=24` | `/api/source-integrity` |
| EDGAR business days missed | **15** (unchanged; weekend). Monday 11-16 makes 16 | calendar |
| Halt duration | **day 24** | CRIT-001 |
| Source-integrity cold path | 5.78 s, then 3.10 s and 3.71 s | MED-022 |
| Coverage | report 47.71%; bottleneck 100% (2,134/2,134); canonical lineage 99.61% (6,004,837/6,028,448); mapping `NOT_MEASURED` | — |
| Buy board | last refresh 11-13T21:00Z `degraded (0/127 quotes)`, `quote_refresh_incomplete`; `/api/buy-board`=[]; next refresh 2026-11-16T14:30Z | LOW-014/015 |
| DB / disk / WAL / backup / restore | UNVERIFIED (no host access) | HIGH-009 |

## New findings

None verified. `main` unchanged; no new code to review.

## Prior findings

- CRIT-001 re-confirmed live (day 24). Open.
- MED-010 re-confirmed (HTTP only; HTTPS no response). MED-021, MED-022, LOW-014 re-confirmed. LOW-015 Partially addressed (Thanksgiving/early-close criteria pending).
- All others unchanged (no code change).

## Tests (isolated, offline, `ACCOUNTANT_ENV=test`, `env -i`, no credentials, Python 3.11)

| Command | Result |
|---|---|
| `uv sync --locked --extra dev --python 3.11` (scratch venv) | exit 0 |
| `ruff check src tests` | exit 0 |
| `python -m pytest -q` | exit 0 — 601 passed, 0 failed, 0 skipped, 1 warning |
| `python scripts/check_mypy_baseline.py` | exit 0 — 236 existing full-src errors, none new (ratchet, not a clean type check) |
| CI `main` | no new runs since 11-09 (last green run on 6b7d6f1) |

Not run: Docker build/compose, alembic on PG16, coverage, restore drill.

## Next actions

1. Urgent operations: capacity decision and capacity-safe catch-up (CRIT-001/HIGH-003). Explicit catch-up range needed after 11-21 (HIGH-001).
2. Recovery: scheduled backup and isolated restore on systemd topology (HIGH-009/MED-005) before any archival.
3. Correctness: valuation basis fix (HIGH-002) before reports resume.

## Not checked / unproven

Deployed SHA; DB size, WAL, disk, logs; scheduler unit; SEC listing; restore; scoring recomputation (no new reports since 10-22); TLS.
