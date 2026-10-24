# Accountant Daily Independent Audit — 2026-10-24

- Audit time: 2026-10-24 02:51–03:40 EDT (America/New_York, UTC−4), Saturday. Daily routine, run 17.
- EDGAR calendar: weekend. No SEC daily index is expected today, so ACC-MED-020 cannot recur today.
- Repository: `main` @ `deec292` (unchanged since the 2026-10-23 audit). Working branch `claude/charming-hopper-2ibjqb` = `deec292` before this artifact. The worktree was clean.
- Other branches: `Claude-Gpt-audit` @ `da3dbd0` (2026-10-21) has not changed; it is 14 ahead and 13 behind `main`.
- Deployed commit: **UNVERIFIED**. There was no SSH, database or monitoring access. No new operator record since `docs/audits/2026-10-22-readiness-hardening.md`.
- Scope: **REPOSITORY-LEVEL ONLY**. No live observation.
- Tools: git, uv 3.11 venv (`uv sync --locked --extra dev`), local scratch PostgreSQL 16 (isolated, non-production), GitHub Actions API (read).

## 1. Operational verdict

**DEGRADED / UNVERIFIED (unchanged).**

- Research-only readiness: **not ready**. Cards remain deliberately `UNVALIDATED`, and packet V2 returns `accepted=false` (fail-closed).
- Execution is prohibited by design, and no order paths were found.
- No status was changed today. Nothing in the repository moved, and no new runtime evidence exists.

## 2. Dashboard

| Metric | Value | Source / status |
|---|---|---|
| Reports cached | 2,126 of a 4,473 universe | operator note 2026-10-22; current value UNVERIFIED |
| Throughput (companies/min) | not computable | no observation window |
| Pending | 2,193 companies / 11,063 accessions | operator note 2026-10-22; UNVERIFIED |
| Latest filing | 2026-10-22 (from an 8-company bounded test only) | universe freshness NOT established |
| DB size | ~14.6 GB vs 14 GiB cap + 128 MiB reserve | operator note; UNVERIFIED |
| Disk free | ~28.87 GB | operator note; UNVERIFIED |
| WAL / logs | UNVERIFIED | — |
| Backup | one off-host 1.64 GB snapshot, checksum matched | restore completion not recorded |
| CI on `main` @ `deec292` | run 39852371657: success | GitHub Actions |

## 3. New or regressed findings

None verified. The source code is byte-identical to the 2026-10-23 audit, so every file:line reference in the register is unchanged.

## 4. Prior findings (re-checked today)

- **ACC-MED-014: re-reproduced.** On a fresh PG16 database (UTF8), `alembic upgrade head` exits 0, but `alembic check` exits non-zero with "New upgrade operations detected". It wants to add four tables (`buy_board_candidates`, `buy_board_snapshots`, `company_reports`, `report_cards`) plus the index `ix_statement_snapshots_company_id`.
- **Unchanged and not independently re-observed at runtime:** all other items, carried forward. They are CRIT-001 (partial, operator-recorded), HIGH-002/003/004/005/006/009, MED-001…MED-016 (open or partial ones), MED-020, and LOW-002…LOW-013 (open or partial ones).
- **RESOLVED (repository level) remains 13:** HIGH-001, HIGH-007, HIGH-008, MED-009, MED-012, MED-017, MED-018, MED-019, LOW-001, LOW-006, LOW-009, LOW-010, LOW-011.

Totals: 43 items (Critical 1, High 9, Medium 20, Low 13) · CONFIRMED 26, SUSPECTED 4, UNVERIFIED 0, RESOLVED 13.

## 5. Tests (main @ deec292, Python 3.11.17, `ACCOUNTANT_ENV=test`, offline)

| Command | Result |
|---|---|
| `uv run --frozen pytest -p no:cacheprovider -q` | exit 0; 526 passed / 0 failed / 0 skipped; 1 warning (Starlette TestClient/httpx deprecation) |
| `uv run --frozen ruff check src tests` | All checks passed |
| `uv run --frozen python scripts/check_mypy_baseline.py` | 236 existing errors, no new diagnostics (full src) |
| `alembic upgrade head` (scratch PG16) | exit 0 |
| `alembic check` (scratch PG16) | FAILS (MED-014) |

Not run: Docker build/compose validation (no Docker), coverage tooling, live endpoints, restore tests, worker sampling.

## 6. Three highest-impact next actions

1. **Operations (CRIT-001):** make a capacity decision, then do capacity-safe catch-up of the 2,193 pending companies. Measure report coverage at two timestamps at least 60 seconds apart. This outranks everything else: until it is done, research is stale.
2. **Recovery (HIGH-009 / MED-005):** add a scheduled, systemd-native backup with an off-host copy, and record one completed isolated restore with row counts. A checksum alone is not recovery evidence.
3. **Correctness (HIGH-002 / MED-014):** use TTM and share-basis valuation inputs, and add a migration for the four ORM tables with `alembic check` in CI. Both must be done before any card leaves `UNVALIDATED`.

## 7. Not run / blocked / unproven

- All of Pass 1 (live API, scheduler, PostgreSQL, worker, logs) is BLOCKED: there is no production access.
- Pass 4 measurements (filesystem, database, WAL, backup footprint) are BLOCKED. The growth rate and time to the threshold cannot be computed.
- Pass 3 sample recomputation was not repeated because the code is unchanged. The prior conclusions stand.
- The deployed SHA, firewall/TLS, effective runtime users and the CI Docker smoke test are not re-verified today.
- No claim of production readiness or autonomy is made.
