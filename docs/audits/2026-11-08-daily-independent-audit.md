# Accountant Daily Independent Audit — 2026-11-08

- **Audit window:** 2026-11-08 01:50–02:10 EST (America/New_York, UTC−5), Sunday. Daily routine, run 32. Not an EDGAR business day.
- **Local repository:** `main` @ `438c1f1` (new since the last audit; committed 2026-11-08 01:48 EST). Audit branch `claude/charming-hopper-7zksdl` = `main` before this artifact; clean worktree.
- **Other branches:** `Claude-Gpt-audit` @ `620de22`, unchanged. Its `97d3c5d` (source-integrity cache) and `620de22` (NYSE quote calendar) were selectively promoted into `main` by `438c1f1` (see `docs/audits/2026-11-08-selective-promotion.md`).
- **Deployed commit:** SHA UNVERIFIED (no SSH, DB or SHA endpoint). The API **restarted at 2026-11-08T06:49:33Z**, about 1 minute after `438c1f1` was pushed. Live responses expose `calendar_version=NYSE_CASH_2026_2028_V1`, `last_session_date` and `truth_policy.snapshot_cache_ttl_seconds=30.0`. Those fields exist only in `438c1f1` on main (or the unpromoted branch commits it was built from). This is feature-level evidence, not SHA proof.
- **Previous audit:** 2026-11-07 01:51 EST (run 31).
- **Access:** repository; GitHub Actions API; unauthenticated read-only HTTP GETs to the Accountant host. No SSH, DB, logs, token or mutation. SEC daily-index listing not attempted (the auditor has no declared-contact User-Agent; the check was blocked on prior runs).
- **Scope:** REPOSITORY + LIMITED LIVE.

## 1. Verdict

**DEGRADED (live-confirmed).** The pipeline is still halted at the storage cap, day 17. Today's restart and deploy did not change the cap.

- **Research-only readiness: not ready.** Failing gates: `machine_running` (database_cap_reached), `source_integrity=FAILED`, `blocked_companies` (database_cap_reached), `stability_window` (0/7).
- **Execution:** prohibited by design (`execution_allowed=false`, `terminal_handoff_allowed=false`).

## 2. Dashboard

| Metric | Value | Evidence |
|---|---|---|
| Liveness | `/health` 200 in 0.07 s | 06:52:52Z, 06:53:36Z |
| API restart | `started_at=2026-11-08T06:49:33Z` (reports, buy board, cache warmer) | `/api/reports/status` |
| Storage gate | `storage gate blocked: database_cap_reached` | 06:52:52Z, 06:53:36Z, 06:58:10Z |
| Scheduler cycles since restart | `processed_cycles=0`, `last_cycle_at=null` | same |
| Reports (distinct companies) | **2,134 / 4,473 (47.7%)**, unchanged since 10-28 | same; `/api/source-integrity`: company_reports 2,134, report_cards 2,105 |
| Throughput | Net **0** over 318 s (three samples). Companies/minute not computable: no completion events. | three samples |
| Workers | 8/8 roles `standby` | same |
| Pending / runnable / blocked | 0 / 0 / 0 while blocked (MED-021 remainder) vs cache warmer "2339 pending" | `/api/cache/status` 06:52:56Z |
| SEC freshness | Newest processed filing 2026-10-22 (accepted 2026-10-22T20:39:57Z). "Latest SEC filing date is 17 days old." EDGAR business days since: 10-23 to 11-06 = **11** (11-06 index publication UNVERIFIED). | `/api/source-integrity` 06:52:52Z |
| Estimated counts | filings ≈3,858,445; raw facts ≈5,619,130; canonical facts ≈5,987,702 (estimates); statement snapshots 4,002 (exact) | same |
| Source-integrity latency | Cold (cache miss) **3.12 s / 3.26 s / 3.52 s**; readiness served within the 30 s cache window in 0.06 s | 06:52:52Z, 06:53:36Z, 06:58:10Z |
| Buy board | `next_refresh_at=2026-11-09T14:30:00Z` (Monday 09:30 EST) on a Sunday; `calendar_version=NYSE_CASH_2026_2028_V1`; `candidate_count=127`; `/api/buy-board` = `[]`; price source NONE ×168 | `/api/buy-board/status` 06:52:56Z |
| Unknown health path | `/health/nonexistent` → 404 (LOW-013 stays resolved) | 06:53:40Z |
| HTTPS | Fails (no TLS listener) | 06:52:56Z |
| DB / disk / WAL / backups | Not measured. Last operator record (10-28): DB 14.91 GB vs 14 GiB cap. | UNVERIFIED |
| CI | Run 42456227347 on `main` 438c1f1: success | Actions API |

