# Accountant Daily Independent Audit — 2026-10-26

- Audit time: 2026-10-26 02:54–03:30 EDT (America/New_York, UTC−4), Monday. Daily routine, run 19.
- EDGAR calendar: business day. The SEC public daily-index listing (one bounded read of `daily-index/2026/QTR4/index.json`, 02:58 EDT) shows `master.20261023.idx` as the newest published index. Today's (10-26) index is not yet published, so per ACC-MED-020 any in-window production discovery run before publication is expected to be recorded PARTIAL/failed. Production effect not observed. US DST ends Sun 2026-11-01.
- Repository: `main` @ `deec292` (unchanged since 2026-10-22; fourth consecutive audit on the same SHA). Working branch `claude/charming-hopper-jd52rw` = `deec292` before this artifact. Worktree clean.
- Other branches: `Claude-Gpt-audit` @ `da3dbd0` unchanged since 2026-10-21. No new CI run on any non-audit branch since 2026-10-22.
- Deployed commit: **UNVERIFIED**. No SSH, database or monitoring access. No operator record newer than `docs/audits/2026-10-22-readiness-hardening.md`.
- Scope: **REPOSITORY-LEVEL ONLY**.
- Tools: git, uv / Python 3.11.17 venv, local scratch PostgreSQL 16 (isolated, non-production, destroyed after use), GitHub Actions API (read-only), one bounded public SEC request.

## 1. Operational verdict

**DEGRADED / UNVERIFIED (unchanged).** Research-only readiness: **not ready** (cards deliberately `UNVALIDATED`; packet V2 `accepted=false`, correct fail-closed). Execution is prohibited by design.

## 2. Dashboard

| Metric | Value | Status |
|---|---|---|
| Reports cached | 2,126 of 4,473 | operator note 2026-10-22 (4 days old); UNVERIFIED |
| Throughput | not computable | no observation window |
| Pending | 2,193 companies / 11,063 accessions | operator note; UNVERIFIED |
| Newest SEC daily index published | 2026-10-23 | public SEC listing, observed 02:58 EDT |
| Newest processed accepted_at | UNVERIFIED | no DB access |
| DB size / disk / WAL | ~14.6 GB vs 14 GiB cap; ~28.87 GB free; WAL UNVERIFIED | operator note; UNVERIFIED |
| Backup | one off-host 1.64 GB snapshot, checksum matched; restore not recorded | operator note |
| CI on `main` @ `deec292` | run 39852371657: success | GitHub Actions |

## 3. New or regressed findings

None verified. Source is byte-identical to the 2026-10-25 audit.

## 4. Prior findings

- **ACC-MED-014: re-reproduced** on a fresh UTF8 PG16. `alembic upgrade head` exit 0 (001→011). `alembic check` exit 255: wants `add_table` for `buy_board_candidates`, `buy_board_snapshots`, `company_reports` and `report_cards`, plus index `ix_statement_snapshots_company_id`.
- **ACC-MED-020:** today is the first business day since the last observed recurrence, so recurrence is expected. Not observable without production access.
- All other items are unchanged and carried forward. RESOLVED stays at 13.

Totals: 43 items (Critical 1, High 9, Medium 20, Low 13) · CONFIRMED 26, SUSPECTED 4, UNVERIFIED 0, RESOLVED 13. Full register: Notion task "Case Capital Accountant — Upgrade Backlog".

## 5. Tests (main @ deec292, Python 3.11.17, `ACCOUNTANT_ENV=test`, offline)

| Command | Result |
|---|---|
| `uv run --frozen pytest -p no:cacheprovider -o addopts= -q` | exit 0; 526 passed / 0 failed / 0 skipped; 1 warning |
| `uv run --frozen ruff check src tests` | All checks passed |
| `uv run --frozen python scripts/check_mypy_baseline.py` | 236 existing errors (full src), no new diagnostics. The tree is not type-clean. |
| `alembic upgrade head` / `alembic check` (scratch PG16) | 0 / 255 (MED-014) |

Not run: Docker build/compose (no Docker), coverage, live endpoints, restore test, worker sampling.

## 6. Next actions

1. CRIT-001 capacity decision and capacity-safe catch-up, verified with two report-count samples at least 60 s apart.
2. HIGH-009 / MED-005: a scheduled systemd backup with an off-host copy, plus one completed isolated restore.
3. HIGH-002 / MED-014: TTM and share-basis valuation inputs; a migration for the 4 tables with `alembic check` in CI.

## 7. Not run / blocked

Pass 1 (live API, scheduler, DB, worker, logs) is BLOCKED. Pass 4 measurements are BLOCKED. Pass 3 recomputation was not repeated (code unchanged). Deployed SHA, firewall/TLS, runtime users and Docker smoke tests are UNVERIFIED. No readiness claim is made.
