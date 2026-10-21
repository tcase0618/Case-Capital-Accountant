from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from accountant.ops.edgar_calendar import CALENDAR_VERSION, edgar_business_days_since


def main() -> int:
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
    scheduler = scheduler_status(args.scheduler_status_file)
    _expect(checks, "scheduler_recent_and_successful", scheduler["ok"], scheduler)

    with httpx.Client(timeout=30.0) as client:
        health = _get_json(client, f"{base_url}/health", checks, "health")
        reports = _get_json(client, f"{base_url}/api/reports/status", checks, "reports_status")
        source = _get_json(client, f"{base_url}/api/source-integrity", checks, "source_integrity")
        _get_json(client, f"{base_url}/api/paper-books", checks, "paper_books")

    _expect(checks, "health_ok", health.get("status") == "ok", health)
    _expect(checks, "machine_running", bool(reports.get("running")), reports)
    _expect(checks, "reports_cached", int(reports.get("reports_cached") or 0) > 0, reports)
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
    sec = source.get("sec") or {}
    freshness = sec_freshness(sec, max_business_days=args.max_sec_staleness_days)
    _expect(checks, "sec_fresh_enough", freshness["ok"], freshness)
    coverage = source.get("coverage") or {}
    _expect(
        checks,
        "report_coverage_100",
        float(coverage.get("report_coverage_pct") or 0.0) >= 99.0,
        coverage,
    )
    _expect(
        checks,
        "bottleneck_coverage_100",
        float(coverage.get("bottleneck_coverage_pct") or 0.0) >= 99.0,
        coverage,
    )

    ok = all(check["ok"] for check in checks)
    print(json.dumps({"ok": ok, "checks": checks}, indent=2))
    return 0 if ok else 1


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
        return {
            "ok": not status.get("last_error") and 0 <= age <= 36 * 3600,
            "last_success_at": status["last_success_at"],
            "last_error": status.get("last_error"),
            "backup_bytes": int(status["backup_bytes"]),
        }
    except (OSError, ValueError, KeyError, TypeError):
        return {"ok": False, "last_error": "backup_status_unavailable"}


def scheduler_status(path: Path) -> dict[str, Any]:
    try:
        status = json.loads(path.read_text())
        last_cycle = datetime.fromisoformat(status["last_cycle_at"])
        if last_cycle.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        age = (datetime.now(UTC) - last_cycle).total_seconds()
        return {
            "ok": status["status"] == "complete"
            and status["exit_code"] == 0
            and 0 <= age <= 36 * 3600,
            "status": status["status"],
            "exit_code": status["exit_code"],
            "last_cycle_at": status["last_cycle_at"],
        }
    except (OSError, ValueError, KeyError, TypeError):
        return {"ok": False, "status": "scheduler_status_unavailable"}


def _get_json(
    client: httpx.Client, url: str, checks: list[dict[str, Any]], name: str
) -> dict[str, Any]:
    try:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        checks.append({"name": f"{name}_http", "ok": False, "detail": str(exc)})
        return {}
    checks.append({"name": f"{name}_http", "ok": True, "detail": response.status_code})
    return payload


def _expect(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


if __name__ == "__main__":
    raise SystemExit(main())
