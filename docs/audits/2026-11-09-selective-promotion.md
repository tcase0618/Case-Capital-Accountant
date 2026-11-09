# November 9 audit review

Source: Claude-Gpt-audit 5c055cb26c7573ed55d87eaab5de6ef6c372a229.
Main baseline: 438c1f12dabfa27391bb5b75096fa9b18007b53b.

## Accepted

Promote the new exact-cohort metrics change and its regressions:

- Report coverage counts companies with a report, not report rows.
- Bottleneck coverage counts reported companies that also have a bottleneck;
  an unrelated company's bottleneck cannot fill the gap.
- Canonical lineage numerator and denominator come from one SQL statement.
- Raw/canonical count densities and statements per report are ratios, not
  percentages or evidence of mapping completeness.
- Planner estimates remain informational and cannot affect source grading.
- Unmeasured mapping coverage is explicitly NOT_MEASURED; legacy misleading
  percentage fields remain present but null. Empty lineage cohorts are unknown.
- Version source metrics as SOURCE_INTEGRITY_V2_EXACT_COHORTS.

No current application consumers reference the deprecated percentage fields.
The existing flexible API coverage dictionary preserves the new fields.
Unknown mapping completeness conservatively prevents an unqualified STRONG
snapshot via an explicit warning; it does not claim an extraction repair.

## Boundaries

This does not verify the correctness of every lineage pointer or financial
report, measure true mapping completeness, clear storage admission, or grant
research/trading acceptance. Existing cache, validation and packet gates remain.
No dependencies, migrations, frontend, storage caps, data deletion or older
held audit-branch changes are included. Cold snapshots still scan canonical
facts once for exact lineage; cache remains process-local and 30 seconds.
