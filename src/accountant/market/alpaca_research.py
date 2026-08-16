"""Alpaca Accountant read-only research adapter for THE ACCOUNTANT."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


@dataclass(frozen=True)
class AlpacaConfig:
    key_id: str
    secret_key: str
    data_base_url: str
    stock_feed: str
    timeout_seconds: float

    @property
    def configured(self) -> bool:
        return bool(self.key_id and self.secret_key)


def config() -> AlpacaConfig:
    return AlpacaConfig(
        key_id=_first_env("APCA_API_KEY_ID", "OPTIONS_APCA_API_KEY_ID"),
        secret_key=_first_env("APCA_API_SECRET_KEY", "OPTIONS_APCA_API_SECRET_KEY"),
        data_base_url=_first_env("ALPACA_DATA_BASE_URL", "OPTIONS_APCA_DATA_BASE_URL") or "https://data.alpaca.markets",
        stock_feed=_first_env("ALPACA_STOCK_FEED", "OPTIONS_APCA_STOCK_FEED") or "iex",
        timeout_seconds=8.0,
    )


def safety_state() -> dict[str, Any]:
    cfg = config()
    return {
        "enabled": cfg.configured,
        "provider": "alpaca_accountant",
        "mode": "research_only",
        "credential_preference": "APCA_* then OPTIONS_APCA_*",
        "data_base_url": cfg.data_base_url,
        "stock_feed": cfg.stock_feed,
        "order_mutation_policy": "blocked_before_http",
    }


def status() -> dict[str, Any]:
    cfg = config()
    if not cfg.configured:
        return {
            "ok": False,
            "connected": False,
            "checked_at": _now_iso(),
            "quality": "credentials_missing",
            "reason": "Alpaca Accountant credentials are not configured",
            "config": safety_state(),
        }
    try:
        response = _request_latest_quote("SPY", cfg)
        if response.status_code == 401:
            return {
                "ok": False,
                "connected": False,
                "checked_at": _now_iso(),
                "quality": "unauthorized",
                "reason": "Alpaca Accountant credentials were rejected by the data API",
                "config": safety_state(),
            }
        response.raise_for_status()
    except Exception as exc:
        return {
            "ok": False,
            "connected": False,
            "checked_at": _now_iso(),
            "quality": "unavailable",
            "reason": str(exc)[:500],
            "config": safety_state(),
        }
    return {
        "ok": True,
        "connected": True,
        "checked_at": _now_iso(),
        "quality": "research_only",
        "config": safety_state(),
    }


def _headers(cfg: AlpacaConfig) -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": cfg.key_id,
        "APCA-API-SECRET-KEY": cfg.secret_key,
    }


def _request_latest_quote(symbol: str, cfg: AlpacaConfig) -> httpx.Response:
    with httpx.Client(timeout=cfg.timeout_seconds, headers=_headers(cfg)) as client:
        return client.get(
            f"{cfg.data_base_url.rstrip('/')}/v2/stocks/{symbol}/quotes/latest",
            params={"feed": cfg.stock_feed},
        )


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def quote(symbol: str) -> dict[str, Any]:
    cfg = config()
    normalized = symbol.upper().strip()
    if not cfg.configured:
        return {
            "ok": False,
            "symbol": normalized,
            "checked_at": _now_iso(),
            "reason": "Alpaca Accountant credentials are not configured",
            "config": safety_state(),
        }

    try:
        response = _request_latest_quote(normalized, cfg)
        if response.status_code == 401:
            return {
                "ok": False,
                "symbol": normalized,
                "checked_at": _now_iso(),
                "reason": "Alpaca Accountant credentials were rejected by the data API",
                "config": safety_state(),
            }
        if response.status_code == 404:
            return {
                "ok": False,
                "symbol": normalized,
                "checked_at": _now_iso(),
                "reason": f"Alpaca quote not found for {normalized}",
                "config": safety_state(),
            }
        response.raise_for_status()
        payload = response.json() or {}
    except Exception as exc:
        return {
            "ok": False,
            "symbol": normalized,
            "checked_at": _now_iso(),
            "reason": str(exc)[:500],
            "config": safety_state(),
        }

    quote_payload = payload.get("quote") or {}
    bid = _float_or_none(quote_payload.get("bp"))
    ask = _float_or_none(quote_payload.get("ap"))
    midpoint = round((bid + ask) / 2, 4) if bid and ask else None

    return {
        "ok": True,
        "symbol": normalized,
        "checked_at": _now_iso(),
        "data_quality": "alpaca_latest_quote",
        "quote": {
            "bid": bid,
            "ask": ask,
            "last": midpoint,
            "close": midpoint,
        },
        "config": safety_state(),
    }
