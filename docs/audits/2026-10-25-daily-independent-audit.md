# Accountant Daily Independent Audit — 2026-10-25

- Audit time: 2026-10-25 02:51–03:45 EDT (America/New_York, UTC−4), Sunday. Daily routine, run 18.
- EDGAR calendar: weekend. No SEC daily index is expected today, so ACC-MED-020 cannot recur today. US DST ends Sun 2026-11-01 (EDT→EST); next week's audit should confirm the scheduler polling window shifts correctly.
- Repository: `main` @ `deec292` (unchanged since the 2026-10-22 commit; third consecutive audit on the same SHA). Working branch `claude/charming-hopper-w71q2b` = `deec292` before this artifact. Worktree clean.
- Other branches: `Claude-Gpt-audit` @ `da3dbd0` unchanged since 2026-10-21 (14 ahead / 13 behind `main`).
- Deployed commit: **UNVERIFIED**. No SSH, database or monitoring access. No operator record newer than `docs/audits/2026-10-22-readiness-hardening.md`.
- Scope: **REPOSITORY-LEVEL ONLY**. No live observation.
- Tools: git, uv / Python 3.11.17 venv (`uv sync --locked --extra dev`), local scratch PostgreSQL 16 (isolated, non-production, destroyed after use), GitHub Actions API (read-only).

## 1. Operational verdict

**DEGRADED / UNVERIFIED (unchanged).**

- Research-only readiness: **not ready**. Cards remain deliberately `UNVALIDATED`; packet V2 returns `accepted=false` (fail-closed, correct).
- Execution is prohibited by design; no order paths found.
- No status changed today. Nothing in the repository moved and no new runtime evidence exists.

## 2. Dashboard

| Metric | Value | Source / status |
|---|---|---|
| Reports cached | 2,126 of a 4,473 universe | operator note 2026-10-22; current value UNVERIFIED |
| Throughput (companies/min) | not computable | no observation window |
| Pending | 2,193 companies / 11,063 accessions | operator note 2026-10-22; UNVERIFIED |
| Latest filing | 2026-10-22 (8-company bounded test only) | universe freshness NOT established |
| DB size | ~14.6 GB vs 14 GiB cap + 128 MiB reserve | operator note; UNVERIFIED |
| Disk free | ~28.87 GB | operator note; UNVERIFIED |
| WAL / logs | UNVERIFIED | — |
| Backup | one off-host 1.64 GB snapshot, checksum matched | restore completion not recorded |
| CI on `main` @ `deec292` | run 39852371657: success | GitHub Actions (re-read 2026-10-25) |

Runtime data is now 3 days old (operator note 2026-10-22). Nothing in this table can be refreshed without production read access.

## 3. New or regressed findings

None verified. Source is byte-identical to the 2026-10-24 audit, so every file:line reference in the register is unchanged.

## 4. Prior findings (re-checked today)

- **ACC-MED-014: re-reproduced.** Fresh PG16 (UTF8): `alembic upgrade head` exits 0 (001→011); `alembic check` fails with "New upgrade operations detected", wanting `add_table buy_board_candidates` (plus `buy_board_snapshots`, `company_reports`, `report_cards`) and index `ix_statement_snapshots_company_id`.
- **Unchanged, not independently re-observed at runtime:** all other items carried forward — CRIT-001 (partial, operator-recorded), HIGH-002/003/004/005/006/009, MED-001…MED-016 (open/partial), MED-020, LOW-002…LOW-013 (open/partial).
- **RESOLVED (repository level) remains 13:** HIGH-001, HIGH-007, HIGH-008, MED-009, MED-012, MED-017, MED-018, MED-019, LOW-001, LOW-006, LOW-009, LOW-010, LOW-011.

Totals: 43 items (Critical 1, High 9, Medium 20, Low 13) · CONFIRMED 26, SUSPECTED 4, UNVERIFIED 0, RESOLVED 13. Full per-item evidence, repair and acceptance criteria are kept in the Notion task "Case Capital Accountant — Upgrade Backlog".

## 5. Tests (main @ deec292, Python 3.11.17, `ACCOUNTANT_ENV=test`, offline)

| Command | Result |
|---|---|
| `uv run --frozen pytest -p no:cacheprovider -o addopts= -q` | exit 0; 526 passed / 0 failed / 0 skipped; 1 warning (Starlette TestClient/httpx deprecation) |
| `uv run --frozen ruff check src tests` | All checks passed |
| `uv run --frozen python scripts/check_mypy_baseline.py` | 236 existing errors (full `src`, 125 files), no new diagnostics — the tree is NOT type-clean |
| `alembic upgrade head` (scratch PG16) | exit 0 |
| `alembic check` (scratch PG16) | FAILS (MED-014) |

Note: the repository's `addopts = "-q"` combined with `-q` on the command line suppresses pytest's summary line; `-o addopts=` was used to obtain the counts.

Not run: Docker build/compose validation (no Docker), coverage tooling, live endpoints, restore tests, worker sampling.

## 6. Three highest-impact next actions

1. **Operations (CRIT-001):** capacity decision, then capacity-safe catch-up of the 2,193 pending companies, with report coverage sampled twice ≥60 s apart. Until done, every research number is stale.
2. **Recovery (HIGH-009 / MED-005):** scheduled systemd-native backup with off-host copy, and one completed isolated restore with row counts. A checksum is not recovery evidence.
3. **Correctness (HIGH-002 / MED-014):** TTM and share-basis valuation inputs; a migration for the four ORM tables with `alembic check` in CI. Both before any card leaves `UNVALIDATED`.

## 7. Not run / blocked / unproven

- Pass 1 (live API, scheduler, PostgreSQL, worker, logs): BLOCKED — no production access.
- Pass 4 measurements (filesystem, database, WAL, backup footprint): BLOCKED; growth rate and time-to-threshold cannot be computed.
- Pass 3 sample recomputation not repeated (code unchanged); prior conclusions stand.
- Deployed SHA, firewall/TLS, effective runtime users and CI Docker smoke not re-verified today.
- No production-readiness or autonomy claim is made.
