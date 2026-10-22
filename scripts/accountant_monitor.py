"""Read-only, one-shot operations monitor; scheduling is external."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from vps_readiness_check import backup_status, scheduler_status, sec_freshness


def collect(client: httpx.Client, base_url: str, backup: Path, scheduler: Path) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    payloads = {}
    for name, route in (
        ("health", "/health"),
        ("reports", "/api/reports/status"),
        ("source", "/api/source-integrity"),
    ):
        try:
            # No retries, redirects, response bodies, exception text, or URLs in logs.
            with client.stream("GET", base_url.rstrip("/") + route) as response:
                response.raise_for_status()
                body = bytearray()
                deadline = time.monotonic() + 10
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 1024 * 1024 or time.monotonic() > deadline:
                        raise ValueError("oversized response")
                payload = json.loads(body)
                if not isinstance(payload, dict):
                    raise ValueError("expected object")
            payloads[name] = payload
            checks[name + "_available"] = True
        except (httpx.HTTPError, ValueError, TypeError):
            payloads[name] = {}
            checks[name + "_available"] = False
    health, reports, source = (payloads[key] for key in ("health", "reports", "source"))
    healthy = checks["health_available"] and health.get("status") == "ok"
    checks["healthy"] = healthy
    checks["research_running"] = reports.get("running") is True
    checks["storage_clear"] = reports.get("storage_blocked") is False
    checks["report_loop_clear"] = "last_error" in reports and not reports["last_error"]
    count = reports.get("reports_cached")
    checks["reports_cached"] = type(count) is int and count > 0
    checks["source_grade"] = source.get("source_grade") in ("STRONG", "WATCH")
    sec = source.get("sec")
    checks["sec_fresh"] = isinstance(sec, dict) and sec_freshness(sec, max_business_days=3)["ok"]
    coverage = source.get("coverage")
    for field in ("report_coverage_pct", "bottleneck_coverage_pct"):
        value = coverage.get(field) if isinstance(coverage, dict) else None
        checks[field] = type(value) in (int, float) and 99 <= value <= 100
    backup_result = backup_status(backup)
    checks["backup_recent"] = backup_result["ok"]
    checks["backup_recovery_verified"] = backup_result.get("recovery_evidence") == "verified"
    checks["scheduler_ready"] = scheduler_status(scheduler)["ok"]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "healthy": healthy,
        "ready": all(checks.values()),
        "checks": checks,
    }


def notify(result: dict[str, Any], webhook: str | None, client: httpx.Client) -> str:
    if not webhook:
        return "not_configured"
    try:
        url = urlsplit(webhook)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            return "invalid_configuration"
        with client.stream("POST", webhook, json=result) as response:
            response.raise_for_status()
    except (httpx.HTTPError, ValueError):
        return "failed"
    return "http_accepted"  # HTTP acceptance is not confirmed downstream delivery.


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--backup-status-file", type=Path, default=Path("/backups/status.json"))
    parser.add_argument(
        "--scheduler-status-file",
        type=Path,
        default=Path(os.environ.get("DATA_DIR", "data")) / "scheduler_cycle_status.json",
    )
    args = parser.parse_args()
    # Finite request timeouts and body limits bound each check; never retry.
    with httpx.Client(timeout=5.0, follow_redirects=False, trust_env=False) as client:
        result = collect(client, args.base_url, args.backup_status_file, args.scheduler_status_file)
        result["notification"] = notify(
            result, os.environ.get("ACCOUNTANT_MONITOR_WEBHOOK_URL"), client
        )
    print(json.dumps(result, allow_nan=False))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
