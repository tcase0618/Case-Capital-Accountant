from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from accountant.universe import load_universe_tickers


@dataclass(frozen=True)
class UniverseMembership:
    in_sp500: bool
    in_russell2000: bool
    in_nasdaq_comp: bool


@lru_cache(maxsize=1)
def load_membership_maps() -> dict[str, set[str]]:
    loaded = load_universe_tickers(["sp500", "russell2000", "nasdaq", "nysearca"])
    return {
        "sp500": set(loaded.get("sp500", [])),
        "russell2000": set(loaded.get("russell2000", [])),
        "nasdaq": set(loaded.get("nasdaq", [])),
        "nysearca": set(loaded.get("nysearca", [])),
    }


def membership_for_ticker(ticker: str) -> UniverseMembership:
    maps = load_membership_maps()
    symbol = ticker.upper().strip()
    return UniverseMembership(
        in_sp500=symbol in maps["sp500"],
        in_russell2000=symbol in maps["russell2000"],
        in_nasdaq_comp=symbol in maps["nasdaq"],
    )


def any_membership(symbols: Iterable[str]) -> set[str]:
    maps = load_membership_maps()
    values = {symbol.upper().strip() for symbol in symbols}
    return {
        symbol
        for symbol in values
        if symbol in maps["sp500"] or symbol in maps["russell2000"] or symbol in maps["nasdaq"] or symbol in maps["nysearca"]
    }
