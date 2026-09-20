from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_ENDPOINTS = (
    ("health", "GET", "/health", 200),
    ("ready", "GET", "/ready", 200),
    ("dashboard", "GET", "/api/dashboard", 200),
    ("reports_status", "GET", "/api/reports/status", 200),
    ("source_integrity", "GET", "/api/source-integrity", 200),
    ("integration_status", "GET", "/api/integration/accountant", 200),
    ("reports", "GET", "/api/reports?limit=5", 200),
    ("report_cards_latest", "GET", "/api/report-cards/latest?limit=5", 200),
    ("sectors", "GET", "/api/sectors", 200),
    ("bottlenecks_summary", "GET", "/api/bottlenecks/summary", 200),
    ("buy_board_status", "GET", "/api/buy-board/status", 200),
    ("paper_books", "GET", "/api/paper-books", 200),
    ("ibkr_status", "GET", "/api/integrations/ibkr", 200),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Accountant research-only smoke tests and save the result.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010", help="Accountant API base URL.")
    parser.add_argument("--ticker", default="AAPL", help="Ticker used for ticker-specific smoke checks.")
    parser.add_argument("--output-dir", default="artifacts/smoke", help="Directory for saved smoke JSON.")
    parser.add_argument("--timeout", type=float, default=12.0, help="Per-request timeout in seconds.")
    args = parser.parse_args()

    started = datetime.now(UTC)
    endpoints = list(DEFAULT_ENDPOINTS)
    ticker = args.ticker.upper().strip()
    if ticker:
        endpoints.extend(
            (
                ("ticker_integration", "GET", f"/api/integration/accountant/{ticker}", 200),
                ("ticker_company", "GET", f"/api/companies/{ticker}", 200),
                ("ticker_market_quote", "GET", f"/api/companies/{ticker}/market-quote", 200),
            )
        )

    results = []
    for name, method, path, expected_status in endpoints:
        results.append(_check_endpoint(args.base_url, name, method, path, expected_status, args.timeout))

    summary = {
        "version": "ACCOUNTANT_SMOKE_V1",
        "base_url": args.base_url.rstrip("/"),
        "ticker": ticker,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "duration_seconds": round(time.time() - started.timestamp(), 3),
        "total": len(results),
        "passed": sum(1 for item in results if item["ok"]),
        "failed": sum(1 for item in results if not item["ok"]),
        "results": results,
    }
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"accountant_smoke_{started.strftime('%Y%m%dT%H%M%SZ')}.json"
    latest_path = out_dir / "accountant_smoke_latest.json"
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    latest_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print(f"saved={out_path}")
    print(f"passed={summary['passed']} failed={summary['failed']} total={summary['total']}")
    for item in results:
        status = "PASS" if item["ok"] else "FAIL"
        print(f"{status} {item['name']} {item['status_code']} {item['path']} {item.get('error') or ''}".rstrip())
    return 0 if summary["failed"] == 0 else 1


def _check_endpoint(base_url: str, name: str, method: str, path: str, expected_status: int, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    url = f"{base_url.rstrip('/')}{path}"
    result: dict[str, Any] = {
        "name": name,
        "method": method,
        "path": path,
        "expected_status": expected_status,
        "status_code": None,
        "ok": False,
        "elapsed_ms": None,
        "error": None,
        "sample": None,
    }
    try:
        request = Request(url, method=method, headers={"Accept": "application/json"})
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - local/dev smoke target.
            body = response.read(4096).decode("utf-8", errors="replace")
            result["status_code"] = response.status
            result["sample"] = _json_sample(body)
            result["ok"] = response.status == expected_status
    except HTTPError as exc:
        result["status_code"] = exc.code
        result["error"] = exc.reason
        result["ok"] = exc.code == expected_status
    except (URLError, TimeoutError, OSError) as exc:
        result["error"] = str(exc)
    finally:
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result


def _json_sample(body: str) -> Any:
    if not body:
        return None
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body[:500]
    if isinstance(parsed, list):
        return {"list_count_sample": len(parsed), "first": parsed[0] if parsed else None}
    if isinstance(parsed, dict):
        return {key: parsed[key] for key in list(parsed)[:8]}
    return parsed


if __name__ == "__main__":
    sys.exit(main())
