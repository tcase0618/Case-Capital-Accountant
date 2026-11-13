# Accountant Daily Independent Audit — 2026-11-13

Run 35. Read-only. No secrets, tokens, DSNs or environment files are reproduced here.

## Evidence contract

| Item | Value |
|---|---|
| Audit time | 2026-11-13 01:51–02:20 EST (America/New_York, UTC−5), Friday, before the open |
| Local / GitHub `main` | `6b7d6f1`, unchanged since the 11-10 audit (`HEAD...origin/main` = 0/0) |
| Audit branch | `claude/charming-hopper-l8o139`, clean worktree before this artifact |
| Deployed commit | SHA UNVERIFIED. API `started_at=2026-11-09T12:36:53Z` (no restart since the 11-10 audit). Live `/api/source-integrity` still returns `version=SOURCE_INTEGRITY_V2_EXACT_COHORTS` (6b7d6f1 lineage; feature evidence, not SHA proof) |
| Previous audit | 2026-11-10 01:52–02:15 EST (run 34). **No audit artifact or Notion update exists for 11-11 or 11-12**, so those two scheduled runs did not complete |
| Access | Unauthenticated read-only HTTP GETs to the public Accountant host (port 80); GitHub Actions API; isolated local tests. No SSH, DB, logs, token or mutation. HTTPS: no response |

## Verdict

**DEGRADED (live-confirmed).** Research-only readiness: **not ready**. `/api/deployment/readiness` 06:53:52Z: `machine_running` fail (`database_cap_reached`), `source_integrity` fail (`FAILED`), `blocked_companies` fail, `stability_window` 0/7 days. Execution is prohibited by design (`execution_allowed=false`, `terminal_handoff_allowed=false`).

## Dashboard (live)

| Metric | Value | Evidence |
|---|---|---|
| `/health`, `/ready` | 200 (0.09 s); `ready`, 4,473 companies | 06:53:45Z |
| Storage gate | `storage_blocked=true`, `database_cap_reached`; `processed_cycles=0` since restart 2026-11-09T12:36:53Z; `last_cycle_at=null` | `/api/reports/status` 06:53:45Z, 06:55:20Z, 06:58:09Z |
| Reports (distinct companies) | 2,134 / 4,473 (47.71%); report cards 2,105 | same |
| Net coverage change | **0 over 264 s** (3 samples). Companies/minute not computable (no completion events) | — |
| Workers | 8/8 `standby`; `pending_companies=0`, `runnable_companies=0`, `blocked_companies=0` while the storage gate blocks everything (MED-021) | — |
| Newest processed filing | 2026-10-22, accepted 2026-10-22T20:39:57Z; `days_since_latest_filing=22` | `/api/source-integrity` 06:53:45Z |
| EDGAR business days missed | **14** (10-23, 10-26 → 10-30, 11-02 → 11-06, 11-09, 11-10, 11-12; 11-11 Veterans Day is a federal holiday). Today 11-13 will be the 15th | calendar |
| Halt duration | **day 22** (since 2026-10-22) | CRIT-001 |
| Source-integrity cold path | **6.19 s** and **5.08 s** | MED-022 |
| Coverage (V2 exact cohorts) | report 47.71%, bottleneck 100.0% (2,134/2,134), canonical lineage 99.61% (6,004,837 / 6,028,448 exact); `mapping_coverage_status=NOT_MEASURED` | — |
| Buy board | 11-12 session refresh (21:00Z): `degraded buy board (0/127 quotes)`, `last_error=quote_refresh_incomplete`; `/api/buy-board`=[]; price source `NONE` for 168 rows; next refresh 2026-11-13T14:30Z | LOW-014 |
| DB / disk / WAL | UNVERIFIED (no host access). Last operator figure 10-28: DB 14.91 GB vs 14 GiB cap | — |
| Backup / restore | UNVERIFIED; no restore of the systemd deployment recorded | HIGH-009 |

## New findings

None verified today. No finding invented. `main` is unchanged, so no new code was reviewed.

## Prior findings

- **CRIT-001** re-confirmed live: day 22, 0 net progress over 264 s, 14 EDGAR business days missed.
- **MED-021** re-confirmed: the queue reports 0 pending, 0 runnable and 0 blocked while every company is storage-blocked.
- **MED-022** re-confirmed: cold path 5.1–6.2 s.
- **LOW-014** remainder re-confirmed: the 11-12 session refresh got 0/127 quotes again. Root cause UNVERIFIED.
- **MED-010** re-confirmed: HTTP only, publicly reachable.
- All other items unchanged (no code change on `main`).

## Tests (isolated, offline, `ACCOUNTANT_ENV=test`, `env -i`, no credentials)

| Command | Result |
|---|---|
| `uv sync --locked --extra dev` | ok (Python 3.11.18) |
| `ruff check src tests` | exit 0 |
| `python -m pytest -q` | exit 0 — **601 passed**, 0 failed, 0 skipped, 1 warning (Starlette/httpx deprecation) |
| `python scripts/check_mypy_baseline.py` | exit 0 — full-src debt 236 errors, none new (a ratchet, not a clean type check) |
| GitHub CI `main` 6b7d6f1 (run 42618267291) | success |

Not run: Docker build/compose (no daemon), alembic on PG16, coverage, restore drill.

## Next actions

1. **Urgent operations:** clear the storage cap safely (grow the volume, or archive with a verified off-host copy) — CRIT-001 / HIGH-003. Fifteen EDGAR days will be missed by tonight. Catch-up must respect HIGH-001 (watermark skips dates).
2. **Recovery:** scheduled backup and one isolated restore on the systemd topology — HIGH-009 / MED-005. This must happen before any archival cleanup.
3. **Correctness:** fix the valuation basis (HIGH-002) before reports resume, so the backlog is not regenerated on a known-wrong basis.

## Not checked / unproven

Deployed SHA; DB size, WAL, disk, logs; scheduler unit state; SEC daily-index listing; restore; scoring recomputation sample (no new reports since 10-22); TLS. Why the 11-11 and 11-12 audit runs did not complete is unknown. No claim of production readiness or autonomy.
