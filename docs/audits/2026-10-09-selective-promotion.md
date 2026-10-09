# Accountant selective audit promotion - 2026-10-09

## Scope

Independently reviewed `origin/Claude-Gpt-audit` at
`4c28c3b4aa88a02f3d7cab898e2aed976cf45acd` against main at
`cedd614dc3ea96a0aa68c9f488526ec5f3866e24`.
This is a selective promotion, not a blanket merge or a deployment.
The daily remediation workflow remains confined to `Claude-Gpt-audit`;
manual promotion follows the user's separate authorization in this chat.

## Accepted

- Backup/restore runbook: mounted script paths, postgres execution identity,
  and an explicitly isolated scratch database instead of production deletion.
- Restore counts derived from the immutable dump, not a moving live database;
  counts manifest and archive-reading helper.
- Backup status, headroom failure evidence, timestamp-scoped retention and
  orphaned sidecar cleanup.
- Additional independent safeguard: no dump expiry unless the configured
  checksum-verified recovery-copy floor is met. Preserve legacy dumps when
  checksums are absent or only one verified copy exists. Checksums alone do
  not establish restoreability or off-host recovery.
- Readiness checks reject missing/stale/failed backup status, distinguish zero
  SEC staleness from missing data, and check application storage blocking.
- Scheduler persists nonzero cycle exit codes and logs failure rather than
  misleading completion while continuing to the next poll.
- Offline regression tests for the accepted operational changes.

## Deferred

- Financial ingestion, valuation and grading changes remain unpromoted.
  `DISCLOSURE_GRADING_V3` fixes the previous conditional example but suppresses
  affirmative non-reliance if an unrelated negation occurs in the sentence.
  This exact fixture returned `big_r_restatement=None` and
  `non_reliance_ambiguous=True` on the audit branch:

  > The Audit Committee determined that the financial statements should no
  > longer be relied upon because they do not comply with GAAP.

  Expected: affirmative non-reliance, not an unknown result. The current
  sentence-wide conditional/negation check needs clause-scoped handling and
  adversarial regressions. Existing main disclosure limitations are not fixed
  by this operational promotion.
- Migrations 012-014 and associated model/schema adoption changes: fresh
  schema CI is useful, but does not establish safe adoption of existing
  populated legacy tables, constraint definitions and large indexes. Require
  a populated upgrade/validation drill before promoting this chain together.
- Remaining unselected branch changes retain the prior review decision; this
  commit does not silently promote them via supporting files or documentation.
- Off-host recovery, production behavior, representative scoring samples,
  broader typing/coverage and infrastructure choices remain unverified here.

## Verification

- Independently ran the source audit branch suite: 463 passed, one dependency
  deprecation warning. Source CI run 37981306670 succeeded at the reviewed SHA.
- Selected main subset: 401 tests passed with one dependency deprecation
  warning; Ruff passed for src, tests and the changed readiness script;
  scoped mypy passed for auth/config; git diff whitespace validation passed.
  GitHub CI must also pass; source-branch results do not stand in for it.
- Shell regression tests use stubbed PostgreSQL commands. They establish
  script control flow, not actual PostgreSQL restore acceptance for this subset.
- No VPS deployment, production migration, database deletion or storage-cap
  bypass was performed during this review.