## 3. New or regressed findings

None new. No regression found.

## 4. Prior findings — status changes

- **ACC-MED-022 (Partially addressed → still Partially addressed, now on main and live).** The 30 s single-flight cache (`source_integrity.py`, `SourceIntegrityCache`) is on main 438c1f1 and evidenced live. A cold snapshot still takes 3.1–3.5 s, and the anonymous route still runs exact counts on every cache miss. Polls more than 30 s apart always miss. Acceptance (p95 < 500 ms; no exact `canonical_facts` scan from anonymous callers) is not met.
- **ACC-LOW-015 (Open → Partially addressed, deployed).** `ops/nyse_calendar.py` and the calendar-walking `_next_refresh_time` are on main. Live on a Sunday, `next_refresh_at` points to Monday 09:30 EST. The two promoted test files pass (30 tests). RESOLVED needs a live post-close observation on Friday 11-13 (expected Monday 11-16 14:30Z) and a Thanksgiving 11-26 skip.
- **Live re-confirmed:** CRIT-001 (day 17), MED-010 (HTTP only), MED-021 remainder, LOW-014 remainder (127 counted vs `[]` listed; quote success after restart not yet observable).
- **Unchanged:** all other items keep their 11-07 dispositions.
- **Totals:** 47 items. Critical 1, High 9, Medium 22, Low 15 · CONFIRMED 27, SUSPECTED 4, UNVERIFIED 0, RESOLVED 16.

## 5. Tests

| Command | Env | Result |
|---|---|---|
| `uv sync --frozen --all-extras`; `ACCOUNTANT_ENV=test uv run --frozen pytest -p no:cacheprovider -q --junitxml=…` | main 438c1f1, Python 3.11, offline | exit 0; **596 tests, 0 failures, 0 errors, 0 skipped**; 1 warning (Starlette TestClient deprecation); 7.23 s |
| `pytest tests/test_nov1_buy_board_calendar.py tests/test_oct30_source_cache.py` | same | 30 passed |
| `uv run --frozen ruff check src tests` | same | All checks passed |

The suite grew from 566 to 596 tests; the 30 new tests are the two promoted files. Not run: mypy (baseline 236–308 errors on the full tree), coverage, Docker/compose (no daemon), `alembic check`, restore drill.

## 6. Three highest-impact next actions

1. **Operations, urgent (CRIT-001).** Today's deploy shows operator access. Use it for a reviewed cap or volume increase, or archive-backed staging cleanup with verified off-host copies, then a capacity-safe catch-up of the 11-business-day backlog before Monday's EDGAR publication adds a 12th.
2. **Recovery (HIGH-009 / MED-005).** Add systemd-native scheduled backups and run one isolated restore drill before any archival.
3. **Correctness (HIGH-002).** Use dated shares outstanding, and separate per-share values from company-wide values, before report cards leave UNVALIDATED.

These outrank cosmetic work because the research output is 17 days stale and cannot be recovered without a working backup.

## 7. Checks not run / limitations

- No SSH, DB, logs, WAL, disk or backup inspection. Deployed SHA UNVERIFIED (feature evidence only).
- SEC daily-index listing not checked (no declared-contact User-Agent for the auditor).
- No authenticated endpoints. Scoring and valuation were not recomputed; scoring code is unchanged since 10-28.
- Systemd units, runtime users and firewall were not live-verified.
