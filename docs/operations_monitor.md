# Read-only operations monitor

Run `python scripts/accountant_monitor.py` from the repository with the application
environment. This is a one-shot check, not a scheduler or recovery executor. It
does not change storage budgets, research settings, data, or orders. Schedule it
externally if desired. JSON stdout and exit 0 mean readiness; exit 1 is not ready.
`healthy` only describes `/health`, never research or recovery readiness.

API requests use finite timeouts, no redirects/retries, and a 1 MiB JSON limit.
Unavailable, unknown, or malformed endpoints fail closed. JSON logs contain no
response bodies, URLs, credentials, or exception text. An optional
`ACCOUNTANT_MONITOR_WEBHOOK_URL` sends that same sanitized result over HTTPS.
`not_configured`, `invalid_configuration`, `failed`, and `http_accepted` are distinct;
HTTP acceptance does not prove downstream notification delivery. No notification
destination or delivery has been provisioned or tested by this change.

The shell scheduler gives each cycle a unique summary path and generation. A
storage-blocked JSON report with exit 0 becomes `paused_storage`, not `complete`.
Cycle time, automation generation time, reason, and last successful research time
are separate. Missing/invalid summaries fail closed. Scheduler readiness rejects
failed/paused, future, older-than-36-hour, or missed-active-poll evidence. Polling
uses `ACCOUNTANT_POLL_WINDOWS` and `ACCOUNTANT_ACTIVE_POLL_INTERVAL_SECONDS` with
a two-interval grace inside Eastern-time windows, including missed closed windows.

Legacy backup status with positive `backup_bytes` can still pass the compatibility
recency check, but its `recovery_evidence` is `unverified` and the monitor is NOT
ready. For local verification the external backup producer must supply these
additional status manifest fields: `archive_path`, `checksum_path`, and
`restore_evidence_path`. Relative paths resolve beside the manifest; URLs are not
verification evidence. The archive must exist and be nonempty; its SHA-256 must
match its named entry in the checksum file; the restore marker must contain
`restore_verified_at=<timezone-aware timestamp>` between backup success and now.
This verifies local recorded evidence, not an independently rerun restore.
Archive creation, host-side manifests, restore drills, and live checks remain
external responsibilities. No archive inference, deletion, or restore is attempted.
