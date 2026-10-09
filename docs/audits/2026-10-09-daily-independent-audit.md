# Accountant Daily Independent Audit, 2026-10-09

- Audit time: 2026-10-09 ~03:00 EDT (America/New_York, UTC-4)
- Repository: `main` @ `cedd614`. Unpromoted `Claude-Gpt-audit` @ `a5ba414` (6 commits ahead).
- Deployed commit: UNVERIFIED. No SSH/monitoring access.
- Previous audit: 2026-10-08 03:02 EDT against `131d478`.
- Scope: REPOSITORY-ONLY. Live operations, freshness, storage, WAL, worker throughput and backups are all UNVERIFIED.
- Full backlog with evidence: Notion task "Case Capital Accountant - Upgrade Backlog".

## Verdict

**UNVERIFIED** for operations. Code-level state is **DEGRADED**.

- Research-only readiness: not established.
- Execution: prohibited by design. No order paths were found.

## Dashboard

| Item | Value |
|---|---|
| Coverage, throughput, pending work, freshness, stage lag | UNVERIFIED (no production access) |
| DB, disk and WAL size | UNVERIFIED |
| Backup and restore evidence | Scripts now checksum and run `pg_restore --list`. No off-host copy. No tested restore timestamp. |
| CI | Run 37766629049 on `cedd614` succeeded. Docker validate and image build passed. This is the first green main run. |
| Local tests | `python -m pytest -q` (SQLite, dummy env): exit 0, 394 passed, 0 failed, 0 skipped, 1 warning |
| Lint and types | `ruff src tests` clean. `ruff scripts alembic` has 15 errors. Mypy is clean on its 2-file CI scope. Full-package mypy has 300 errors in 36 files. |
| Coverage | 60% total. `report_machine.py` is at 17%. |
| Schema | `alembic check` on an empty PG16 FAILS: 4 tables, about 48 indexes and some FK/constraint drift. |

## New findings

**ACC-HIGH-008: the restore runbook drops the production database, then cannot restore.**
- `docs/vps_readiness.md:134` runs `dropdb`.
- `:136` then runs `pg_restore` from `/backups` inside the postgres container, which no longer mounts it (`docker-compose.prod.yml:9-10`).
- `:128` calls the wrong script path.

**ACC-MED-014: four tables exist only through `create_all`, which production now skips.**
- The tables are `company_reports`, `report_cards`, `buy_board_candidates` and `buy_board_snapshots`.
- `app.py:587-588` now skips `create_all` when running in production.
- Reproduced on a fresh PG16: `/health` returns 200 while `/api/reports` and `/api/buy-board` return 500.

**ACC-MED-015: backups stop silently once disk is short.**
- `backup_postgres.sh:19-22` exits before retention pruning at `:28`.
- Expired dumps are never removed, so backups stay blocked.
- The failure goes only to stderr.

**ACC-LOW-010: the restore verifier compares a past dump with live, changing row counts.**
- See `verify_backup_restore.sh:23-31`.
- Any insert after the dump makes the verification fail.

**ACC-LOW-011: pruning leaves `.sha256` and `.restore_verified` sidecars behind.**

**Deferred branch.** The two disclosure defects were independently CONFIRMED in `grading_evidence.py`. Both block promotion of the ACC-MED-001 fix.
- The going-concern candidate set excludes the latest 10-K when an 8-K is newer (`grading_evidence.py:46-55`).
- Conditional non-reliance wording triggers Big-R severity 95 (`grading_evidence.py:16-19`, `:79`).

## Prior findings

**RESOLVED** at repository/CI level. Deployment is still unverified.
- HIGH-007, MED-009, MED-012, LOW-001, LOW-009.

**Partially addressed:**
- MED-005, MED-006, MED-007, MED-010, MED-011.
- LOW-002, LOW-003, LOW-006, LOW-008.

**Unchanged on main, with a fix only on the unpromoted branch:**
- HIGH-001 to HIGH-006.
- MED-001, MED-002, MED-003, MED-008.
- LOW-007.

**Unchanged on all branches:**
- MED-004 (SUSPECTED), MED-013.
- LOW-004, LOW-005.

## Top three actions

1. **Correct the restore runbook (HIGH-008).** It is the only item an operator could trigger destructively just by following the repo docs.
2. **Make worker failures visible and fix the storage gate.** Covers HIGH-004 and HIGH-003, with MED-015 backup pruning. Stalled work and disk exhaustion are currently undetectable.
3. **Review and promote the data-correctness fixes, with the schema fix before any fresh deploy.**
   - Promote HIGH-001, HIGH-005, HIGH-006 and HIGH-002, after fixing the two disclosure defects on the branch.
   - Land the MED-014 migration and add `alembic check` to CI before any fresh deployment.

## Not run or unproven

- Every live check: deployed hash, worker snapshots 60 seconds apart, DB/WAL/disk usage, backup recency, and pg_dump version in the container.
- Docker runtime: no daemon was available.
- The MED-004 accepted_at timezone check.
- The representative sector sample for scoring.
