# Accountant Daily Independent Audit — 2026-11-10

Run 34. Read-only. No secrets, tokens, DSNs or environment files are reproduced here.

## Evidence contract

| Item | Value |
|---|---|
| Audit time | 2026-11-10 01:52–02:15 EST (America/New_York, UTC−5), Tuesday, before the open |
| Local / GitHub `main` | `6b7d6f1` (new since the 11-09 audit: "Promote audited exact-cohort source coverage metrics"; `HEAD...origin/main` = 0/0) |
| Audit branch | `claude/charming-hopper-939ssu`, clean worktree |
| Deployed commit | SHA UNVERIFIED. API `started_at=2026-11-09T12:36:53Z` (restart ~1 min after the 6b7d6f1 CI run finished at 12:36:35Z). Live `/api/source-integrity` returns `version=SOURCE_INTEGRITY_V2_EXACT_COHORTS`, which exists only in 6b7d6f1 lineage (feature evidence, not SHA proof) |
| Previous audit | 2026-11-09 01:52–02:20 EST (run 33) |
| Access | Unauthenticated read-only HTTP GETs to the public Accountant host (port 80); GitHub Actions API; isolated local tests. No SSH, DB, logs, token or mutation. HTTPS: TLS handshake fails / no valid listener |

## Verdict

**DEGRADED (live-confirmed).** Research-only readiness: **not ready** (`machine_running`, `source_integrity=FAILED`, `blocked_companies`, `stability_window` 0/7 failing). Execution prohibited by design (`execution_allowed=false`, `terminal_handoff_allowed=false`).

## Dashboard (live)

| Metric | Value | Evidence |
|---|---|---|
| `/health`, `/ready` | 200 (0.08 s), ready, 4,473 companies | 06:54:35Z, 06:55:06Z |
| Storage gate | `database_cap_reached`, `storage_blocked=true`, `processed_cycles=0` since restart 2026-11-09T12:36:53Z | `/api/reports/status` 06:54:35Z, 06:56:21Z, 07:05:24Z |
| Reports (distinct companies) | 2,134 / 4,473 (47.71%); report cards 2,105 | same snapshot |
| Net coverage change | **0 over 649 s** (06:54:35Z → 07:05:24Z, 3 samples). Companies/minute not computable (no completion events) | — |
| Workers | 8/8 `standby`; `pending_companies=0` while cache says "2339 pending" | MED-021 remainder |
| Newest processed filing | 2026-10-22, accepted 2026-10-22T20:39:57Z; "19 days old" | `/api/source-integrity` |
| EDGAR business days missed | 12 (10-23 → 11-09); today 11-10 is the 13th. 11-11 (Veterans Day) is a federal holiday | calendar |
| Halt duration | day 19 | CRIT-001 |
| Source-integrity cold path | 5.86 s, 7.53 s; warm 0.06 s (30 s cache) | MED-022 |
| Coverage metrics (V2) | `report_coverage_pct=47.71`, `bottleneck_coverage_pct=100.0`, `canonical_lineage_coverage_pct=99.61` (6,004,837 / 6,028,448 exact); deprecated `canonical_to_raw_pct`/`statement_to_report_pct` = null; `mapping_coverage_status=NOT_MEASURED` | LOW-016 |
| Buy board | 2026-11-09 session refresh: `degraded buy board (0/127 quotes)`, `last_error=quote_refresh_incomplete`; `/api/buy-board`=[]; next refresh 2026-11-10T14:30Z; price source `NONE` for 168 rows | LOW-014 |
| DB / disk / WAL | UNVERIFIED (no host access). Last operator figure 10-28: DB 14.91 GB vs 14 GiB cap | — |
| Backup / restore | UNVERIFIED; no restore of the systemd deployment recorded | HIGH-009 |

## New findings

None verified today. No finding invented.

## Prior findings

- **ACC-LOW-016 → RESOLVED.** main 6b7d6f1 `src/accountant/research/source_integrity.py` replaces estimate/estimate and statements/reports "percentages" with exact same-cohort counts; ratio fields renamed (`canonical_to_raw_ratio_estimate`, `statements_per_report`); legacy `*_pct` nulled; grade basis `exact company-cohort counts only; planner estimates excluded`. `tests/test_nov9_source_metrics.py` passes in the full suite (601 passed). Live: no `*_pct` field above 100. Deployed SHA by feature evidence only.
- **CRIT-001** re-confirmed live (day 19, 0 progress over 649 s).
- **MED-021** remainder re-confirmed (empty queue vs 2,339 pending).
- **MED-022** re-confirmed (cold 5.9–7.5 s; V2 still runs an exact canonical-fact scan per cold snapshot).
- **LOW-014** remainder re-confirmed: the first weekday refresh after the restart again returned 0/127 quotes. Root cause UNVERIFIED.
- **MED-010** re-confirmed (HTTP only, public).
- All other items unchanged (no other code change on main).

## Tests (isolated, offline, `ACCOUNTANT_ENV=test`, `env -i`, no credentials)

| Command | Result |
|---|---|
| `uv sync --locked --extra dev` | ok (Python 3.11.18) |
| `ruff check src tests` | exit 0 |
| `python -m pytest -rA` | exit 0 — **601 passed**, 0 failed, 0 skipped, 1 warning |
| `python scripts/check_mypy_baseline.py` | exit 0 — full-src debt 236 errors, no new (ratchet, not a clean type check) |
| GitHub CI `main` 6b7d6f1 (run 42618267291) | success |

Not run: Docker build/compose (no daemon), alembic on PG16, coverage, restore drill.

## Next actions

1. **Urgent operations:** clear the storage cap safely (archive-verified off-host staging or an authorised cap/disk change) — CRIT-001 / HIGH-003. 13 EDGAR days now missed.
2. **Recovery:** scheduled backup + one isolated restore on the systemd topology — HIGH-009 / MED-005.
3. **Correctness:** fix valuation basis (HIGH-002) before reports resume.

## Not checked / unproven

Deployed SHA; DB size, WAL, disk, logs; scheduler unit state; SEC daily-index listing; restore; scoring recomputation sample (no new reports since 10-22); TLS. No claim of production readiness or autonomy.
