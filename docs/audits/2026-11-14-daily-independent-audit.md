# Accountant Daily Independent Audit — 2026-11-14

Run 36. Read-only. No secrets, tokens, DSNs or environment files are reproduced here.

## Evidence contract

| Item | Value |
|---|---|
| Audit time | 2026-11-14 01:51–02:15 EST (America/New_York, UTC−5), Saturday (EDGAR closed; no new SEC daily index expected today) |
| Local / GitHub `main` | `6b7d6f1`, unchanged since the 11-10 audit (`origin/main` = `6b7d6f1`) |
| Audit branch | `claude/charming-hopper-mtetaw` (at `6b7d6f1`), clean worktree before this artifact |
| Deployed commit | SHA UNVERIFIED. API `started_at=2026-11-09T12:36:53Z` (no restart since 11-09). Live `/api/source-integrity` returns `SOURCE_INTEGRITY_V2_EXACT_COHORTS` (6b7d6f1 lineage; feature evidence, not SHA proof) |
| Previous audit | 2026-11-13 01:51–02:20 EST (run 35), artifact on `claude/charming-hopper-l8o139` @ `21c6ad1` |
| Access | Unauthenticated read-only HTTP GETs to the public Accountant host (port 80); GitHub Actions API; isolated local tests. No SSH, DB, logs, token or mutation. HTTPS: no response (curl 000) |

## Verdict

**DEGRADED (live-confirmed).** Research-only readiness: **not ready**. `/api/deployment/readiness` 06:52:33Z: `machine_running` fail (`database_cap_reached`), `source_integrity` fail (`FAILED`), `blocked_companies` fail, `stability_window` 0/7 days. Execution prohibited by design (`execution_allowed=false`, `terminal_handoff_allowed=false`).

## Dashboard (live)

| Metric | Value | Evidence |
|---|---|---|
| `/health`, `/ready` | 200 (0.08 s); `ready`, 4,473 companies | 06:52:26Z |
| Storage gate | `storage_blocked=true`, `database_cap_reached`; `processed_cycles=0` since restart 2026-11-09T12:36:53Z; `last_cycle_at=null` | `/api/reports/status` 06:52:26Z, 06:52:56Z, 06:56:36Z |
| Reports (distinct companies) | 2,134 / 4,473 (47.71%); report cards 2,105; statement snapshots 4,002 | same |
| Net coverage change | **0 over 250 s** (3 samples). Companies/minute not computable (no completion events) | — |
| Workers | 8/8 `standby`, no current ticker; pending/runnable/blocked = 0/0/0 while the storage gate blocks everything (MED-021) | — |
| Newest processed filing | 2026-10-22, accepted 2026-10-22T20:39:57Z; `days_since_latest_filing=23` | `/api/source-integrity` 06:52:26Z, 06:56:36Z |
| EDGAR business days missed | **15** (10-23; 10-26→10-30; 11-02→11-06; 11-09, 11-10, 11-12, 11-13; 11-11 federal holiday). Weekend: none added today | calendar |
| Halt duration | **day 23** (since 2026-10-22) | CRIT-001 |
| Source-integrity cold path | **6.87 s** and **6.88 s** (up from 5.1–6.2 s on 11-13) | MED-022 |
| Coverage (V2 exact cohorts) | report 47.71%, bottleneck 100.0% (2,134/2,134), canonical lineage 99.61% (6,004,837 / 6,028,448 exact); `mapping_coverage_status=NOT_MEASURED` | — |
| Buy board | 11-13 session refresh (21:00Z): `degraded buy board (0/127 quotes)`, `last_error=quote_refresh_incomplete`; `/api/buy-board`=[]; price source `NONE` for 168 rows; **next refresh 2026-11-16T14:30Z (Monday)** | LOW-014, LOW-015 |
| DB / disk / WAL | UNVERIFIED (no host access). Last operator figure 10-28: DB 14.91 GB vs 14 GiB cap | — |
| Backup / restore | UNVERIFIED; no restore of the systemd deployment recorded | HIGH-009 |

## New findings

None verified today. No finding invented. `main` is unchanged, so no new code was reviewed.

## Prior findings — status changes and evidence

- **CRIT-001** re-confirmed live: day 23, 0 net progress over 250 s, 15 EDGAR business days missed. Open.
- **LOW-015** evidence: the Friday 11-13 16:00 EST refresh was followed by `next_refresh_at=2026-11-16T14:30Z` (Monday 09:30 EST), with `calendar_version=NYSE_CASH_2026_2028_V1`. This meets the Friday→Monday criterion live. `tests/test_nov1_buy_board_calendar.py` + `tests/test_oct30_source_cache.py`: 30 passed. Thanksgiving (11-26) and early close (11-27) criteria still pending, so it stays **Partially addressed**.
- **LOW-014** remainder re-confirmed: the 11-13 session refresh got 0/127 quotes again (now every observed session since 10-28). Root cause UNVERIFIED.
- **MED-021** re-confirmed: queue shows 0 pending / 0 runnable / 0 blocked while every company is storage-blocked.
- **MED-022** re-confirmed and slower: cold path 6.87–6.88 s.
- **MED-010** re-confirmed: HTTP only, publicly reachable; HTTPS no response.
- All other items unchanged (no code change on `main`).

## Tests (isolated, offline, `ACCOUNTANT_ENV=test`, `env -i`, no credentials)

| Command | Result |
|---|---|
| `uv sync --locked --extra dev --python 3.11` (scratch venv) | exit 0 (Python 3.11.18) |
| `ruff check src tests` | exit 0 |
| `python -m pytest -q` | exit 0 — **601 passed**, 0 failed, 0 skipped, 1 warning (Starlette/httpx deprecation) |
| `python scripts/check_mypy_baseline.py` | exit 0 — full-src debt 236 errors, none new (a ratchet, not a clean type check) |
| GitHub CI `main` 6b7d6f1 (run 42618267291) | success; no new CI runs on `main` since 11-09 |

Not run: Docker build/compose (no daemon), alembic on PG16, coverage, restore drill.

## Next actions

1. **Urgent operations:** clear the storage cap safely (grow the volume, or archive with a verified off-host copy) — CRIT-001 / HIGH-003. 15 EDGAR days are already missed; Monday 11-16 adds the 16th. Catch-up must respect HIGH-001 residuals (the gap since 10-22 reaches the 30-day `HISTORY_DAYS` default on 11-21; an explicit catch-up range is needed after that) and MED-020.
2. **Recovery:** scheduled backup and one isolated restore on the systemd topology — HIGH-009 / MED-005, before any archival cleanup.
3. **Correctness:** fix the valuation basis (HIGH-002) before reports resume, so the backlog is not regenerated on a known-wrong basis.

## Not checked / unproven

Deployed SHA; DB size, WAL, disk, logs; scheduler unit state; SEC daily-index listing; restore; scoring recomputation sample (no new reports since 10-22); TLS. No claim of production readiness or autonomy.
