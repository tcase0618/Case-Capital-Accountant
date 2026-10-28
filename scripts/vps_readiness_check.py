from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from accountant.ops.edgar_calendar import CALENDAR_VERSION, edgar_business_days_since
from accountant.ops.polling_schedule import DEFAULT_WINDOWS, EASTERN, parse_windows


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--record-cycle":
        path, summary, code, started, finished, generation = sys.argv[2:]
        print(
            json.dumps(
                record_cycle(Path(path), Path(summary), int(code), started, finished, generation)
            )
        )
        return 0
    parser = argparse.ArgumentParser(
        description="Validate Accountant VPS readiness through live API endpoints."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument(
        "--max-sec-staleness-days",
        type=int,
        default=3,
        help="Maximum EDGAR business days after the latest filing (default: 3).",
    )
    parser.add_argument("--backup-status-file", type=Path, default=Path("/backups/status.json"))
    parser.add_argument(
        "--scheduler-status-file",
        type=Path,
        default=Path(os.environ.get("DATA_DIR", "data")) / "scheduler_cycle_status.json",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    checks: list[dict[str, Any]] = []
    backup = backup_status(args.backup_status_file)
    _expect(checks, "backup_recent_and_successful", backup["ok"], backup)
    if "recovery_evidence" in backup:
        _expect(
            checks,
            "backup_recovery_verified",
            backup["recovery_evidence"] == "verified",
            backup["recovery_evidence"],
        )
    scheduler = scheduler_status(args.scheduler_status_file)
    _expect(checks, "scheduler_recent_and_successful", scheduler["ok"], scheduler)

    with httpx.Client(timeout=30.0) as client:
        health = _get_json(client, f"{base_url}/health", checks, "health")
        reports = _get_json(client, f"{base_url}/api/reports/status", checks, "reports_status")
        source = _get_json(client, f"{base_url}/api/source-integrity", checks, "source_integrity")
        _get_json(client, f"{base_url}/api/paper-books", checks, "paper_books")

    _expect(checks, "health_ok", health.get("status") == "ok", health)
    _expect(checks, "machine_running", bool(reports.get("running")) and not reports.get("storage_blocked"), reports)
    cached = reports.get("reports_cached")
    _expect(checks, "reports_cached", type(cached) is int and cached > 0, reports)
    _expect(
        checks, "no_report_loop_error", not reports.get("last_error"), reports.get("last_error")
    )
    _expect(
        checks,
        "storage_not_blocked",
        not reports.get("storage_blocked"),
        reports.get("storage_block_reason"),
    )
    _expect(
        checks,
        "source_integrity_not_failed",
        source.get("source_grade") in {"STRONG", "WATCH"},
        source,
    )
    sec = source.get("sec") if isinstance(source.get("sec"), dict) else {}
    freshness = sec_freshness(sec, max_business_days=args.max_sec_staleness_days)
    _expect(checks, "sec_fresh_enough", freshness["ok"], freshness)
    coverage = source.get("coverage") if isinstance(source.get("coverage"), dict) else {}
    _expect(
        checks,
        "report_coverage_100",
        _coverage_valid(coverage.get("report_coverage_pct")),
        coverage,
    )
    _expect(
        checks,
        "bottleneck_coverage_100",
        _coverage_valid(coverage.get("bottleneck_coverage_pct")),
        coverage,
    )

    ok = all(check["ok"] for check in checks)
    print(json.dumps({"ok": ok, "ready": ok, "checks": checks}, indent=2))
    return 0 if ok else 1


def _coverage_valid(value: Any) -> bool:
    return type(value) in (int, float) and 99 <= value <= 100


def sec_freshness(sec: dict[str, Any], *, max_business_days: int) -> dict[str, Any]:
    as_of = datetime.now(ZoneInfo("America/New_York")).date()
    detail = {
        "calendar_version": CALENDAR_VERSION,
        "as_of_date": as_of.isoformat(),
        "latest_filing_date": sec.get("latest_filing_date"),
        "max_business_days": max_business_days,
    }
    try:
        latest = date.fromisoformat(sec["latest_filing_date"])
        age = edgar_business_days_since(latest, as_of=as_of)
    except (ValueError, KeyError, TypeError):
        return {**detail, "ok": False, "error": "sec_filing_date_unavailable_or_invalid"}
    return {**detail, "ok": 0 <= age <= max_business_days, "business_days_since_latest_filing": age}


def backup_status(path: Path) -> dict[str, Any]:
    try:
        status = json.loads(path.read_text())
        success = datetime.fromisoformat(status["last_success_at"])
        if success.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        age = (datetime.now(UTC) - success).total_seconds()
        evidence = backup_evidence(status, path.parent)
        return {
            "ok": not status.get("last_error")
            and 0 <= age <= 36 * 3600
            and type(status["backup_bytes"]) is int
            and status["backup_bytes"] > 0
            and evidence != "invalid",
            "last_success_at": status["last_success_at"],
            "last_error": status.get("last_error"),
            "backup_bytes": int(status["backup_bytes"]),
            "recovery_evidence": evidence,
        }
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {"ok": False, "last_error": "backup_status_unavailable"}


def scheduler_status(path: Path, *, now: datetime | None = None) -> dict[str, Any]:
    try:
        status = json.loads(path.read_text())
        last_cycle = datetime.fromisoformat(status["last_cycle_at"])
        if last_cycle.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        now = now or datetime.now(UTC)
        age = (now - last_cycle).total_seconds()
        interval = int(os.environ.get("ACCOUNTANT_ACTIVE_POLL_INTERVAL_SECONDS", "900"))
        if interval <= 0:
            raise ValueError("invalid interval")
        windows = parse_windows(os.environ.get("ACCOUNTANT_POLL_WINDOWS", DEFAULT_WINDOWS))
        # Ignore closed hours, but detect a missed poll even after a window closes.
        missed = False
        local_now = now.astimezone(EASTERN)
        for offset in (0, 1, 2):
            day = local_now.date() - timedelta(days=offset)
            for window in windows:
                start = datetime.combine(day, window.start, tzinfo=EASTERN).astimezone(UTC)
                end = datetime.combine(day, window.end, tzinfo=EASTERN).astimezone(UTC)
                elapsed = (min(now, end) - max(last_cycle, start)).total_seconds()
                missed = missed or elapsed > 2 * interval
        return {
            "ok": status["status"] == "complete"
            and status["exit_code"] == 0
            and 0 <= age <= 36 * 3600
            and not missed,
            "status": status["status"],
            "exit_code": status["exit_code"],
            "last_cycle_at": status["last_cycle_at"],
            "reason": status.get("reason"),
            "last_success_at": status.get("last_success_at"),
            "generation": status.get("generation"),
            "missed_active_poll": missed,
        }
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {"ok": False, "status": "scheduler_status_unavailable"}


def record_cycle(
    path: Path, summary: Path, code: int, started: str, finished: str, generation: str
) -> dict[str, Any]:
    previous: dict[str, Any] = {}
    try:
        previous = json.loads(path.read_text())
        if not isinstance(previous, dict):
            previous = {}
    except (OSError, ValueError):
        pass
    result = {
        "status": "failed",
        "exit_code": code,
        "reason": "automation_process_failed",
        "started_at": started,
        "last_cycle_at": finished,
        "generation": generation,
        # Legacy "complete" only meant process exit 0, including storage pauses.
        # It cannot be promoted into evidence of a successful research cycle.
        "last_success_at": previous.get("last_success_at"),
    }
    if code not in (0, 75):
        return result
    try:
        payload = json.loads(summary.read_text())
        generated = datetime.fromisoformat(payload["generated_at"])
        if generated.tzinfo is None or not (
            datetime.fromisoformat(started)
            <= generated
            <= datetime.fromisoformat(finished) + timedelta(seconds=1)
        ):
            raise ValueError("summary is not from this cycle")
        result["automation_generated_at"] = payload["generated_at"]
        storage = payload["storage"]
        if storage["blocked"] is True and (
            code == 0 or payload.get("status") == "paused_storage"
        ):
            result.update(
                status="paused_storage", reason=storage.get("reason") or "storage_blocked"
            )
        elif (
            code == 0
            and storage["blocked"] is False
            and payload.get("status") == "complete"
            and all(step["returncode"] == 0 for step in payload["steps"])
        ):
            result.update(status="complete", reason=None, last_success_at=finished)
        else:
            result["reason"] = "automation_not_complete"
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        result["reason"] = "automation_summary_unavailable_or_invalid"
    return result


def backup_evidence(status: dict[str, Any], directory: Path) -> str:
    """Only a manifest naming local evidence can establish recovery verification."""
    fields = ("archive_path", "checksum_path", "restore_evidence_path")
    if not any(field in status for field in fields):
        return "unverified"
    if not all(isinstance(status.get(field), str) and status[field] for field in fields):
        return "unverified"
    paths = [Path(status[field]) for field in fields]
    if any("://" in status[field] for field in fields):
        return "unverified"
    archive, checksum, restore = [p if p.is_absolute() else directory / p for p in paths]
    try:
        if not archive.is_file() or archive.stat().st_size <= 0:
            return "invalid"
        expected = None
        for line in checksum.read_text().splitlines():
            digest, name = line.split(maxsplit=1)
            if name.lstrip("*") == archive.name:
                expected = digest
        with archive.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if expected != actual:
            return "invalid"
        marker = restore.read_text().strip()
        if not marker.startswith("restore_verified_at="):
            return "invalid"
        verified = datetime.fromisoformat(marker.partition("=")[2])
        success = datetime.fromisoformat(status["last_success_at"])
        if verified.tzinfo is None or not success <= verified <= datetime.now(UTC):
            return "invalid"
    except (OSError, ValueError, TypeError):
        return "invalid"
    return "verified"


def _get_json(
    client: httpx.Client, url: str, checks: list[dict[str, Any]], name: str
) -> dict[str, Any]:
    try:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("expected JSON object")
    except Exception:
        checks.append({"name": f"{name}_http", "ok": False, "detail": "unavailable_or_invalid"})
        return {}
    checks.append({"name": f"{name}_http", "ok": True, "detail": response.status_code})
    return payload


def _expect(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


if __name__ == "__main__":
    raise SystemExit(main())
