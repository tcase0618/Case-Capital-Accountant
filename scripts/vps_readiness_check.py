from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Accountant VPS readiness through live API endpoints.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--max-sec-staleness-days", type=int, default=3)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    checks: list[dict[str, Any]] = []

    with httpx.Client(timeout=30.0) as client:
        health = _get_json(client, f"{base_url}/health", checks, "health")
        reports = _get_json(client, f"{base_url}/api/reports/status", checks, "reports_status")
        source = _get_json(client, f"{base_url}/api/source-integrity", checks, "source_integrity")
        _get_json(client, f"{base_url}/api/paper-books", checks, "paper_books")

    _expect(checks, "health_ok", health.get("status") == "ok", health)
    _expect(checks, "machine_running", bool(reports.get("running")), reports)
    _expect(checks, "reports_cached", int(reports.get("reports_cached") or 0) > 0, reports)
    _expect(checks, "no_report_loop_error", not reports.get("last_error"), reports.get("last_error"))
    _expect(checks, "source_integrity_not_failed", source.get("source_grade") in {"STRONG", "WATCH"}, source)
    sec = source.get("sec") or {}
    staleness = int(sec.get("days_since_latest_filing") or 999)
    _expect(checks, "sec_fresh_enough", staleness <= args.max_sec_staleness_days, sec)
    coverage = source.get("coverage") or {}
    _expect(checks, "report_coverage_100", float(coverage.get("report_coverage_pct") or 0.0) >= 99.0, coverage)
    _expect(checks, "bottleneck_coverage_100", float(coverage.get("bottleneck_coverage_pct") or 0.0) >= 99.0, coverage)

    ok = all(check["ok"] for check in checks)
    print(json.dumps({"ok": ok, "checks": checks}, indent=2))
    return 0 if ok else 1


def _get_json(client: httpx.Client, url: str, checks: list[dict[str, Any]], name: str) -> dict[str, Any]:
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
