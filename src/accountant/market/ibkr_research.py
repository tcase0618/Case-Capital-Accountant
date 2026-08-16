"""Interactive Brokers read-only research adapter for THE ACCOUNTANT."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from accountant.config import get_settings

try:  # pragma: no cover - depends on optional/local IBKR runtime
    from ibapi.client import EClient as _IB_EClient
    from ibapi.wrapper import EWrapper as _IB_EWrapper
except Exception:  # pragma: no cover
    class _IB_EWrapper:  # type: ignore[no-redef]
        pass

    class _IB_EClient:  # type: ignore[no-redef]
        pass


class IbkrUnavailable(RuntimeError):
    """Raised when IBKR is disabled, unavailable, or disconnected."""


@dataclass(frozen=True)
class IbkrConfig:
    enabled: bool
    host: str
    port: int
    client_id: int
    read_only: bool
    timeout_seconds: float


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def config() -> IbkrConfig:
    settings = get_settings()
    return IbkrConfig(
        enabled=settings.ibkr_enabled,
        host=settings.ibkr_host,
        port=settings.ibkr_port,
        client_id=settings.ibkr_client_id,
        read_only=settings.ibkr_read_only,
        timeout_seconds=8.0,
    )


def safety_state() -> dict[str, Any]:
    cfg = config()
    return {
        "enabled": cfg.enabled,
        "host": cfg.host,
        "port": cfg.port,
        "client_id": cfg.client_id,
        "read_only": cfg.read_only,
        "mode": "research_only",
        "order_mutation_policy": "blocked_before_gateway",
    }


def _import_ibapi() -> tuple[Any, ...]:
    try:
        from ibapi.client import EClient
        from ibapi.contract import Contract
        from ibapi.wrapper import EWrapper
    except Exception as exc:  # pragma: no cover
        raise IbkrUnavailable(f"IBKR Python dependency unavailable: {exc}") from exc
    return EClient, EWrapper, Contract


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
        if math.isnan(parsed) or math.isinf(parsed):
            return None
        return parsed
    except Exception:
        return None


def _make_stock_contract(symbol: str) -> Any:
    _, _, Contract = _import_ibapi()
    contract = Contract()
    contract.symbol = symbol.upper().strip()
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    return contract


class _ReadOnlyIbApp(_IB_EWrapper, _IB_EClient):
    def __init__(self) -> None:
        EClient, EWrapper, _ = _import_ibapi()
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        self.connected_event = threading.Event()
        self.quote_done = threading.Event()
        self.errors: list[dict[str, Any]] = []
        self.next_order_id: int | None = None
        self.ticks: dict[str, float | None] = {}
        self.market_data_type = "unknown"

    def nextValidId(self, orderId: int) -> None:  # noqa: N802
        self.next_order_id = orderId
        self.connected_event.set()

    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
        self.errors.append(
            {
                "req_id": reqId,
                "code": errorCode,
                "message": errorString,
                "details": advancedOrderRejectJson,
            }
        )
        if errorCode in {200, 354, 10167, 10168, 10186}:
            self.quote_done.set()

    def tickPrice(self, reqId: int, tickType: int, price: float, attrib: Any) -> None:  # noqa: N802, ARG002
        mapping = {
            1: "bid",
            2: "ask",
            4: "last",
            9: "close",
            66: "delayed_bid",
            67: "delayed_ask",
            68: "delayed_last",
            75: "delayed_close",
        }
        key = mapping.get(tickType)
        if key:
            self.ticks[key] = _float_or_none(price)
            self.quote_done.set()

    def marketDataType(self, reqId: int, marketDataType: int) -> None:  # noqa: N802, ARG002
        mapping = {1: "live", 2: "frozen", 3: "delayed", 4: "delayed_frozen"}
        self.market_data_type = mapping.get(marketDataType, "unknown")


def _with_connection(fn):
    cfg = config()
    if not cfg.enabled:
        return {
            "ok": False,
            "reason": "IBKR_ENABLED=false",
            "checked_at": _now_iso(),
            "config": safety_state(),
        }
    if not cfg.read_only:
        return {
            "ok": False,
            "reason": "IBKR_READ_ONLY must remain true",
            "checked_at": _now_iso(),
            "config": safety_state(),
        }

    app = _ReadOnlyIbApp()
    thread: threading.Thread | None = None
    try:
        app.connect(cfg.host, cfg.port, cfg.client_id)
        thread = threading.Thread(target=app.run, daemon=True)
        thread.start()
        if not app.connected_event.wait(cfg.timeout_seconds):
            raise IbkrUnavailable("IBKR connection timed out before nextValidId")
        return fn(app, cfg)
    except Exception as exc:
        return {
            "ok": False,
            "reason": str(exc)[:500],
            "checked_at": _now_iso(),
            "config": safety_state(),
            "errors": app.errors[-8:],
        }
    finally:
        try:
            if app.isConnected():
                app.disconnect()
        except Exception:
            pass
        if thread and thread.is_alive():
            thread.join(timeout=1.0)


def status() -> dict[str, Any]:
    def _probe(app: _ReadOnlyIbApp, cfg: IbkrConfig) -> dict[str, Any]:
        return {
            "ok": True,
            "connected": bool(app.isConnected()),
            "checked_at": _now_iso(),
            "config": safety_state(),
            "quality": "research_only",
        }

    return _with_connection(_probe)


def quote(symbol: str, *, delayed_allowed: bool = True) -> dict[str, Any]:
    def _run(app: _ReadOnlyIbApp, cfg: IbkrConfig) -> dict[str, Any]:
        contract = _make_stock_contract(symbol)
        req_id = int(time.time() * 1000) % 1_000_000

        app.reqMarketDataType(1)
        app.reqMktData(req_id, contract, "100,101,104,106", False, False, [])
        app.quote_done.wait(min(3.0, cfg.timeout_seconds))
        app.cancelMktData(req_id)

        if delayed_allowed and not any(app.ticks.get(key) is not None for key in ("bid", "ask", "last", "close")):
            app.quote_done.clear()
            req_id += 1
            app.reqMarketDataType(3)
            app.reqMktData(req_id, contract, "100,101,104,106", False, False, [])
            app.quote_done.wait(min(3.0, cfg.timeout_seconds))
            app.cancelMktData(req_id)

        has_tick = any(app.ticks.get(key) is not None for key in ("bid", "ask", "last", "close", "delayed_bid", "delayed_ask", "delayed_last", "delayed_close"))
        if not has_tick:
            return {
                "ok": False,
                "symbol": symbol.upper(),
                "reason": "IBKR returned no live or delayed quote ticks; check Gateway/TWS, subscriptions, or delayed permissions.",
                "checked_at": _now_iso(),
                "config": safety_state(),
                "errors": app.errors[-8:],
            }

        return {
            "ok": True,
            "symbol": symbol.upper(),
            "checked_at": _now_iso(),
            "data_quality": app.market_data_type,
            "quote": {
                "bid": app.ticks.get("bid") or app.ticks.get("delayed_bid"),
                "ask": app.ticks.get("ask") or app.ticks.get("delayed_ask"),
                "last": app.ticks.get("last") or app.ticks.get("delayed_last"),
                "close": app.ticks.get("close") or app.ticks.get("delayed_close"),
            },
            "config": safety_state(),
        }

    result = _with_connection(_run)
    result.setdefault("symbol", symbol.upper())
    return result
