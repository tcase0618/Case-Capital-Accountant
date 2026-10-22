# Accountant daily independent audit — 2026-10-22

Daily run 15. Repository-level audit plus review of operator-recorded VPS evidence. No production access from this session.

## Evidence contract

- Audit time: 2026-10-22 02:51–03:40 EDT (America/New_York, UTC−4), Thursday. Regular EDGAR business day.
- Local commit: `main` @ `6486343` ("Honor worker storage reserve in unattended scheduler admission", 2026-10-21 08:27 EDT). Clean worktree. Previous audit commit: `e234b26`. New since then: `c37687f`, `6486343`.
- CI: run 39598945481 on `c37687f` success; run 39599723203 on `6486343` success.
- Deployed commit: `c37687f` according to the operator note `docs/audits/2026-10-21-selective-promotion.md` ("VPS fast-forwarded to that exact SHA"). Whether `6486343` was deployed is not recorded, so it is UNVERIFIED. This session did not observe the VPS.
- Previous audit: 2026-10-21 02:53–03:20 EDT (run 14).
- Tools and access: git, uv, Python 3.11, local throwaway PostgreSQL 16, GitHub Actions read access. No SSH, API, database or monitoring access to production. A Docker CLI is present but there is no daemon.

## Operational verdict

- **Operations: BLOCKED** (operator-recorded evidence from 2026-10-21; current state UNVERIFIED). Research-only readiness: **not ready**. Execution remains prohibited by design, and no order path exists.
- The 2026-10-21 VPS preflight recorded in the repository showed:
  - `storage_blocked=true` with `database_cap_reached` (14,902,639,639 bytes against a 14 GiB cap plus a 128 MiB reserve)
  - source integrity FAILED, with the latest filing dated 2026-10-06
  - 4,473 companies, 2,121 reports (47.4%) and 2,092 report cards
  - root volume of 48G, with 21G used and 27G available, against a configured minimum free disk of 25 GB
- After the restart, the worker storage gate was still blocked.

## Dashboard

| Item | Value | Status |
|---|---|---|
| Report coverage | 2,121 / 4,473 companies (47.4%) on 2026-10-21 | operator-recorded; not comparable to any prior measured value |
| Throughput | none: the machine is storage-blocked | operator-recorded |
| Filing freshness | latest filing 2026-10-06, which is 12 EDGAR business days before 10-22 | operator-recorded |
| DB size / cap | 14.90 GB / 14 GiB (15.03 GB) | operator-recorded |
| Disk free / floor | 27G / 25 GB | operator-recorded |
| WAL, logs, backups | — | UNVERIFIED |
| Backup/restore | no evidence that a backup exists for the systemd deployment (see ACC-HIGH-009) | UNVERIFIED |
| Deployed / local | `c37687f` (recorded) / `6486343` | partial |

## New findings (ranked)

### ACC-CRIT-001 — Production research pipeline halted at the storage cap; data stale since 2026-10-06

- Status: CONFIRMED (operator-recorded VPS preflight, 2026-10-21; current state UNVERIFIED) · Open
- Evidence: `docs/audits/2026-10-21-selective-promotion.md:40-46, 55-70`. The guards are `.env.production.example:25-28` (`MAX_DATABASE_GB=14`, `MIN_FREE_DISK_GB=25`, `WORKER_RESERVE_MB=128`) and `scripts/run_accountant_automation.py:101-129`, where a blocked preflight returns 0 without running anything.
- Consequence: no new filings, reports or report cards. The research packet served to the Terminal is 12 EDGAR business days stale, and only 47% of the universe has a report. Disk headroom above the 25 GB floor is about 2 GB, so raising the database cap alone would buy at most about 2 GB before the disk guard blocks.
- Repair: an operator decision is required, and this audit made no change. Options are a larger volume, or archiving with a verified off-host copy, retained provenance and a tested restore before any cleanup. Then re-measure growth.
- Acceptance: `storage_blocked=false`; the newest processed `accepted_at` is within 1 EDGAR business day; distinct-company completions are above zero across two samples at least 60 s apart.

### ACC-HIGH-009 — The production systemd deployment has no repository-managed backup or API unit; backup tooling and docs are Docker-only

- Status: SUSPECTED for production backups; CONFIRMED for the repository gap · Open
- Evidence:
  - The VPS runs systemd services (API, scheduler, PostgreSQL and nginx) under user `casecapital` at `/opt/case-capital/accountant` (operator note; `deploy/case-capital-accountant-scheduler.service:9-12`).
  - `deploy/` contains only the scheduler unit. `After=case-capital-accountant.service` references an API unit that is not in the repository.
  - Backup, retention and verify scripts run only through the compose `backup` service (`docs/vps_readiness.md:127-145`).
  - The 10-21 VPS preflight does not mention backups.
