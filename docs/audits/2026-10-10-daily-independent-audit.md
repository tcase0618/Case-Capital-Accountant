# Accountant daily independent audit — 2026-10-10

## Evidence header

- Audit run: 2026-10-10 02:51–03:40 EDT (America/New_York, UTC−4). Saturday; no SEC EDGAR dissemination today or tomorrow.
- Repository: `main` @ `7785df7` ("Select safe Oct 9 audit operational fixes with retention safeguard", 2026-10-09 17:21 EDT). Clean worktree. Audit branch `claude/charming-hopper-63k5j2` = `main`.
- `origin/Claude-Gpt-audit` @ `4c28c3b`: 11 ahead / 2 behind main. Grading, valuation, discovery, limiter, storage and migration fixes are still **not promoted**.
- Deployed commit: **UNVERIFIED**. This routine has no SSH, monitoring or API access.
- Previous audit: 2026-10-09 ~03:00 EDT (Notion task "Case Capital Accountant — Upgrade Backlog"; artifact on `claude/charming-hopper-1jmucd`).
- Tools: git, GitHub Actions API (read-only), uv/Python 3.12 venv, SQLite, and stubbed shell commands. No Docker daemon, no production PostgreSQL, no VPS.
- Scope: **REPOSITORY-LEVEL ONLY**. Passes 1, 2 and 4 cannot be checked live; they stay UNVERIFIED.

## Verdict

- Operations: **UNVERIFIED**. Code level: **DEGRADED**.
- Research-only readiness: not established. HIGH-001..006 (freshness, valuation, storage, worker visibility) are still open on `main`.
- Execution: prohibited by design. No order paths were found.

## Dashboard

| Item | Value | Evidence status |
|---|---|---|
| Report coverage, throughput, pending work, filing freshness, stage lag | not observable | UNVERIFIED |
| DB / disk / WAL size and headroom | not observable | UNVERIFIED |
| Backup / restore evidence | Repo now writes `status.json`, a `.counts` manifest and a `.restore_verified` marker. No live dump or restore observed. | UNVERIFIED (runtime) |
| CI on `main` HEAD 7785df7 | run 37992934630 (attempt 2): **FAILURE**. `docker` hit HTTP 429 from Docker Hub on `python:3.12-slim-bookworm`; `test` timed out pulling `postgres:16`. No test body ran. | CONFIRMED |
| CI on Claude-Gpt-audit 4c28c3b | run 37981306670: success | CONFIRMED |
| Local pytest (main) | 401 passed, 0 failed, 0 skipped, 1 warning; exit 0 | CONFIRMED |
| Coverage | 60% total; `report_machine.py` 17%, `buy_board.py` 17%, `canonical_ingestion.py` 29% (unchanged) | CONFIRMED |
| Ruff `src tests` / `scripts alembic` | clean / 14 errors (was 15) | CONFIRMED |
| Mypy, CI scope (2 files) | pass. The full package was not re-run (300 errors on 2026-10-09). | CONFIRMED (scope-limited) |

## What changed since 2026-10-09 (cedd614 → 7785df7)

Only `scripts/`, `docs/` and `tests/` changed. **No `src/` change.** Every source-code finding therefore keeps its 2026-10-09 line numbers and status.

- `docs/vps_readiness.md`: the restore drill no longer runs `dropdb`. It uses the mounted `/scripts`, `gosu postgres` and an `accountant_restore_test_*` scratch database.
- `scripts/backup_postgres.sh`: retention now runs before the headroom check. It keeps the 2 newest checksum-verified dumps and deletes nothing until that floor is met. It prunes orphaned sidecars, writes a `.counts` manifest from the archive, and writes `status.json`.
- `scripts/archive_row_count.sh` (new): counts COPY rows inside the dump.
- `scripts/verify_backup_restore.sh`: compares restored counts with archive counts instead of the live database.
- `scripts/vps_readiness_check.py`: adds backup-status freshness (36 h) and `storage_not_blocked` checks, and fixes the treatment of 0-day SEC staleness.
- `scripts/run_vps_scheduler.sh`: writes `$DATA_DIR/scheduler_cycle_status.json` with the exit code and logs "failed" instead of "complete".
- New tests: `tests/test_oct9_backups.py` (6 tests) and `tests/test_oct9_scheduler.py` (1 test). All pass locally.

## New findings

### ACC-MED-016 — `main` HEAD has no green CI; CI depends on anonymous Docker Hub pulls (NEW)

- Severity: Medium · Status: CONFIRMED · Current: Open
- Evidence: Actions run 37992934630 on `7785df7` (re-run, attempt 2).
  - `docker` job 114031857339: `429 Too Many Requests` on `registry-1.docker.io/.../python/manifests/3.12-slim-bookworm`.
  - `test` job 114031857519: `docker pull postgres:16` timed out 3 times, so the job never reached checkout or pytest.
  - `.github/workflows/ci.yml:10-12` (service `postgres:16`) and the Dockerfile `FROM python:3.12-slim-bookworm` pull anonymously.
