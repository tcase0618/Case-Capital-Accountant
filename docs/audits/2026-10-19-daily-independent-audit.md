# Accountant Daily Independent Audit — 2026-10-19 (run 12, repository-only)

- **Audit time:** 2026-10-19 02:53–03:30 EDT (America/New_York, UTC−4), Monday. Regular EDGAR business day; the last daily index before today was Fri 10-16.
- **Local repository:** branch `claude/charming-hopper-wqukqm` = `main` @ `7785df7` (2026-10-09 17:21 EDT). Clean worktree. No commits on `main` since 10-09; `origin/Claude-Gpt-audit` @ `4c28c3b` unchanged. Only new remote commits are prior audit artifacts.
- **Deployed commit:** UNVERIFIED — no SSH, monitoring, API or production credentials in this session.
- **Previous audit:** 2026-10-18 02:50–03:20 EDT (run 11).
- **Tools/access:** git, uv + Python 3.11 venv, GitHub MCP (Actions read), Notion MCP. No production access, no Docker daemon.

## Verdict
- **Operations:** UNVERIFIED (no production access). **Code level:** DEGRADED, now with a **red local test suite on `main`** (new ACC-MED-017).
- **Research-only readiness:** not established. **Execution:** prohibited by design; no order paths found.

## Dashboard
| Item | Value |
|---|---|
| Report coverage, throughput, pending/blocked work, filing freshness, stage lag | UNVERIFIED (no production access) |
| DB / disk / WAL size and headroom | UNVERIFIED |
| Errors / restarts | UNVERIFIED |
| Backup / restore evidence | UNVERIFIED (repository-level only) |
| Local / deployed commit | `7785df7` / UNVERIFIED |
| CI on `main` HEAD | run 37992934630 FAILURE (attempt 2), not re-run — 10 days without green CI. A re-run would now also fail the test job (ACC-MED-017). |

## New findings

### ACC-MED-017 — `main` test suite now fails: wall-clock-dependent governance test expired on 2026-10-19
- **Severity:** Medium · **Status:** CONFIRMED (reproduced) · Current status: Open
- **Evidence:** `ACCOUNTANT_ENV=test uv run --frozen --offline pytest -q` on `7785df7` → **400 passed, 1 failed** (was 401/0 through 10-18 on identical code). Failing: `tests/test_filing_signal_engine.py::test_build_governance_signals_detects_form4_cluster_and_dual_class` (`:176`, `insider_buy_cluster_flag` False). The fixture Form 4 dated `2026-07-20` fell outside `date.today() - timedelta(days=90)` (`src/accountant/research/filing_signal_engine.py:254`) today.
- **Consequence:** `main` cannot get green CI even after the Docker Hub issue (ACC-MED-016) clears; every fix promotion is blocked or tempted to skip tests. Any other wall-clock test will expire the same way.
- **Repair:** pass an explicit `as_of` date into `build_governance_signals`/`build_event_red_flags` (from the report's as-of/accepted date) and use it in tests; do not loosen the assertion or skip the test.
- **Acceptance / test:** the test passes with a frozen `as_of`, and a parametrized check with `as_of` = 2026-10-19 and 2027-01-01 gives deterministic results. Full suite green locally and in CI on `main`.

### ACC-MED-018 — Governance signals are not point-in-time and mislabel Form 4 counts as insider buying
- **Severity:** Medium · **Status:** CONFIRMED (source) · Current status: Open
- **Evidence:** `filing_signal_engine.py:254-257`: `form4s` = every Form 4 filed in the last 90 days **of wall-clock time** (no transaction code, buy/sell or share parsing). `insider_buy_cluster_flag = len(form4s) >= 2`; `insider_net_shares_bought_90d = float(len(form4s))` — a filing count, not shares. `build_event_red_flags` uses the same `date.today()` pattern (`:193`, `:229`). Values are written to the report at `report_machine.py:1821-1822` (`governance_ownership`). No scoring consumer was found (display/packet only).
- **Consequence:** insider selling clusters are shown as "insider buy cluster", and "net shares bought" is a count of filings. Re-running a historical report changes these fields, so report cards are not reproducible as of their date.
- **Repair:** parse Form 4 transaction codes (P/S) and share amounts, or rename the fields to `form4_filing_count_90d` and mark unknown direction as unknown. Compute windows from the report as-of date.
- **Acceptance / test:** fixture with two S-code Form 4s → `insider_buy_cluster_flag` False/unknown; P-code fixture → shares summed. Same inputs and `as_of` give identical output on any wall-clock date.

## Prior findings
No other status changes. Totals now **37 items** (Critical 0, High 8, Medium 18, Low 11) · CONFIRMED 26, SUSPECTED 3, UNVERIFIED 0, RESOLVED 8 (RESOLVED is repository-level only).
- Re-checked: ACC-HIGH-001 evidence at `scripts/import_stale_sec_filings.py:133-141` unchanged.
- ACC-MED-016 evidence refreshed: still no `main` run after 37992934630; see ACC-MED-017 for the additional test failure.
- Full text: Notion task "Case Capital Accountant — Upgrade Backlog".

## Tests (isolated, offline; `main` @ 7785df7)
| Command | Result |
|---|---|
| `uv sync --locked --extra dev` (Python 3.11 venv) | exit 0 |
| `ACCOUNTANT_ENV=test uv run --frozen --offline pytest -q -p no:cacheprovider` | **exit 1 — 400 passed, 1 failed**, 0 skipped (new date-expired failure, ACC-MED-017) |
| `uv run --frozen --offline ruff check src tests` | clean |
| `mypy src/accountant/api/auth.py src/accountant/config.py --ignore-missing-imports` (CI scope: 2 files only) | pass — not a whole-package type check (ACC-LOW-005) |

Not run: Docker/compose validation (no daemon), whole-package mypy, coverage, PostgreSQL migration re-check (ACC-MED-014, code unchanged since the 10-17 reproduction).

## Top three next actions
1. **Urgent operations:** an operator read-only check of the deployed SHA, discovery watermark versus newest `accepted_at` after today's first post-weekend index, and DB/disk headroom. Production has been unverified for 11 days.
2. **Correctness:** ACC-HIGH-001 (watermark skips dates) and ACC-HIGH-002 (valuation unit mixing), then ACC-MED-018 (mislabelled insider signal).
3. **CI trust:** fix ACC-MED-017 with an explicit as-of date, re-run `main` CI (ACC-MED-016), and add the ACC-MED-014 migration.

## Checks not run / unproven claims
- Pass 1 (live operations), Pass 2 freshness counts, Pass 3 live samples and Pass 4 storage measurements: UNVERIFIED (no access).
- No claim of production readiness, autonomy or crash recovery is made.