- Consequence: a 14.9 GB production database may have no scheduled backup. Even if one exists, there is no repository-managed dump, checksum, retention, status file or restore test for this topology. Same-host dumps would also compete for the roughly 2 GB of headroom.
- Repair: commit the actual systemd API, backup timer and service units, with off-host transfer, `status.json` and a scheduled scratch restore. Alternatively, document that Docker is the production path and migrate to it.
- Acceptance: read-only VPS evidence of a dump under 36 h old, its checksum, an off-host copy and a scratch-restore timestamp.

### ACC-MED-019 — Storage-blocked scheduler cycles are recorded as "complete" with exit code 0

- Status: CONFIRMED (source and an existing test) · Open
- Evidence: `scripts/run_accountant_automation.py:109-129` returns (comment at `:128`) 0 when blocked ("controlled pause"). `scripts/run_vps_scheduler.sh:23-31` then writes `status=complete`, and `scripts/vps_readiness_check.py:121-131` treats that as `scheduler_recent_and_successful`. `tests/test_scheduler_storage_reserve.py:45-46` asserts `main() == 0`.
- Consequence: the scheduler status file reports success during a multi-day halt. Full readiness still fails through `storage_not_blocked`, but any monitor that reads only the status file shows green.
- Repair: write a distinct `status=paused_storage` with the reason, keep exit 0 if desired, and have readiness reject it.
- Test: a blocked preflight writes `paused_storage`, and readiness returns false for it.

### ACC-LOW-012 — Storage limits default to 0, which disables them, when environment values are absent

- Status: CONFIRMED (source) · Open · `src/accountant/config.py:49-63`. A systemd `EnvironmentFile` missing these keys runs with no storage governor.
- Repair: fail closed in production when the limits are unset. Test: production settings with the keys missing raise an error at startup.

### ACC-LOW-013 — Unknown `/health/*` paths return the SPA page with 200

- Status: CONFIRMED (source; the operator observed `/health/db`) · Open · `src/accountant/api/app.py:1909-1911` excludes only `api/`, `companies/` and `assets/`. Monitors that probe a mistyped health path receive 200.
- Repair: add `health` to the excluded prefixes so these paths return 404. Test: GET `/health/db` returns 404.

## Prior findings — status changes

- **ACC-HIGH-003 → Partially addressed.** `6486343` adds `reserved_bytes` to scheduler admission (`scripts/run_accountant_automation.py:107`, test `tests/test_scheduler_storage_reserve.py`). The core defect is unchanged. `cycle_start_database_bytes=database_bytes` is still a zero-growth baseline (`:106`), with one preflight per cycle and no cross-process reservation.
- **ACC-LOW-003:** the calendar sub-issue is resolved at repository level. `src/accountant/ops/edgar_calendar.py` and `scripts/vps_readiness_check.py:88-102` count EDGAR business days. The main item (healthcheck semantics) stays Partially addressed.
- **ACC-LOW-005 → Partially addressed.** The full-source mypy ratchet (`scripts/check_mypy_baseline.py`, CI step) holds 308 baseline errors. It passed locally.
- **ACC-MED-014:** re-reproduced on a fresh PG16. `alembic upgrade head` succeeds, then `alembic check` fails at `add_table buy_board_candidates`, and 0 of the 4 tables exist. The VPS evidently has these tables (2,121 reports served).
- All other items are unchanged. HIGH-001 (`import_stale_sec_filings.py:133-141, 186-197`), HIGH-002 (`report_machine.py:1299-1307, 2723`) and HIGH-004 (`:358`) were re-checked, and `src/` changed only by adding `edgar_calendar.py`.

## Tests

- `uv sync --locked --extra dev`; `ACCOUNTANT_ENV=test uv run --frozen pytest -p no:cacheprovider` → exit 0, **427 passed / 0 failed / 0 skipped**, 1 warning (Starlette/httpx deprecation).
- `ruff check src tests` → clean. `python scripts/check_mypy_baseline.py` → "308 existing errors; no new diagnostics", exit 0.
- PG16: `alembic upgrade head` OK; `alembic check` FAIL (ACC-MED-014).
- Not run: Docker (no daemon), coverage, any live check.

## Top three next actions

1. **Operations:** resolve the storage block (ACC-CRIT-001) with a capacity or archival decision. This must not delete immutable facts or report-card history. Nothing downstream is fresh until this is done.
2. **Recovery:** confirm or establish backups for the systemd deployment (ACC-HIGH-009) before any archival or cleanup. Archival without a proven restore risks unrecoverable loss.
3. **Correctness:** HIGH-001 (index watermark) before resuming ingestion at scale, so the catch-up from 10-07 does not drop throttled index days permanently.

## Not run / unproven

- No live API, scheduler, PostgreSQL, worker, log, WAL or backup observation. Every runtime number above comes from the operator note and is dated 2026-10-21.
- Deployment of `6486343` is unrecorded. There is no throughput sample, no representative scoring sample, and no restore test.
