# Selective audit promotion - 2026-10-19

Reviewed audit commit `31d2398b0cc1b8db6e2550d2663517657c34b036`
against main `7785df78bd1151e862f5e5bb726c25880d5dd696`.
This manually authorized promotion is separate from the branch-confined daily
remediation workflow and does not authorize production deployment.

## Accepted

- Governance metadata no longer invents shares purchased or buying clusters
  from a count of Form 4 filings. Transaction direction and shares remain
  UNKNOWN until parsed. Publish actual filing count, source accessions,
  as-of date and rule version in report cards.
- Explicit as-of windows exclude future-dated governance/event filings;
  sort event evidence so the most recent matching disclosure supplies dates.
  The current-report builder passes one captured report date. This does not
  establish accepted-timestamp integrity for every part of a backtest.
- Scheduler readiness consumes its persisted cycle status; rejects missing,
  failed, future-dated and stale status. Correct the compose polling variable
  to the variable actually consumed by the scheduler.
- Preserve existing main backup safeguards: the branch's new legacy-copy
  protection is already present on main with zero/one-copy regressions.
- Mutation-route authorization and selected signal/readiness regressions.

## Held

- Broader grading, valuation, SEC ingestion/limiter, storage and migration
  changes remain outside this promotion. Migrations still require populated
  legacy-schema acceptance; fresh schema CI alone is insufficient.
- V4 fixes the previous GAAP explanation false negative, but a trailing
  conditional still creates a false positive. Offline fixture:

  > The Audit Committee determined that the financial statements should no
  > longer be relied upon if material errors are identified.

  Branch result: `big_r_restatement=True`; expected UNKNOWN/no hard veto for
  a contingent statement. Do not promote the parser and its downstream
  grading dependencies on the strength of the repaired earlier fixture alone.
- Existing heuristic limits (including auditor identity/tenure, dual-class
  inference and incomplete transaction parsing) are not proven resolved.
- No production changes, backfills, database migration or runtime readiness
  claims. Previously stored report cards are not rewritten by a code commit.

## Evidence

- Independently ran audit-branch pytest: 473 passed, one dependency warning.
- Audit CI run 39249409623 succeeded at the reviewed source SHA.
- Selected main subset: 408 tests passed with one dependency warning; Ruff
  passed for src/tests and the changed readiness script; scoped auth/config
  mypy passed; git whitespace checks passed. CI on the promoted commit is
  checked separately and is not inferred from source-branch CI.
- Review readability: 7/10. Further improvements: clause-scoped disclosure
  parsing and smaller report-building functions with explicit evidence types.
