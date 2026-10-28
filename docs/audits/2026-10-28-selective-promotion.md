# October 28 selective audit promotion

## Scope and source

Reviewed `origin/Claude-Gpt-audit` at
`a096821f102eb79a6c9c3497715d03e5b4292aca`, independently against main
`deec292d334683c1e9947ce0edf4c0534e9269e4`.
New audit commits since the previous review:

- `e1fe8b02a9f958a08b6d51e40d76cf335969f488`: storage and health safeguards.
- `a096821f102eb79a6c9c3497715d03e5b4292aca`: paused queues and quote status.

This is a selective implementation, not a merge or wholesale cherry-pick.
The audit branch is left unchanged. The Trading Terminal is out of scope.

## Accepted

| Change | Decision |
| --- | --- |
| Production storage settings | Require three finite positive limits; local/test zero defaults remain supported. Verified the live VPS already has 14/25/1 GiB limits and 128 MiB reserve. |
| Environment validation | Include the audit's prerequisite normalization/rejection of unknown environments so whitespace or a typo cannot bypass production checks. |
| Validation error privacy | Suppress input values in settings exception text; regression checks that a credential is not printed. |
| Controlled pause exit | Automation returns 75, not success. Adapt main's existing cycle-evidence reader to accept 75 only with a current matching paused-storage summary. |
| Status preservation | Keep main's generation-specific summaries, atomic status, exact budget reason, and independent last-success evidence. A bare exit 75 is not sufficient proof of a pause or completion. |
| Readiness gates | A live supervisor with a storage block cannot pass the work-running or zero-blocked readiness gates. Integration completion state explicitly says paused_storage. |
| Reserved HTTP paths | Missing health/API/assets endpoints return 404 instead of misleading SPA HTML success. Actual health and legitimate UI routes stay available. |
| Quote refresh | Partial/total quote failures remain visible as degraded status; an empty eligible board is not treated as a provider failure. |

## Not Promoted

- The audit's full paused-queue refresh calls `_load_role_inventory`, grouping
  entire filing/raw/canonical/snapshot tables. That would repeatedly scan
  millions of rows while blocked. Keep main's lightweight persisted company
  and report counts; a bounded/precomputed queue summary needs separate design.
- The branch's direct shell status replacement loses stronger mainline cycle
  evidence. Preserve main's implementation and adapt exit-code handling only.
- No older held annual-flow, disclosure/grading, schema 012-014, or broad
  worker/storage rewrites are newly approved by this pass. These changes are
  outside the two new commits and remain deferred rather than silently merged.
- No storage-limit increase, raw-fact cleanup, historical-card rewrite, broker
  action, or trading authority is authorized by this promotion.

## Validation

Local full suite: **566 passed**, one existing TestClient deprecation warning.
Ruff passed for source/tests and changed Python operations scripts.
Scoped auth/config types passed. Full-source debt ratchet passed: 236 existing
diagnostics, no new errors. This is not a full-source type-clean claim.

Regressions cover finite/positive/missing production limits, environment bypass,
credential-safe settings errors, reserved paths, worker reserve admission,
matched/malformed exit-75 evidence, real shell continuation on pause, and
zero/partial/all-success quote refreshes. Main's financial-input and packet-QA
quarantine tests remain in place.

## Production Baseline and Deployment Boundary

Verified Accountant host `129.121.138.129`, `/opt/case-capital/accountant`,
clean checkout at the main baseline above. API and scheduler active.
Database `accountant_vps2`, Alembic **011**:
14,909,774,871 bytes; 2,134 reports; latest filing October 22.
Filesystem free 28,838,465,536 bytes. Scheduler status is paused_storage,
database_cap_reached, last_success_at null.

No migration or frontend build is needed for this subset. Deploy only after
exact-commit CI passes; restart the Accountant API and scheduler, verify real
health/404 behavior, authenticated read readiness, and controlled pause status.
Do not infer research readiness from successful deployment. Capacity-safe
archive rebuilding, SEC catch-up, and independent report QA remain separate.
