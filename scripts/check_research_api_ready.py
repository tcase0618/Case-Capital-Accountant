from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass


DEFAULT_BASE_URL = "http://127.0.0.1:8010"


@dataclass
class CheckResult:
    ok: bool
    status_code: int | None
    detail: str | None = None
    payload: dict | list | str | None = None


def _fetch_json(url: str) -> CheckResult:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)
            return CheckResult(ok=True, status_code=response.status, payload=payload)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return CheckResult(ok=False, status_code=exc.code, detail=detail[:1000])
    except Exception as exc:  # pragma: no cover - operational script
        return CheckResult(ok=False, status_code=None, detail=str(exc))


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    base_url = base_url.rstrip("/")

    health = _fetch_json(f"{base_url}/health")
    reports = _fetch_json(f"{base_url}/api/reports/status")
    integration = _fetch_json(f"{base_url}/api/integration/accountant")
    ticker = _fetch_json(f"{base_url}/api/integration/accountant/AAPL")
    market = _fetch_json(f"{base_url}/api/integrations/ibkr")

    reports_payload = reports.payload if isinstance(reports.payload, dict) else {}
    integration_payload = integration.payload if isinstance(integration.payload, dict) else {}
    market_payload = market.payload if isinstance(market.payload, dict) else {}

    runtime_ok = health.ok and reports.ok and integration.ok and ticker.ok
    loop_running = bool(reports_payload.get("running"))
    loop_error = reports_payload.get("last_error")
    market_mode = market_payload.get("config", {}).get("mode") if isinstance(market_payload.get("config"), dict) else None
    research_mode_ok = market.ok and market_mode == "research_only"
    market_connected = bool(market_payload.get("connected"))
    backlog_remaining = int(integration_payload.get("pending_companies") or 0) if integration.ok else None
    queue_drained = backlog_remaining == 0
    api_surface_ready = runtime_ok and loop_running and not loop_error
    market_ready = research_mode_ok and market_connected
    ready = api_surface_ready and market_ready and queue_drained

    summary = {
        "ready": ready,
        "api_surface_ready": api_surface_ready,
        "market_ready": market_ready,
        "queue_drained": queue_drained,
        "runtime_ok": runtime_ok,
        "loop_running": loop_running,
        "loop_error": loop_error,
        "research_mode_ok": research_mode_ok,
        "market_connected": market_connected,
        "backlog_remaining": backlog_remaining,
        "checks": {
            "health": asdict(health),
            "reports": asdict(reports),
            "integration": asdict(integration),
            "ticker": asdict(ticker),
            "market": asdict(market),
        },
    }
    print(json.dumps(summary, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
