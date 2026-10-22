# October 22 readiness hardening

## Decision

PARTIAL. These changes close unsafe publication and misleading status paths;
they do not establish that the research universe is ready for integration.
No execution authority is added. No storage limits are raised, source facts
deleted, historical cards overwritten, or held audit migrations promoted.

## Accepted changes

- Research packet V2 and ticker readiness share one fail-closed acceptance
  check: identity, source freshness, explicit research-only policy, report
  quality, aware timestamps, finite/reconciled scores, and versioned financial
  QA with all required checks. Unverified reports are diagnostics, not packets.
- Global readiness counts validated current card/report pairs only after its
  cheap prerequisites pass. Report-row counts alone cannot establish readiness.
- A dedicated research credential authorizes protected read endpoints only;
  operator authentication remains separate for mutations.
- Financial input selection requires consolidated, correctly denominated,
  comparable reported periods; quarterly and annual flows cannot be mixed.
  Weighted-average EPS shares are distinct from instant valuation shares.
  Unknown financing is not inferred by adding share counts to dollar debt.
- New calculations are explicitly UNVALIDATED pending independent financial
  and disclosure QA. Unknown disclosure gates are not clean passes, and an
  amendment alone is not evidence of accounting fraud.
- SEC discovery checkpoints persist failed days and uncommitted company work,
  overlap recent filing days, verify expected accessions after commit, use
  atomic locked state, and exclude known recurring EDGAR holidays.
- Scheduler status distinguishes storage pause from successful research;
  generation-specific scratch summaries are removed after status persistence.
  The read-only monitor checks freshness, storage, scheduler, and recovery
  evidence without fabricating alert delivery.

## Verification

Local full suite: 518 passed (one upstream TestClient deprecation warning).
Ruff: source, tests, and changed Python operations scripts passed.
Scoped auth/config type checks passed. Full-source type debt decreased from
308 to 236 existing diagnostics, with no new diagnostics; this is not a
type-clean claim. Removed baseline entries were verified resolved, not waived.
Trading Terminal consumer tests: 94 passed in its separate audit checkout.
Its calendar-date contract was cross-checked against the producer. Consumer
changes are not evidence of a deployed connection or enabled influence.

## Live baseline, before this deployment

Accountant host 129.121.138.129, commit
64863431a964b6aafc1168ef62d12c4372887e4f. API and scheduler active.
Database accountant_vps2: 14,902,639,639 bytes; latest filing October 6;
2,121 company reports. Approximately 28.87 GB filesystem space available.
The 14 GiB database cap plus the 128 MiB worker reserve still blocks growth;
free filesystem space does not override that separate database budget.

## Recovery evidence and remaining gates

The October 7 raw-facts archive was restored into an isolated local PostgreSQL
scratch database: 15,907,880 rows across 1,156 company IDs. The restore command
completed successfully. Pre-data and table data were restored, not production
foreign keys or a complete current database backup. No AAPL rows were present.
Archive SHA-256:
E6C53C53C442D3B952B6A97F7204DAD6BC74DE9FA4C842D2056A1F01BCC5D908.
This identifies the file inspected; no earlier trusted checksum was available.

The October 6 archive restore is a separate local job and was still running
when this evidence was written. Neither archive is installed on the VPS.

Still required: complete archive/company coverage reconciliation; tested
bounded hot/cold rebuild and canonical relinking; current off-host backup and
restore; capacity-safe SEC catch-up; independently reconciled representative
financial samples and disclosure evidence; fresh validated report cards; a
real authenticated consumer smoke test; and configured/verified alert delivery.
Do not bypass these gates to make a dashboard report green.
