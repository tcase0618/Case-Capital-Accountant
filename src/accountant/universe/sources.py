from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable
from html import unescape
from html.parser import HTMLParser

import httpx

from accountant.domain.ticker import normalize_ticker

_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
_RUSSELL_2000_URL = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/latest-holdings.csv"


class _SimpleTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.rows: list[list[str]] = []
        self._row: list[str] = []
        self._cell: list[str] = []
        self._table_count = 0
        self._target_table = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_map = dict(attrs)
        if tag == "table" and "wikitable" in attrs_map.get("class", ""):
            if self._table_count == self._target_table:
                self.in_table = True
            self._table_count += 1
        elif self.in_table and tag == "tr":
            self.in_row = True
            self._row = []
        elif self.in_row and tag in {"th", "td"}:
            self.in_cell = True
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if self.in_cell and tag in {"th", "td"}:
            self.in_cell = False
            self._row.append(unescape("".join(self._cell)).strip())
        elif self.in_row and tag == "tr":
            self.in_row = False
            if self._row:
                self.rows.append(self._row)
        elif self.in_table and tag == "table":
            self.in_table = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self._cell.append(data)


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(30.0),
        headers={
            "User-Agent": "Case Capital Accountant accountant@casecapital.example",
            "Accept-Encoding": "identity",
        },
        follow_redirects=True,
    )


def _normalize_many(symbols: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in symbols:
        try:
            ticker = normalize_ticker(raw)
        except Exception:
            continue
        if ticker in seen:
            continue
        seen.add(ticker)
        normalized.append(ticker)
    return normalized


def load_sp500_tickers() -> list[str]:
    with _client() as client:
        response = client.get(_SP500_URL)
        response.raise_for_status()
    parser = _SimpleTableParser()
    parser.feed(response.text)
    rows = parser.rows
    tickers = []
    for row in rows[1:]:
        if not row:
            continue
        ticker = row[0].replace(".", "-").strip()
        tickers.append(ticker)
    return _normalize_many(tickers)


def load_nasdaq_tickers() -> list[str]:
    with _client() as client:
        response = client.get(_NASDAQ_URL)
        response.raise_for_status()
    reader = csv.DictReader(io.StringIO(response.text), delimiter="|")
    tickers: list[str] = []
    blocked_words = (
        "Warrant",
        "Right",
        "Unit",
        "Preferred",
        "ETF",
        "ETN",
        "Trust",
        "Fund",
        "Notes",
    )
    for row in reader:
        symbol = (row.get("Symbol") or "").strip()
        name = (row.get("Security Name") or "").strip()
        if not symbol or symbol == "File Creation Time":
            continue
        if (row.get("ETF") or "").strip().upper() == "Y":
            continue
        if any(word.lower() in name.lower() for word in blocked_words):
            continue
        tickers.append(symbol)
    return _normalize_many(tickers)


def load_russell2000_tickers() -> list[str]:
    with _client() as client:
        response = client.get(_RUSSELL_2000_URL)
        response.raise_for_status()
    lines = response.text.splitlines()
    start = 0
    for index, line in enumerate(lines):
        if line.startswith("Ticker,"):
            start = index
            break
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    tickers: list[str] = []
    for row in reader:
        asset_class = (row.get("Asset Class") or "").strip()
        symbol = (row.get("Ticker") or "").strip()
        if asset_class and asset_class.lower() != "equity":
            continue
        if not symbol or symbol in {"-", "CASH", "USD"}:
            continue
        if re.search(r"[^A-Z\.\-]", symbol):
            continue
        tickers.append(symbol.replace(".", "-"))
    return _normalize_many(tickers)


def load_universe_tickers(universe_names: list[str]) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for name in universe_names:
        key = name.strip().lower()
        if key == "sp500":
            results[key] = load_sp500_tickers()
        elif key == "nasdaq":
            results[key] = load_nasdaq_tickers()
        elif key == "russell2000":
            results[key] = load_russell2000_tickers()
        else:
            results[key] = []
    return results
