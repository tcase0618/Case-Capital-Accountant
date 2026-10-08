# Selective Audit Promotion October 8 2026

Source reviewed: Claude-Gpt-audit at a5ba4145c70440648bbb93531255c1fdd886d65d.
Base reviewed: main at 131d47829e7d5669574b829e972cd0eb10da1591.

The user authorized selective main promotion following independent review.
This is not a production deployment or an approval of the investment strategy.

## Accepted Scope

- Constant-time bearer comparison, authenticated market lookup routes, and
  an operator token held in browser memory rather than persisted storage.
- API lifespan cleanup, including startup failure; no production create_all.
- Generic public market errors with server-side diagnostic logging.
- Locked Python/frontend builds, required dummy compose environment in CI,
  and the compatible source-map-js advisory patch.
- Loopback-only compose API exposure, separate PostgreSQL 16 backup tooling,
  private atomic dump creation, and opt-in isolated restore verification.
- Scheduler window timing and continuing after a failed cycle.

## Deferred Scope

No grading, valuation, companyfacts ingestion, discovery schema, shared SEC
limiter, or shared storage-job serialization changes are promoted in this pass.
Dependencies and their dedicated tests remain together on the audit branch.

Two independently reproduced disclosure defects block full-branch promotion:

1. A latest dividend 8-K excludes the current annual going-concern evidence
   from the candidate list and reports the condition as false.
2. Conditional non-reliance language triggers Big-R and severity 95.

The shared storage gate serializes full jobs across processes. Its capacity
benefit must be weighed against measured throughput and recovery behavior.

## Daily Review Contract

Daily remediation stays on Claude-Gpt-audit. This selective promotion is not
blanket authorization for future main merges or production deployments.
Review new diffs, inspect evidence, test the proposed combined main result,
and record accepted and deferred work. Preserve immutable source/history and
unrelated work. CI passing is necessary but does not prove live readiness.

The source branch's 444 tests and green CI describe that branch, not this
selective subset. Report independent subset checks separately.

## Independent Local Verification

- Full Python suite: 394 passed, one existing Starlette/httpx warning.
- Ruff src/tests: passed.
- Mypy auth/config: passed, scoped to two files only.
- Strict app deprecation API/lifecycle checks: 20 passed, one unrelated warning.
- Frontend operator-token test: one passed.
- Frontend production build: passed.

No VPS restart, database migration, live ingestion, or deployment was performed.
Docker validation is delegated to CI; local Docker/restore acceptance is not claimed.
