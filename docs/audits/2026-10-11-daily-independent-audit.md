# Case Capital Accountant — daily independent audit 2026-10-11

## Evidence header

- **Audit time:** 2026-10-11 02:51–03:30 EDT (America/New_York, UTC−4). Sunday. Daily audit run 4.
- **Calendar:** EDGAR does not disseminate on weekends or on Mon 2026-10-12 (Columbus Day, a federal holiday). The next EDGAR business day is Tue 2026-10-13, so no new filings should appear before then.
- **Local repository:** `main` @ `7785df7` ("Select safe Oct 9 audit operational fixes with retention safeguard"). Clean worktree. The audit branch `claude/charming-hopper-hv9su2` equals `main` before this artifact.
- **Other branches:** `origin/Claude-Gpt-audit` @ `4c28c3b`, unchanged since 2026-10-09. The only commit anywhere since the previous audit is `b0988f2`, which is the 2026-10-10 audit artifact.
- **Deployed commit:** UNVERIFIED. No SSH, monitoring or API access.
- **Previous audit:** 2026-10-10 02:51–03:40 EDT (`docs/audits/2026-10-10-daily-independent-audit.md` on `claude/charming-hopper-63k5j2`, plus the Notion task).
- **Tools available:** git, GitHub Actions (read), an isolated Python 3.12 venv (`uv sync --locked`), ruff and mypy. No Docker daemon, no production access, no PostgreSQL.
- **Scope:** REPOSITORY-LEVEL ONLY.

## Verdict

- **Operations:** UNVERIFIED. No live API, scheduler, PostgreSQL, worker, log, disk or backup observation was possible.
- **Code level:** DEGRADED, unchanged. HIGH-001..006 are still open on `main`.
- **Research-only readiness:** not established.
- **Execution:** prohibited by design. No order paths were found.

## Dashboard

| Item | 2026-10-10 | 2026-10-11 |
|---|---|---|
| Report coverage / throughput / pending / blocked | UNVERIFIED | UNVERIFIED |
| Filing freshness / stage lag | UNVERIFIED | UNVERIFIED (no EDGAR dissemination expected until 10-13) |
| DB / disk / WAL / headroom | UNVERIFIED | UNVERIFIED |
| Errors | UNVERIFIED | UNVERIFIED |
| Deployed / local commit | UNVERIFIED / 7785df7 | UNVERIFIED / 7785df7 |
| Backup / restore evidence | none live | none live |
| CI on `main` HEAD | FAILURE (run 37992934630, infra) | **FAILURE, still not re-run** (same run, attempt 2) |

## Tests (main @ 7785df7; isolated venv; SQLite; `ACCOUNTANT_ENV=test`)

- `python -m pytest`: exit 0, **401 passed**, 0 failed, 0 skipped, 1 warning (Starlette `httpx` testclient deprecation).
- `ruff check src tests`: clean.
- `ruff check scripts alembic`: 14 errors (13 fixable). Not in CI.
- `mypy src/accountant/api/auth.py src/accountant/config.py` (the CI scope, 2 files): pass. This says nothing about the rest of the tree.
- Coverage was not re-measured. Source is unchanged since the 60% / `report_machine.py` 17% measurement on 2026-10-10.

## New or regressed findings

None verified. No `src/`, `scripts/`, `deploy/` or compose file changed since the previous audit, so every prior file:line reference still holds.

**Calendar note (added to ACC-LOW-003, not a new ID):** `scripts/vps_readiness_check.py:17,53` enforces `sec_fresh_enough` as `days_since_latest_filing <= 3` calendar days. The latest possible EDGAR filing date is Fri 10-09, and the next one is Tue 10-13. A readiness run on Tue 10-13 before that day's filings arrive will report 4 days and FAIL, although nothing is wrong. Use business days with the federal holiday calendar. Note that the input is also a global max, so it cannot detect per-company staleness (ACC-HIGH-001).

## Prior findings

- **No status changes.** The 35 items keep their 2026-10-10 statuses.
- **ACC-MED-016:** still Open. Run 37992934630 has not been re-run, and no new `main` push exists. `main` HEAD has now been unvalidated by CI for about 30 hours.
- **RESOLVED items** (HIGH-007, HIGH-008, MED-009, MED-012, LOW-001, LOW-009, LOW-010, LOW-011) are resolved only at repository level. There is no deployed-commit confirmation for any of them.

## Three highest-impact next actions

1. **CI on `main` (ACC-MED-016).** Re-run 37992934630 or add authenticated or mirrored image pulls. Every promoted fix since `cedd614` is unvalidated, so this gates trust in the others.
2. **ACC-HIGH-004, then ACC-HIGH-003.** Make lane failures visible and enforce the storage gate per job. These are the two items that hide stalled work and allow disk exhaustion. Both are still open on `main`.
3. **Operator read-only VPS check before Tue 10-13.** Get the deployed SHA, `/api/reports/status` sampled twice at least 60 s apart, `/backups/status.json`, and `df` plus database size. Until this is done, every Pass 1, 2 and 4 conclusion stays UNVERIFIED.

Correctness fixes (HIGH-001/002/005/006) still outrank cosmetic work. They exist only on the unpromoted branch, and the branch's MED-001 classifier still has the reproduced non-reliance negation defect.

## Checks not run / unproven

- Every live check in Passes 1, 2 and 4. The representative sector sample for scoring in Pass 3 was not run because there is no production data.
- Docker compose validation, image build and runtime smoke test: no daemon locally, and CI on HEAD failed before running them.
- Real PostgreSQL `alembic upgrade head && alembic check`. Not re-run today; it failed on 2026-10-09 with an unchanged schema.
- Restore drill. There is no recorded tested recovery timestamp.
