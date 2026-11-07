# Accountant Daily Independent Audit — 2026-11-07

- **Audit window:** 2026-11-07 01:51–02:15 EST (America/New_York, UTC−5), Saturday. Daily routine, run 31. Not an EDGAR business day.
- **Local repository:** `main` @ `7bf2012`, unchanged since 10-28 (tenth audit on this SHA). Audit branch `claude/charming-hopper-doyne8` equalled main before this artifact; clean worktree.
- **Other branches:** `Claude-Gpt-audit` @ `620de22`, unchanged since 11-02, not promoted.
- **Deployed commit:** SHA UNVERIFIED (no SSH, DB or SHA endpoint). API `started_at` still 2026-10-28T14:11:13Z (no restart in 9.7 days).
- **Previous audit:** 2026-11-06 01:51 EST (run 30).
- **Access:** repository; GitHub Actions API; unauthenticated read-only GETs over HTTP to the Accountant host. The SEC daily-index listing was **BLOCKED** (SEC returned its "undeclared automated tool" page; no contact User-Agent was configured, and the auditor did not add personal contact details). No SSH, DB, logs or token. No mutation attempted.
- **Scope:** REPOSITORY + LIMITED LIVE.

## 1. Verdict

**DEGRADED (live-confirmed).** The pipeline is still halted at the storage cap. Day 16 of the halt.

- **Research-only readiness: not ready.** Failing gates: `machine_running` (database_cap_reached), `source_integrity=FAILED`, `blocked_companies`, `stability_window` (0/7).
- **Execution:** prohibited by design. Live readiness shows `execution_allowed=false`, `terminal_handoff_allowed=false`.

## 2. Dashboard

| Metric | Value | Evidence |
|---|---|---|
| Liveness | `/health` 200 in 0.09 s | 06:51:52Z |
| Storage gate | `storage gate blocked: database_cap_reached` | `/api/reports/status` at 06:51:52Z, 06:52:40Z, 06:53:44Z |
| Scheduler cycles since restart | `processed_cycles=0`, `last_cycle_at=null` | same |
| Reports (distinct companies) | **2,134 / 4,473 (47.7%)**, unchanged since 10-28 | same; `/api/source-integrity` company_reports=2,134, report_cards=2,105 |
| Throughput | Net **0** over 112 s (three samples). Companies/minute not computable: no completion events. | three samples |
| Workers | 8/8 roles `standby` (storage-blocked) | same |
| Pending / runnable / blocked | 0 / 0 / 0 reported while blocked (MED-021 remainder) | same |
| Cache warmer | Deferred, 2,339 pending | `/api/cache/status` |
| SEC freshness | Newest processed filing 2026-10-22 (accepted 2026-10-22T20:39:57Z). Source integrity: "Latest SEC filing date is 16 days old." EDGAR business days since then: 10-23 through 11-06 = **11** (11-05 index was confirmed published on 11-06; 11-06 index publication UNVERIFIED today because the listing was blocked). | `/api/source-integrity` 06:51:59Z |
| Estimated counts | filings ≈3,858,445; raw facts ≈5,619,130; canonical facts ≈5,987,702 (estimates); statement snapshots 4,002 | `/api/source-integrity` |
| Readiness latency | `/api/deployment/readiness` **6.66 s**, `/api/source-integrity` **7.38 s**, anonymous (MED-022) | 06:52:06Z, 06:51:59Z |
| Buy board | `degraded buy board (0/127 quotes)`, `quote_refresh_incomplete`; last refresh 11-06 21:00Z; **next refresh 2026-11-07T14:30Z = Saturday 09:30 EST** (LOW-015 re-confirmed live on a non-session day); price source NONE for 168 rows | `/api/buy-board/status` 06:52:13Z |
| HTTPS | Fails (connection reset) | 06:52:13Z |
| DB / disk / WAL / backups | Not re-measured. Last operator record (10-28): DB 14.91 GB against a 14 GiB cap. | UNVERIFIED |
| CI | latest run 42177643590 (11-06 audit branch, docs only) success; main 7bf2012 green | Actions API |

## 3. New or regressed findings

None.

## 4. Prior findings (47 items)

- **Live re-confirmed today:** CRIT-001 (halt day 16; 11 business days unprocessed), MED-010 (HTTP only), MED-021 remainder, MED-022 (6.66 s / 7.38 s), LOW-014 remainder (0/127), LOW-015 (Saturday `next_refresh_at`).
- **Unchanged:** all other items keep their 11-06 dispositions.
- **Totals:** Critical 1, High 9, Medium 22, Low 15 · CONFIRMED 27, SUSPECTED 4, UNVERIFIED 0, RESOLVED 16.

## 5. Tests

| Command | Env | Result |
|---|---|---|
| `uv sync --frozen --all-extras`; `ACCOUNTANT_ENV=test uv run --frozen pytest -p no:cacheprovider -q` | main 7bf2012, Python 3.11, offline | exit 0, **566 passed / 0 failed / 0 skipped**, 1 warning (Starlette TestClient deprecation), 7.26 s |
| `uv run --frozen ruff check src tests` | same | All checks passed, exit 0 |

Not run: mypy (unchanged SHA; baseline 236–308 errors), coverage, Docker/compose (no daemon), alembic check, restore drill.

## 6. Three highest-impact next actions

1. **Operations, urgent (CRIT-001):** approve a reviewed cap/volume increase or archive-backed staging cleanup with verified off-host copies, then a capacity-safe catch-up of the 11 business-day backlog. The weekend is the lowest-risk window.
2. **Recovery (HIGH-009 / MED-005):** systemd-native scheduled backups plus one isolated restore drill, before any archival.
3. **Correctness (HIGH-002):** dated shares outstanding; separate per-share from company-wide values before cards leave UNVALIDATED.

## 7. Checks not run / limitations

- No SSH, DB, logs, WAL, disk or backup inspection. Deployed SHA UNVERIFIED.
- SEC daily-index listing BLOCKED (needs a declared contact User-Agent configured for the auditor).
- No authenticated endpoints. Scoring/valuation not recomputed (code unchanged since 10-28).
- Systemd units, runtime users, firewall not live-verified.
