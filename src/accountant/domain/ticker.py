from __future__ import annotations

import re

from accountant.domain.exceptions import MalformedTickerError

# SEC tickers are short symbols; class shares use . or - (BRK-B, BF.B).
_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")


def normalize_ticker(ticker: str | None) -> str:
    """Uppercase and validate a ticker. Never invent a replacement symbol."""
    if ticker is None:
        raise MalformedTickerError("ticker is required")
    cleaned = str(ticker).strip().upper()
    if not cleaned:
        raise MalformedTickerError("ticker is required")
    if not _TICKER_RE.fullmatch(cleaned):
        raise MalformedTickerError(f"malformed ticker: {ticker!r}")
    return cleaned
