# November 8 audit promotion

Source: Claude-Gpt-audit at 620de22fc63f36283030e79de1e269b6ad21c0e7.
Baseline main: 7bf20121c8c25908cd7ca1834b68520b81f2fd51.

## Accepted

- 97d3c5d: engine-scoped 30-second single-flight source-integrity cache.
  Deep-copy responses, retain evidence generation time, propagate refresh
  failures rather than serving expired evidence. CLI builders remain uncached.
- 620de22: published NYSE 2026-2028 quote-refresh sessions, holidays,
  early closes, UTC elapsed waits across DST, missed-session guards and
  unsupported-calendar pause reporting. Add API calendar/session metadata.
- Both source regression suites, adapted onto current main without replacing
  mainline scoring, publication or financial-input controls.

Calendar verified against the NYSE/ICE December 23, 2025 publication:
https://ir.theice.com/press/news-details/2025/NYSE-Group-Announces-2026-2027-and-2028-Holiday-and-Early-Closings-Calendar/

## Held

Older audit-branch math, migrations and worker changes remain unapproved.
In particular, retain main's validated-report gates, duration-aware fact
selection, missing-data behavior, quote errors and research packet gates.
Do not replace complete files with their audit-branch versions.

## Evidence Boundaries

The cache reduces duplicate work; cold or expired snapshots still execute the
underlying queries. It is per process, not a distributed cache. The calendar
requires explicit updates for later years or unscheduled market closures.
No runtime LLMs, execution authority, storage-cap changes, production
migrations, historical fact deletion or report rescoring are included.
Deployment and data readiness must be verified and reported separately.
