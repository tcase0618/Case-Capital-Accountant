# Selective audit promotion - October 21, 2026

Reviewed audit HEAD `da3dbd00736b5d21bbe52d38a13214b4b0041fdf`
against main `e234b2613a8c79e2780f2f9552b56ecc0f3ded9d`.
User authorized selective main promotion and Accountant VPS deployment.

## Accepted

- Versioned EDGAR federal-holiday business-day calendar and Eastern-date
  readiness check; reject malformed, missing, future and unsupported dates.
  Verified the 2026 fixture against the SEC EDGAR calendar:
  https://www.sec.gov/submit-filings/filer-support-resources/edgar-calendar
- Full-source mypy diagnostic ratchet, including duplicate/new/resolved
  diagnostic handling. Generated the initial baseline from this selected
  main tree, not the divergent audit tree: 308 existing errors across 173
  fingerprints. These are acknowledged debt, not fixed errors. CI must not
  automatically regenerate or enlarge this baseline. Existing scoped-clean
  type gates remain in place.

## Held / Not Claimed

- Worker-recovery tests depend on unpromoted storage, discovery and retry
  implementation. They pass on the audit tree but cannot establish those
  features on selected main; not copied into this promotion.
- Prior grading/valuation/ingestion/storage changes and migrations 012-014
  remain deferred. The V4 trailing-conditional restatement counterexample
  remains unchanged; populated legacy database migration acceptance is absent.
- No raw-fact deletion, historical-card rewrite, schema migration, storage-cap
  override, runtime LLM or order execution is authorized by this promotion.
- The calendar checks global latest filing freshness, not discovery coverage.
  It models standard federal holidays, not exceptional SEC closures.

## Independent Verification

- Audit tree: 499 tests passed, one dependency deprecation warning.
- Selected main tree: 426 tests passed, one dependency warning; Ruff passed
  for src/tests and both changed scripts; calendar/readiness scoped mypy
  passed; full-source ratchet passed at 308 existing errors; whitespace checks
  passed. CI must pass at the exact promoted SHA before VPS code replacement.
- VPS preflight: existing code `cedd614`; clean tracked tree; API, scheduler,
  PostgreSQL and nginx active; root volume 48G total, 21G used, 27G available.
- API preflight showed `storage_blocked=true`, `database_cap_reached`, and
  source integrity FAILED: latest filing October 6, 2026; 4,473 companies,
  2,121 reports, 2,092 report cards. Runtime progress counters were zero after
  preflight blocked the machine; they do not mean the stored data vanished.
- Deployment and post-restart checks must be recorded separately. A healthy
  process or successful deploy will not be represented as a current universe.
- No frontend source changes since the deployed commit; reuse the existing
  frontend build rather than rebuilding unchanged assets during this update.
