# Accountant remediation follow-up — October 8, 2026

Result: **PARTIAL**. Source reloaded directly from the connected Notion task [Case Capital Accountant — Upgrade Backlog](https://app.notion.com/p/3f26947878308090951fcab47548750e). Its latest audit is dated October 8, 03:02 EDT and is inline; no separate dated audit artifact is referenced. The audit was fetched before inspecting remediation code. The page still describes the earlier main-branch state, not the current remediation branch. No Notion finding was closed or rewritten.

Starting checkout: existing clean `Claude-Gpt-audit`, upstream `origin/Claude-Gpt-audit`, local/remote HEAD `a1aad7b392be540db02f1cac2b42877064e3514e`. No branch was created or switched. GitHub confirms protected=false. Main before work: `131d47829e7d5669574b829e972cd0eb10da1591`. All edits are this repository only, preserving the user's separate checkout and unrelated files.

## Validation and changes this pass

The [first-pass finding matrix](2026-10-08-remediation.md) records all 29 original issues and their validations. This pass reran its regressions against the unchanged starting branch (427 passed) and re-inspected the remaining grading, valuation, ingestion, lifecycle, lint, dependency, timezone, and deployment paths. Findings are audit input, not automatic truth. Code-level fixes are not equivalent to Claude's required deployed acceptance evidence.

| Finding | Current validation | Files/fix | Regression evidence | Remaining risk |
| --- | --- | --- | --- | --- |
| ACC-HIGH-002 | CONFIRMED remaining defect: legacy unversioned quarterly report generates annual target (127.5 in isolated reproduction) | `buy_board.py`: legacy valuation null until TTM rebuild. `annual_flows.py`/`report_machine.py`: gross/COGS/net/owner-earnings margins require matching duration windows; recorded ANNUAL_PERIOD_ALIGNMENT_V1 | Legacy target regression failed before/passes after; alignment regression | Representative operating/bank/REIT golden comparisons, other ancillary ratios and deployed rebuild remain incomplete. Historical filing cards are not modified. |
| ACC-HIGH-006 | Existing shared limiter remains present; previous aggregate-rate acceptance untested | No limiter code change; added 12-client fake-HTTP transport regression with independent SecClients sharing the operational clock | Every sliding one-second interval has <=10 mocked requests; all 12 complete | Not a live SEC benchmark or cross-process stress measurement; deployed processes must share the data directory. |
| ACC-MED-001 | CONFIRMED: amendment metadata alone severity 95; hard-coded off vetoes; one-period sustained flag; missing severity leaves confidence 1.0 (reproduced) | New `grading_evidence.py`, `grading_engine.py`, `report_machine.py`: administrative Part III vs affirmative financial non-reliance; positive going-concern/non-reliance evidence, unknown text stays null; two consecutive annual Beneish observations; missing-input confidence fraction | Administrative grade unchanged with same quality; affirmative 4.02 triggers Big-R F veto; headings/negation/conditional language don't trigger; missing text unknown; single/gapped period not sustained; synthetic SQL report builds persist evidence | Conservative deterministic phrase detector, not exhaustive legal/accounting interpretation. Untested real-sector samples and deployed acceptance remain. No new runtime LLM. |
| ACC-MED-003 | CONFIRMED remaining ignored payload errors at legacy `_process_company` caller | `report_machine.py`: count payload errors, raise and rollback; do not continue as success | Mocked legacy caller raises provenance/payload error and rollback occurs | Existing immutable source lineage not rewritten; other legacy sequential lane failure handling and lineage-wide historical recovery remain incomplete. |
| ACC-LOW-005 | CONFIRMED: expanded lint initially has 12 pre-existing findings in scripts/Alembic; CI scope narrower | CI now Ruff src/tests/scripts/alembic; mechanical import/unused/context-manager fixes in scripts and migration environment; new grading Mypy gate | Full expanded Ruff passes; old 2-file type gate and new 2-file grading gate pass | Not a full-package mypy baseline/ratchet or repository-wide formatting solution. |
| ACC-LOW-008 | CONFIRMED live npm audit: source-map-js 1.2.1, GHSA-68fv-2mgg-jv7q (high), fixed version available | `frontend/package-lock.json`: only source-map-js 1.2.1 -> 1.2.2 | npm ci, audit (0 reported vulnerabilities), production build, 1 frontend auth test pass | Base-image digest pinning remains incomplete; zero current npm reports is not a guarantee of no vulnerabilities. |
| ACC-LOW-009 | CONFIRMED startup/shutdown event registration; strict app warning check also exposed pre-existing utcnow call | `api/app.py`: async lifespan invokes existing startup/shutdown, cleanup on startup failure; now(UTC) with old timezone-less response format preserved | No deprecated route event registrations; lifecycle cleanup regression; strict app-deprecation focused run | Existing third-party Starlette/httpx warning remains. No service restarted. |

### Versioning/provenance

New grading rule: `REPORT_CARD_GRADING_V2_FORENSIC_COMPLETENESS`. Disclosure evidence: `DISCLOSURE_GRADING_V2` with accession, source URL, normalized-text SHA256, and matched flags. Sustained evidence: `SUSTAINED_BENEISH_TWO_ANNUAL_V1`, threshold -1.78, required two consecutive annual scores and input fact IDs. `FORENSIC_COMPLETENESS_V1` multiplies confidence by known severity inputs / 4; missing evidence is not invented as a veto. Unknown Beneish/Altman severity stays null, and dispersion excludes missing observations. New cards record these inputs/version identifiers; old immutable cards and source facts are untouched.

## All findings not fully closed

| IDs | Current disposition / exact outstanding reason |
| --- | --- |
| ACC-HIGH-001, ACC-HIGH-005, ACC-MED-002 | Prior code fixes and offline regressions still pass; complete repeated-cycle/import acceptance and deployed freshness/throughput not observed. |
| ACC-HIGH-002 | Additional valuation/period fixes above; real-sector golden samples and ancillary ratios/rebuild acceptance still incomplete. |
| ACC-HIGH-003 | Shared per-job storage gate regressions still pass; reserves are estimates, not hard quotas. Oversized jobs, direct ingestion and live cross-process PostgreSQL acceptance remain. |
| ACC-HIGH-004 | Prior active-worker error propagation/retention tests pass; not every legacy sequential lane error path/staleness monitor covered. |
| ACC-HIGH-006 | Aggregate mocked 12-client acceptance now passes; cross-process/deployed clock sharing/rate not observed. |
| ACC-HIGH-007 | Prior branch CI 37749983823 passed compose/image build; this pass requires its own branch CI. Main is intentionally never altered. |
| ACC-MED-001 | Code acceptance above passes; conservative text parser and immutable old-card behavior require real-data/deployed review. |
| ACC-MED-003 | Legacy payload handling improved; historical lineage/backfill is not safely implemented without immutable-data design. |
| ACC-MED-004 | SUSPECTED/UNVERIFIED: no authoritative EDGAR Accepted-time fixture comparison. No speculative timezone rewrite. |
| ACC-MED-005 | Prior CI dump/checksum/scratch restore passed; off-host destination/credentials and scheduled deployed recovery evidence unavailable. No production backup/restore attempted. |
| ACC-MED-006, ACC-MED-007 | Prior PostgreSQL16/ownership code mitigations exist, but actual deployed tool version and fresh compose-volume dump acceptance unverified. |
| ACC-MED-008, ACC-MED-009, ACC-LOW-001, ACC-LOW-002, ACC-LOW-003, ACC-LOW-006, ACC-LOW-007 | Existing code fixes/regressions still pass. No deployed security/browser/liveness/scheduler acceptance claims. |
| ACC-MED-010 | Loopback/auth fixes pass; TLS proxy and actual reachable-port checks need separate deployment authority. |
| ACC-MED-011 | Production create_all disabled and migration smoke exists; schema-drift Alembic check/baseline still missing. No speculative schema migration. |
| ACC-MED-012 | Locked dependency/image configuration and previous CI build pass; exhaustive installed-image vs lock comparison not performed. |
| ACC-MED-013 | Additional full report-build/rate/lifecycle regressions added; >=60% targeted coverage and restart-recovery acceptance not established. |
| ACC-LOW-004 | Not implemented: systemd vs compose deployment choice and filesystem write paths require operator input; no systemd service changed/restarted. |
| ACC-LOW-005 | Full expanded lint addressed, but full-package type baseline and whole-tree format ratchet remain. |
| ACC-LOW-008 | npm advisory fixed; digest-pinning portion remains. |
| ACC-LOW-009 | Lifespan and strict app-deprecation acceptance addressed; third-party warning is separate pre-existing debt. |

## Exact local verification

Working directory is the existing isolated checkout except npm/node commands in `frontend/`. All database/HTTP fixtures isolated, mocked, or synthetic. No external SEC/broker request or production database connection was used for these tests.

| Command | Exit/result |
| --- | --- |
| `uv run pytest` baseline | 0; 427 passed, 0 failed, 0 skipped, 1 pre-existing warning; 4.90s |
| `uv run pytest tests/test_remediation_followup.py` before fixes | 1; 3 failed (confidence, legacy target, deprecated registration) |
| `uv run ruff check src tests scripts alembic` before fixes | 12 pre-existing findings; individual Ruff exit was not separately captured in the combined read-only inspection command |
| `uv run pytest` final full run | 0; 443 passed, 0 failed, 0 skipped, 1 pre-existing Starlette/httpx warning; 9.05s |
| `uv run pytest tests/test_remediation_followup.py tests/test_grading_engine.py tests/test_audit_regressions.py tests/test_annual_flows.py tests/test_companyfacts_audit.py` | 0; 50 passed, 0 failed, 0 skipped; 5.21s (before last legacy regression added) |
| `uv run pytest tests/test_remediation_followup.py tests/test_api.py -W 'error::DeprecationWarning:accountant.api.app'` | 0; 33 passed, 0 failed, 0 skipped, 1 unrelated third-party warning; 7.64s |
| `uv run ruff check src tests scripts alembic` final | 0; all checked files pass |
| `uv run mypy src/accountant/api/auth.py src/accountant/config.py --ignore-missing-imports` | 0; 2 source files |
| `uv run mypy src/accountant/research/grading_engine.py src/accountant/research/grading_evidence.py --follow-imports=silent --ignore-missing-imports` | 0; 2 source files (initial new-code union inference issue fixed with typed observation) |
| `npm audit --json` before dependency fix | 1; 1 high source-map-js advisory |
| `npm audit fix --package-lock-only` | 0; only compatible transitive patch changed, no force upgrade |
| `npm ci` / `npm audit --json` after fix | both 0; audit reports 0 vulnerabilities |
| `npm run build` | 0; Vite 7.3.6, 1683 modules; successful build |
| `node --test src/lib/api.test.mjs` | 0; 1 passed, 0 failed, 0 skipped |
| `git diff --check` | 0; Windows line-ending warnings only |

A new mocked legacy test initially failed because its Mock did not implement context-manager methods; changed to MagicMock, then passed. A new nested-with lint issue was corrected. Strict app-deprecation testing initially reproduced the pre-existing utcnow warning, then passed after compatible replacement. These intermediate failures are not production failures.

Final commit hashes, explicit destination push, protected-ref comparison and current CI evidence are appended in the chat handoff report after push. No pull request has been created. No main/master/develop/production commit, push or merge is permitted; production remains unverified and execution prohibited.
