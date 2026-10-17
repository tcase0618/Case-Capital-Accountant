# Accountant daily independent audit — 2026-10-17

- **Audit time:** 2026-10-17 02:51–03:20 EDT (America/New_York, UTC−4), Saturday. Daily audit run 10. EDGAR does not disseminate on weekends; the last EDGAR business day was Fri 10-16 and the next is Mon 10-19.
- **Repository:** `main` @ `7785df7`, unchanged since 2026-10-09 17:21 EDT. Clean worktree. `origin/Claude-Gpt-audit` @ `4c28c3b` is unchanged. A fetch of every remote branch found no commits since 10-16 other than the 10-16 audit artifact (`claude/charming-hopper-ktvnux` @ `f4defd0`).
- **Deployed commit:** UNVERIFIED. The session has no SSH, monitoring or API access, and no production credentials or host configuration.
- **Previous audit:** 2026-10-16 (`docs/audits/2026-10-16-daily-independent-audit.md` on `claude/charming-hopper-ktvnux`, plus the Notion task).
- **Scope:** REPOSITORY-LEVEL ONLY.
- **Verdict:**
  - Operations: UNVERIFIED.
  - Code level: DEGRADED (unchanged).
  - Research-only readiness: not established.
  - Execution: prohibited by design; no order paths found.

## Passes 1–4 (live operations, freshness, scoring samples, storage)

UNVERIFIED. Without production access this audit states no coverage, throughput, lag, DB/WAL, backup or restore figures.

## Pass 5 (tests, isolated)

Environment: `uv sync --locked --extra dev` (the project venv resolved to Python 3.11.17; earlier runs used 3.12), `ACCOUNTANT_ENV=test`, `uv run --offline`, proxy pointed at a dead port for pytest. A throwaway local PostgreSQL 16 cluster (`127.0.0.1:55432`, trust auth) was used for the migration check and deleted afterwards.

- `uv run --frozen --offline pytest`: exit 0, 401 passed, 0 failed, 0 skipped, 1 warning (Starlette TestClient/httpx deprecation).
- `uv run --frozen ruff check src tests`: clean.
- `uv run --frozen mypy src/accountant/api/auth.py src/accountant/config.py`: pass. This covers 2 files only (ACC-LOW-005).
- **ACC-MED-014 re-reproduced on PostgreSQL 16:** `alembic upgrade head` (001→011) succeeds, `alembic check` fails with "New upgrade operations detected" (starting with `add_table buy_board_candidates`), and 0 of the 4 tables `company_reports`, `report_cards`, `buy_board_candidates`, `buy_board_snapshots` exist.
- CI: `main` 7785df7 run 37992934630 is still FAILURE and has not been re-run, now 8 days (ACC-MED-016).
- Re-verified: ACC-HIGH-001 evidence at `scripts/import_stale_sec_filings.py:133-141` is unchanged.

## Findings

- No new verified findings and no status changes.
- 35 items (Critical 0, High 8, Medium 16, Low 11) · CONFIRMED 24, SUSPECTED 3, UNVERIFIED 0, RESOLVED 8.

## Three highest-impact next actions

1. Re-run CI on `main` 7785df7, or push the next fix with a Docker Hub mirror or login (ACC-MED-016). Until then no `main` change is validated.
2. Add an Alembic migration for the four ORM-only tables and an `alembic check` CI step (ACC-MED-014). Production `/api/reports` and `/api/buy-board` depend on tables that migrations never create.
3. Fix ACC-HIGH-004 (worker failures hidden as standby), then ACC-HIGH-003 (storage gate). Then review and promote the ACC-HIGH-001 and ACC-HIGH-006 discovery fixes.

## Checks not run

- All live checks (Pass 1, 2 and 4), the deployed commit, and backup/restore evidence: no production access.
- Docker compose validation and image smoke test: not run today.
- Whole-package mypy and coverage: not re-measured (source unchanged since 10-09).
- Restore drill and representative sector scoring sample: no production data.
