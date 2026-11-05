# Accountant Daily Independent Audit — 2026-11-05

- **Audit window:** 2026-11-05 01:50–02:10 EST (America/New_York, UTC−5), Thursday. Daily routine, run 29. EDGAR business day; today's daily index not yet published.
- **Local repository:** `main` @ `7bf2012`, unchanged since 10-28 (eighth audit on this SHA). Audit branch `claude/charming-hopper-ez33wt` equalled main before this artifact; clean worktree.
- **Other branches:** `Claude-Gpt-audit` @ `620de22`, unchanged since 11-02, not promoted.
- **Deployed commit:** SHA UNVERIFIED (no SSH, DB or SHA endpoint). API `started_at` still 2026-10-28T14:11:13Z (no restart in 8 days).
- **Previous audit:** 2026-11-04 01:50 EST (run 28).
- **Access:** repository; GitHub Actions API; unauthenticated read-only GETs over HTTP to the Accountant host. The bounded SEC directory listing returned **403** today (one request, no retry), so SEC-side freshness is UNVERIFIED. No SSH, DB, logs or token. No mutation attempted.
- **Scope:** REPOSITORY + LIMITED LIVE.

## 1. Verdict

**DEGRADED (live-confirmed).** The pipeline is still halted at the storage cap. This is day 14 of the halt.

- **Research-only readiness: not ready.** Failing gates: `machine_running` (database_cap_reached), `source_integrity=FAILED`, `blocked_companies`, `stability_window` (0/7).
- **Execution:** prohibited by design. Live readiness shows `execution_allowed=false` and `terminal_handoff_allowed=false`.

## 2. Dashboard

| Metric | Value | Evidence |
|---|---|---|
| Liveness | `/health` 200 in 0.08 s | 06:53:03Z |
| Storage gate | `storage gate blocked: database_cap_reached` | `/api/reports/status` at 06:53:03Z, 06:53:39Z and 06:55:53Z |
| Scheduler cycles since restart | `processed_cycles=0`, `last_cycle_at=null` | same |
| Reports (distinct companies) | **2,134 / 4,473 (47.7%)**, unchanged since 10-28 | same |
| Throughput | Net **0** over 170 s (three samples). Companies/minute not computable: no completion events. | three samples |
| Workers | 8/8 roles `standby` (storage-blocked, not idle on an empty queue) | same |
| Pending / runnable / blocked | 0 / 0 / 0 reported while blocked (MED-021 remainder) | same |
| Cache warmer | Deferred, 2,339 pending | `/api/cache/status` |
| SEC freshness | Newest processed filing 10-22 (operator record). **9 EDGAR business days have elapsed** since then (10-23 to 11-04). Today's SEC listing check was BLOCKED (403), so whether the 11-04 index is published is unverified. | calendar plus prior evidence |
| Readiness | 200 in **6.32 s**, anonymous (MED-022) | 06:53:17Z |
| Buy board | `degraded buy board (0/127 quotes)`, `quote_refresh_incomplete`; last refresh 11-04 21:00Z; next 11-05 14:30Z | `/api/buy-board/status` |
| HTTPS | Fails (status 000) | 06:53Z |
| DB / disk / WAL / backups | Not re-measured. Last operator record (10-28): DB 14.91 GB against a 14 GiB cap. | UNVERIFIED |
| CI | main 7bf2012 green; `Claude-Gpt-audit` 620de22 green (no new commits) | Actions API |

## 3. New or regressed findings

None.

## 4. Prior findings (47 items)

- **Live re-confirmed today:** CRIT-001 (halt continues), MED-010 (HTTP only), MED-021 remainder (the blocked machine reports 0 pending), MED-022 (6.32 s anonymous readiness), LOW-014 remainder (0/127 quotes).
- **Unchanged:** all other items keep their 11-04 dispositions. LOW-015 remains Partially addressed, on branch 620de22 only.
- **Totals:** Critical 1, High 9, Medium 22, Low 15 · CONFIRMED 27, SUSPECTED 4, UNVERIFIED 0, RESOLVED 16.

## 5. Tests

| Command | Env | Result |
|---|---|---|
| `uv sync --frozen --all-extras`, then `ACCOUNTANT_ENV=test uv run --frozen pytest -p no:cacheprovider -q` | main 7bf2012, Python 3.11, offline | exit 0, **566 passed / 0 failed / 0 skipped** (counted from progress markers), 1 warning (Starlette TestClient deprecation) |
| `uv run --frozen ruff check src tests` | same | clean, exit 0 |

Not run: mypy (unchanged SHA; 236-error baseline), coverage, Docker/compose (no daemon), alembic check, restore drill.

## 6. Three highest-impact next actions

1. **Operations, urgent (CRIT-001):** make a capacity decision. Either approve a reviewed cap or volume increase, or do archive-backed staging cleanup with verified off-host copies. Then run a capacity-safe catch-up of the backlog of at least 9 business days.
2. **Recovery (HIGH-009 / MED-005):** add systemd-native scheduled backups and run one isolated restore drill.
3. **Correctness (HIGH-002):** use dated shares outstanding and separate per-share from company-wide values before cards leave UNVALIDATED.

## 7. Checks not run / limitations

- No SSH, DB, logs, WAL, disk or backup inspection. Deployed SHA UNVERIFIED.
- SEC listing returned 403. Discovery freshness on the SEC side is UNVERIFIED today.
- No authenticated endpoints. Scoring and valuation not recomputed (code unchanged).
- Systemd units, runtime users and firewall not live-verified.
