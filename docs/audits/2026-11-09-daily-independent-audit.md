# Accountant Daily Independent Audit — 2026-11-09

Run 33. Read-only. No secrets, tokens, DSNs or environment files are reproduced here.

## Evidence contract

| Item | Value |
|---|---|
| Audit time | 2026-11-09 01:52–02:20 EST (America/New_York, UTC−5), Monday, before the 09:30 open |
| Local / GitHub `main` | `438c1f1` (unchanged since the 2026-11-08 audit; `HEAD...origin/main` = 0/0) |
| Audit branch | `claude/charming-hopper-g1cvki`, clean worktree |
| Deployed commit | SHA UNVERIFIED. API `started_at=2026-11-08T06:49:33Z` (no restart since the last audit). Live payloads still carry `NYSE_CASH_2026_2028_V1` and `snapshot_cache_ttl_seconds=30.0`, features that exist only in `438c1f1` lineage (feature evidence, not SHA proof) |
| Previous audit | 2026-11-08 01:50–02:10 EST (run 32) |
| Access | Unauthenticated read-only HTTP GETs to the public Accountant host; GitHub Actions API; local isolated tests. No SSH, DB, logs, token or mutation. HTTPS has no listener |

## Verdict

**DEGRADED (live-confirmed).** Research-only readiness: **not ready** (gates failing: `machine_running`, `source_integrity=FAILED`, `blocked_companies`, `stability_window` 0/7). Execution remains prohibited by design (`execution_allowed=false`, `terminal_handoff_allowed=false`).

## Dashboard (live, 2026-11-09)

| Metric | Value | Evidence |
|---|---|---|
| `/health` | 200 in 0.09 s | 06:53:32Z |
| Storage gate | `database_cap_reached`, `storage_blocked=true` | `/api/reports/status` 06:53:38Z, 06:54:58Z, 06:55:46Z |
| Reports (distinct companies; `uq_company_reports_company`) | 2,134 / 4,473 (47.71%) | same cohort, same snapshot |
| Report cards | 2,105 | `/api/source-integrity` |
| Net coverage change | **0 over 128 s** (3 samples); `processed_cycles=0` since 2026-11-08T06:49Z | companies/minute not computable — no completion events |
| Workers | 8/8 `standby`; queue reported empty (`pending_companies=0`) while cache says "2339 pending" | MED-021 contradiction persists |
| Newest processed filing | filing date 2026-10-22, accepted 2026-10-22T20:39:57Z; "18 days old" | `/api/source-integrity` |
| EDGAR business days missed | 11 (10-23 → 11-06); today 11-09 will be the 12th | calendar |
| Halt duration | day 18 since the storage-gate halt | CRIT-001 |
| Readiness latency (cold) | **6.23 s** and **3.88 s** | MED-022 cold path unchanged |
| Buy board | 127 candidates counted, `/api/buy-board` = `[]`; `next_refresh_at=2026-11-09T14:30Z` | LOW-014 / LOW-015 |
| DB / disk / WAL | UNVERIFIED (no host access). Last operator figure 10-28: DB 14.91 GB vs 14 GiB cap | — |
| Backup / restore | UNVERIFIED; no restore of the systemd deployment recorded | HIGH-009 |

## New findings

### ACC-LOW-016 — Source-integrity "coverage percentages" mix planner estimates and non-coverage ratios (>100%)

- Severity Low · CONFIRMED (source + live) · Open
- Component: `src/accountant/research/source_integrity.py`
- Evidence: `:66-71` raw and canonical counts use `_estimated_count` (pg `reltuples`) on PostgreSQL, while `:76` already computes an exact `canonical_fact_count_exact`; `:113` `canonical_to_raw_pct` divides estimate by estimate; `:115` `statement_to_report_pct` divides statements by reports. Live 06:53:32Z: `canonical_to_raw_pct=106.56`, `statement_to_report_pct=187.54`. `canonical_to_raw_pct` feeds the `DEGRADED` grade threshold (`:199`).
- Consequence: fields named `*_pct` exceed 100% and are not coverage; a grade input depends on autovacuum-dependent planner estimates from two different cohorts. Operators can read 106% as "complete mapping".
- Repair: rename ratio fields (e.g. `statements_per_report`), label estimate-based ratios `_estimate`, or compute mapping coverage from exact, same-cohort counts (canonical facts with lineage / raw facts for the same companies). Do not let an estimate decide the grade.
- Effort S. Dependencies: MED-022 (count cost).
- Acceptance: no `*_pct` field can exceed 100; every grade input is exact or explicitly labelled estimate.
- Test: unit test with `reltuples` estimates inverted relative to exact counts; assert grade unchanged and ratio fields bounded.

## Prior findings

No code changed on `main` since `438c1f1`, so no status is closed by code. Live re-confirmations today: CRIT-001 (halt day 18, 0 progress), MED-010 (HTTP only, public), MED-021 remainder (empty queue vs 2,339 pending), MED-022 (cold readiness 3.9–6.2 s), LOW-014 remainder (127 vs 0), LOW-013 still RESOLVED (`/health/nonexistent` → 404 JSON). All other items unchanged.

Register reconciliation note: the 11-08 totals (CONFIRMED 27 / SUSPECTED 4 / RESOLVED 16) do not match an automated recount of explicit status markers in the item headers (13 RESOLVED). The three-item discrepancy should be reconciled by the next run; today's totals are carried forward plus the one new item.

## Tests (isolated, offline, `ACCOUNTANT_ENV=test`, `env -i`, no credentials)

| Command | Result |
|---|---|
| `uv sync --locked --extra dev` | ok (uv selected Python 3.13; CI uses 3.12) |
| `uv run ruff check src tests` | exit 0, "All checks passed" |
| `uv run pytest -q` | exit 0 — 596 passed, 0 failed, 0 skipped, 1 warning (Starlette httpx deprecation) |
| `uv run python scripts/check_mypy_baseline.py` | exit 0 — full-src debt unchanged at 236 errors, no new diagnostics. Scope: full `src` ratchet, not a clean type check |
| GitHub CI `main` 438c1f1 (run 42456227347) | success |

Not run: Docker build/compose (no daemon), `alembic upgrade/check` against PG16 (no isolated DB today), coverage, restore drill.

## Next actions

1. **Urgent operations:** clear the storage cap safely (archive-verified off-host staging, or authorised cap/disk change) so the report backlog and 12 missed EDGAR days can catch up — CRIT-001 / HIGH-003.
2. **Recovery:** install a scheduled backup and record one isolated restore for the systemd topology — HIGH-009 / MED-005.
3. **Correctness:** fix valuation basis (HIGH-002) before reports resume, so the catch-up does not mass-produce mis-scaled valuations.

## Not checked / unproven

Deployed SHA; DB size, WAL, disk, logs; scheduler unit state; SEC daily-index listing (no declared-contact User-Agent); restore; scoring recomputation sample (no new reports since 10-22); TLS. No claim of production readiness or autonomy.