- Consequence: the commit promoted to `main` has not been validated by CI. The promotion note itself says "GitHub CI must also pass". Any regression on HEAD is invisible until another push happens.
- Repair:
  - Re-run CI on `7785df7`.
  - Authenticate to Docker Hub in CI (read-only token), or pull from `public.ecr.aws/docker/library` / GHCR mirrors.
  - Pin images by digest. Treat a red infrastructure run as "not validated", not as "pass".
- Acceptance: both `test` and `docker` jobs are green on the current `main` SHA.
- Verification: the Actions run on the next `main` push, or a re-run of 37992934630.

## Prior findings — status changes (against main @ 7785df7)

| ID | New status | Proof |
|---|---|---|
| ACC-HIGH-008 restore runbook drops production | **RESOLVED (repository level)** | `docs/vps_readiness.md:125-143` contains no `dropdb`. Paths resolve to `/scripts` in the backup service (`docker-compose.prod.yml:83`). `test_restore_runbook_has_no_production_drop_and_uses_mounted_scripts` passes. Gaps: no CI compose smoke run, and green CI is missing (MED-016). |
| ACC-MED-015 blocked backup never prunes | **Partially addressed** | Pruning now precedes the headroom check (`backup_postgres.sh:36-64` before `:70-76`). `status.json` records `insufficient_disk_headroom`. **Stub reproduction:** with 3 legacy dumps (no `.sha256`) older than retention and headroom insufficient, the run exits 1, prunes nothing and records the failure. This is the documented safeguard, but backups stay halted until an operator acts. The status file is read only by the manual readiness script; nothing delivers an alert. |
| ACC-LOW-010 restore verifier vs live counts | **RESOLVED** | `verify_backup_restore.sh:24-32` uses `archive_row_count.sh`. `test_restore_uses_dump_snapshot_not_current_source` passes. |
| ACC-LOW-011 orphaned sidecars | **RESOLVED** | `backup_postgres.sh:58-64`. `test_blocked_backup_prunes_expired_sidecars_but_keeps_two_verified` passes. |
| ACC-LOW-006 scheduler loop / DST | Partially addressed (improved) | Failure is persisted to `scheduler_cycle_status.json` (`run_vps_scheduler.sh:23-42`). **No consumer reads it**: grep finds no reader in `scripts/` or `src/`, and readiness ignores it. Compose sets `ACCOUNTANT_AUTOMATION_INTERVAL_SECONDS` (`docker-compose.prod.yml:63`), which no script reads. |
| ACC-HIGH-003 storage gate | Open (one sub-item addressed) | `vps_readiness_check.py` now checks `storage_blocked` (field exists at `report_machine.py:214`). The core defect is unchanged: one preflight per cycle, growth baseline = 0, and reservations not shared. |
| ACC-MED-005 backups | Partially addressed (improved) | Counts manifest and status file added. Still no off-host copy, no scheduled restore and no CI dump/restore. |
| ACC-MED-001 grading (deferred branch fix) | Open on main; branch fix still defective | Independently reproduced on `4c28c3b` (`grading_evidence.py:16-19,99-111`). The sentence "…should no longer be relied upon because they do not comply with GAAP." returns `big_r_restatement=None` and `non_reliance_ambiguous=True`, because a sentence-wide `\bnot\b` suppresses an affirmative determination. The affirmative control sentence correctly returns True. This blocks promotion of the fix. |

All other items are **unchanged** from the 2026-10-09 register (`src/` is unchanged):
- Open: HIGH-001..006, MED-001..004, MED-008, MED-013, MED-014, LOW-004, LOW-005, LOW-007.
- Partially addressed: MED-006, MED-007, MED-010, MED-011, LOW-002, LOW-003, LOW-008.
- Resolved: HIGH-007, MED-009, MED-012, LOW-001, LOW-009. These remain resolved at repository level, but no CI is green on the current HEAD.

## Totals

- 35 items: Critical 0, High 8, Medium 16, Low 11.
- CONFIRMED 24 · SUSPECTED 3 (MED-004, MED-006, MED-007) · UNVERIFIED 0 · RESOLVED 8.

## Next three actions

1. **Ops/CI:** get green CI on `main` 7785df7 (MED-016). Every promoted fix needs this before it can be trusted.
2. **Correctness:** promote the reviewed fixes for HIGH-004 (visible worker failures) and HIGH-003 (storage gate). After that, HIGH-001/005/006 (discovery freshness and SEC budget). Stale or invisible research outranks cosmetic work.
3. **Correctness:** fix the disclosure classifier with clause-scoped negation and adversarial tests before promoting MED-001. Then do a populated-database upgrade drill for migrations 012–014 (MED-014).

## Checks not run / unproven

- Not checked live: API, scheduler, PostgreSQL, worker state, logs, two-point throughput sampling, SEC watermark, disk/WAL/backup footprint, deployed commit.
- Not checked against real systems:
  - Docker compose and image validation (no daemon locally; CI never got past image pull).
  - Real `pg_dump`/`pg_restore` of the new scripts (shell tests stub PostgreSQL).
  - The representative sector scoring sample (no production data).
- No claim of production readiness or autonomy is made.
