# Accountant Daily Independent Audit — 2026-10-27

- Audit time: 2026-10-27 02:52–03:20 EDT (America/New_York, UTC−4), Tuesday. Daily routine, run 20.
- EDGAR calendar: business day. One bounded read of the SEC public `daily-index/2026/QTR4/index.json` at 02:56 EDT shows `master.20261026.idx` as the newest index. Monday's index is published; today's (10-27) is not yet. ACC-MED-020 (in-window discovery runs recorded as PARTIAL/failed before publication) is therefore expected to recur today. The production effect was not observed. US DST ends Sun 2026-11-01. Next Monday's audit should confirm the polling window moves correctly.
- Repository: `main` @ `deec292` (unchanged since 2026-10-22; fifth consecutive audit on the same SHA). Working branch `claude/charming-hopper-h3tuxl` = `deec292` before this artifact. Worktree clean.
- Other branches: `Claude-Gpt-audit` @ `da3dbd0` (unchanged since 2026-10-21). No non-audit CI run since 2026-10-22. CI on `main` @ `deec292`: run 39852371657 success.
- Deployed commit: **UNVERIFIED**. No SSH, database or monitoring access. No operator record newer than `docs/audits/2026-10-22-readiness-hardening.md`.
- Scope: **REPOSITORY-LEVEL ONLY**.
- Tools: git, uv with a Python 3.11 venv, local scratch PostgreSQL 16 (isolated and non-production, stopped after use), GitHub Actions API (read-only), one bounded public SEC request. The Docker CLI is present but there is no daemon, so no image or compose validation was done.

## 1. Operational verdict

**DEGRADED / UNVERIFIED (unchanged).** Research-only readiness: **not ready**. Cards are deliberately `UNVALIDATED` and packet V2 returns `accepted=false`, which is the correct fail-closed behaviour. Execution is prohibited by design.

## 2. Dashboard

| Metric | Value | Status |
|---|---|---|
| Reports cached | 2,126 of 4,473 | operator note 2026-10-22 (5 days old); UNVERIFIED |
| Throughput | not computable | no observation window |
| Pending | 2,193 companies / 11,063 accessions | operator note; UNVERIFIED |
| Newest SEC daily index published | 2026-10-26 | public SEC listing, 02:56 EDT |
| Newest processed accepted_at | UNVERIFIED | no DB access |
| DB size / disk / WAL | ~14.6 GB vs 14 GiB cap; ~28.87 GB free; WAL UNVERIFIED | operator note; UNVERIFIED |
| Backup | one off-host 1.64 GB snapshot, checksum matched; no restore recorded | operator note |

## 3. New or regressed findings

None verified. Source is byte-identical to the 2026-10-26 audit.

## 4. Prior findings

- **ACC-MED-014 reproduced again** on a fresh UTF8 PG16. `alembic upgrade head` exit 0 (001→011). `alembic check` exit 255: it detects added tables `buy_board_candidates`, `buy_board_snapshots`, `company_reports` and `report_cards`, plus index `ix_statement_snapshots_company_id`.
- **ACC-CRIT-001** still has no newer runtime evidence. The pending backlog is now 5 days old without a recorded catch-up.
- **ACC-MED-020:** recurrence expected today, as above. It cannot be observed without production access.
- All other items are unchanged and carried forward. RESOLVED stays at 13.

Totals: 43 items (Critical 1, High 9, Medium 20, Low 13) · CONFIRMED 26, SUSPECTED 4, UNVERIFIED 0, RESOLVED 13. The full register is in the Notion task "Case Capital Accountant — Upgrade Backlog".

## 5. Tests (main @ deec292, Python 3.11, `ACCOUNTANT_ENV=test`, offline)

| Command | Result |
|---|---|
| `uv sync --frozen --extra dev` then `uv run --frozen --extra dev pytest -p no:cacheprovider -o addopts= -q` | exit 0; 526 passed / 0 failed / 0 skipped; 1 warning (Starlette TestClient deprecation) |
| `uv run --frozen ruff check src tests` | All checks passed |
| `uv run --frozen --extra dev python scripts/check_mypy_baseline.py` | 236 existing errors (full src), no new diagnostics. The tree is not type-clean. |
| `alembic upgrade head` / `alembic check` (scratch PG16) | 0 / 255 (MED-014) |

Process note: a first run without `--extra dev` used a pytest outside the project venv and exited 4 (`ModuleNotFoundError: sqlalchemy`). That was an audit-harness error, not a repository defect. The results above come from the corrected run.

Not run: Docker build/compose (no daemon), coverage, live endpoints, restore test, worker sampling.

## 6. Next actions

1. CRIT-001: decide on capacity and run a capacity-safe catch-up. Verify it with two report-count samples at least 60 s apart.
2. HIGH-009 / MED-005: a scheduled systemd backup with an off-host copy, plus one completed isolated restore.
3. HIGH-002 / MED-014: TTM and share-basis valuation inputs, and a migration for the 4 tables with `alembic check` in CI.

## 7. Not run / blocked

- Pass 1 (live API, scheduler, DB, worker, logs): BLOCKED.
- Pass 4 measurements: BLOCKED.
- Pass 3 recomputation: not repeated, because the code is unchanged.
- Deployed SHA, firewall/TLS, runtime users and Docker smoke tests: UNVERIFIED.

No readiness claim is made.
