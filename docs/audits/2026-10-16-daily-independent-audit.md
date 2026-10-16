# Accountant daily independent audit — 2026-10-16

- **Audit time:** 2026-10-16 02:52–03:45 EDT (America/New_York, UTC−4), Friday. Daily audit run 9. Today is a regular EDGAR business day.
- **Repository:** `main` @ `7785df7`, unchanged since 2026-10-09 17:21 EDT. Clean worktree. `origin/Claude-Gpt-audit` @ `4c28c3b` is unchanged. The only commits anywhere since 10-09 are the daily audit artifacts.
- **Deployed commit:** UNVERIFIED. There is no SSH, monitoring or API access, and the session has no production credentials or host configuration.
- **Previous audit:** 2026-10-15 (`docs/audits/2026-10-15-daily-independent-audit.md` on `claude/charming-hopper-slr8ce`, plus the Notion task).
- **Scope:** REPOSITORY-LEVEL ONLY.
- **Verdict:**
  - Operations: UNVERIFIED.
  - Code level: DEGRADED (unchanged).
  - Research-only readiness: not established.
  - Execution: prohibited by design; no order paths found.

## Passes 1–4 (live operations, freshness, scoring samples, storage)

UNVERIFIED. Without production access this audit states no coverage, throughput, lag, DB/WAL, backup or restore figures.

## Pass 5 (tests, isolated)

Environment: Python 3.12, `uv sync --locked --extra dev`, `ACCOUNTANT_ENV=test`, proxy pointed at a dead port. A throwaway local PostgreSQL 16 cluster (`127.0.0.1:55432`, trust auth, deleted after the run) was used for the migration check.

- `uv run --frozen pytest`: exit 0, 401 passed, 0 failed, 0 skipped, 1 warning (Starlette TestClient/httpx deprecation).
- `uv run --frozen ruff check src tests`: clean.
- `uv run --frozen mypy src/accountant/api/auth.py src/accountant/config.py`: pass. This covers 2 files only.
- `uv run --frozen mypy src` (whole package, informational): 308 errors in 39 of 121 files. This supports ACC-LOW-005. The count differs from the earlier 300/36 measurement, and today's run does not establish why.
- **ACC-MED-014 re-reproduced on PostgreSQL 16:** after `alembic upgrade head` (001→011), `alembic check` fails with "New upgrade operations detected" (starting with `add_table buy_board_candidates`). `company_reports`, `report_cards`, `buy_board_candidates` and `buy_board_snapshots` are absent (0 of 4 in `information_schema.tables`).
- CI: `main` 7785df7 run 37992934630 is still FAILURE and has not been re-run, now 7 days. ACC-MED-016 remains open.
- Re-verified: ACC-HIGH-001 evidence at `scripts/import_stale_sec_filings.py:133-141` is unchanged.

## Findings

- No new verified findings and no status changes. ACC-MED-014 and ACC-LOW-005 evidence was refreshed.
- 35 items (Critical 0, High 8, Medium 16, Low 11) · CONFIRMED 24, SUSPECTED 3, UNVERIFIED 0, RESOLVED 8.

## Three highest-impact next actions

1. Re-run CI on `main` 7785df7, or push the next fix with a Docker Hub mirror or login (ACC-MED-016). Without it, no `main` change is validated.
2. Add an Alembic migration for the four ORM-only tables and an `alembic check` CI step (ACC-MED-014). As it stands, production `/api/reports` and `/api/buy-board` depend on tables that migrations never create.
3. Fix ACC-HIGH-004 (worker failures hidden as standby), then ACC-HIGH-003 (storage gate). Then review and promote the ACC-HIGH-001 and ACC-HIGH-006 discovery fixes.

## Checks not run

- All live checks (Pass 1, 2 and 4), the deployed commit, and backup/restore evidence: no production access.
- Docker validation: the CLI is present but there is no daemon (`/var/run/docker.sock` is absent).
- Restore drill: not run.
- Representative sector scoring sample: no production data.
