# Accountant Daily Independent Audit — 2026-11-25 (run 47)

- Audit time: 2026-11-25 01:50–02:25 EST (America/New_York, UTC−5), Wednesday. Previous audit: 2026-11-24 (run 46).
- EDGAR: today's daily index not yet published at audit time. Thanksgiving 2026-11-26 (EDGAR closed) tomorrow.
- Repository: `main` @ `6b7d6f1` (unchanged since 2026-11-09; `git ls-remote`). `Claude-Gpt-audit` @ `5c055cb` unchanged. Audit branch: `claude/charming-hopper-mbnu7o`. Worktree clean before this file.
- Deployed commit: UNVERIFIED.
- Scope: **REPOSITORY-ONLY**. No Accountant host address, SSH, database, logs or token were available. Nothing was mutated.
- Tools: git, uv with `uv.lock`, Python 3.11, GitHub Actions API (read), Notion.

## 1. Operational verdict

**DEGRADED (carried forward; live UNVERIFIED today).** Research-only readiness: **not ready**. Execution: prohibited by design (no order placement, no runtime LLM).

## 2. Dashboard

| Item | Value | Evidence status |
|---|---|---|
| Report coverage | last observed 2,134 / 4,473 (2026-11-19 live) | UNVERIFIED today |
| Throughput | last observed net 0 over 78 s (11-19) | UNVERIFIED today |
| Storage gate | last observed `database_cap_reached` (11-19) | UNVERIFIED today |
| Presumed halt | day 34; 22 EDGAR business days missed (10-23 → 11-24, excl. 11-11) | inferred; no code change touches the cap |
| Default discovery floor today | 2026-10-27 (`src/accountant/sec/discovery_state.py:16` `HISTORY_DAYS = 30`; `:109` floor = end − 29 d) | CONFIRMED from source |
| Window loss | 10-23 and **10-26 now outside** the default window; 10-27 drops on the 11-26 run | CONFIRMED from source |
| DB/disk/WAL size | not measured | UNVERIFIED |
| Backup/restore evidence | none on real topology | UNVERIFIED (HIGH-009) |
| CI | latest run #99 (audit-doc branch, success); no new `main` runs | CONFIRMED |

## 3. New or regressed findings

None. No code changed on `main`.

## 4. Prior findings

- CRIT-001: Open, evidence updated (presumed day 34; 10-26 left the default window today as predicted). Catch-up still needs an explicit start of 2026-10-23, unless failed checkpoint entries exist for those days (`discovery_state.py:116-120` retries only recorded, not-ok days; UNVERIFIED).
- All other 47 items unchanged (no code change). Not re-observed live: CRIT-001, MED-010, MED-021, MED-022, LOW-014, LOW-015.
- Totals: 48 items (Critical 1, High 9, Medium 22, Low 16). CONFIRMED 27, SUSPECTED 4, UNVERIFIED 0, RESOLVED 17.

## 5. Tests (isolated, offline)

| Command | Result |
|---|---|
| `uv sync --locked --extra dev --python 3.11` (scratch venv) | exit 0 |
| `env -i ACCOUNTANT_ENV=test python -m pytest -q --junitxml` | exit 0; 601 tests, 0 failures, 0 errors, 0 skipped; 1 warning (starlette TestClient deprecation) |
| `ruff check src tests` (CI scope) | All checks passed |
| `ruff check .` (whole repo) | 12 errors (alembic/, scripts/) — LOW-005, unchanged |
| `python scripts/check_mypy_baseline.py` | exit 0; 236 existing errors, none new |

Not run: Docker build/compose validation, Alembic upgrade on PostgreSQL 16, coverage tooling, backup/restore drill, any live check.

## 6. Three highest-impact next actions

1. (Urgent ops) Make the storage capacity decision and run a capacity-safe catch-up with explicit start 2026-10-23 (CRIT-001, HIGH-003). Another default-window day (10-27) is lost on each further run.
2. (Recovery) Add backup + isolated restore drill for the real systemd topology (HIGH-009, HIGH-008).
3. (Correctness) Fix the valuation basis (quarterly vs annual flows, share counts) before catch-up repopulates reports (HIGH-002).

## 7. Not checked / unproven

All live checks (API, scheduler, workers, PostgreSQL, logs, disk, WAL, backups), deployed commit, scoring recomputation against live rows, Docker. Access needed: Accountant host address or a read-only monitoring path.
