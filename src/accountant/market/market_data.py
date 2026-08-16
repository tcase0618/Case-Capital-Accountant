"""Market data interface for valuation research (read-only, no trading)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class HistoricalPrice:
    """Single historical price point for a security."""

    date: str  # YYYY-MM-DD
    open_price: float | None
    high_price: float | None
    low_price: float | None
    close_price: float | None
    adjusted_close: float | None
    volume: int | None


@dataclass(frozen=True)
class MarketCapSnapshot:
    """Market capitalization at a point in time."""

    date: str  # YYYY-MM-DD
    market_cap_usd: float | None  # Total market cap
    price_per_share: float | None
    shares_outstanding: int | None


@dataclass(frozen=True)
class EnterpriseValueData:
    """Enterprise value calculation inputs."""

    date: str  # YYYY-MM-DD
    market_cap_usd: float | None
    cash_and_equivalents_usd: float | None
    debt_usd: float | None
    preferred_equity_usd: float | None
    minority_interest_usd: float | None

    @property
    def enterprise_value_usd(self) -> float | None:
        """Calculate enterprise value."""
        if self.market_cap_usd is None:
            return None
        ev = self.market_cap_usd
        if self.debt_usd:
            ev += self.debt_usd
        if self.cash_and_equivalents_usd:
            ev -= self.cash_and_equivalents_usd
        if self.preferred_equity_usd:
            ev += self.preferred_equity_usd
        if self.minority_interest_usd:
            ev += self.minority_interest_usd
        return ev


@dataclass(frozen=True)
class MarketDataQuery:
    """Request for market data."""

    ticker: str
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    data_types: list[str]  # ["price", "market_cap", "enterprise_value"]


class MarketDataInterface:
    """
    Read-only market data access for valuation research.

    This interface provides:
    - Historical price data (open, high, low, close, adjusted close)
    - Market capitalization snapshots
    - Enterprise value components

    CRITICAL: This is research-only access.
    - NO real-time data (no trading decisions)
    - NO order placement
    - Broker connectivity, if added, must remain research-only
    - Data sourced from public feeds (Yahoo Finance, SEC filings, etc.)
    """

    @staticmethod
    def get_price_history(
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> list[HistoricalPrice]:
        """
        Get historical price data for a security.

        Data is NOT adjusted for splits/dividends unless using
        adjusted_close field (which is adjusted).

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of HistoricalPrice objects (earliest to latest)
        """
        # Stub: Would query Yahoo Finance API or database
        return []

    @staticmethod
    def get_latest_price(ticker: str) -> HistoricalPrice | None:
        """
        Get most recent closing price.

        Note: NOT real-time; may be delayed per data provider terms.

        Args:
            ticker: Stock ticker

        Returns:
            Latest HistoricalPrice or None if not found
        """
        # Stub: Would query database or API
        return None

    @staticmethod
    def get_market_cap_at_date(
        ticker: str,
        as_of_date: str,
    ) -> MarketCapSnapshot | None:
        """
        Get market capitalization at a point in time.

        Uses closing price and shares outstanding from SEC filings
        or market data sources.

        Args:
            ticker: Stock ticker
            as_of_date: Query date (YYYY-MM-DD)

        Returns:
            MarketCapSnapshot or None if unavailable
        """
        # Stub: Would calculate from price + filing shares
        return None

    @staticmethod
    def get_market_cap_history(
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> list[MarketCapSnapshot]:
        """
        Get market cap history over a date range.

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of MarketCapSnapshot objects
        """
        # Stub: Would calculate for each date
        return []

    @staticmethod
    def get_enterprise_value_at_date(
        ticker: str,
        as_of_date: str,
    ) -> EnterpriseValueData | None:
        """
        Calculate enterprise value at a point in time.

        Combines market data (price, shares) with financial data
        (debt, cash) from SEC filings at the specified date.

        Args:
            ticker: Stock ticker
            as_of_date: Query date (YYYY-MM-DD)

        Returns:
            EnterpriseValueData with calculated EV or None
        """
        # Stub: Would combine price + filing data
        return None

    @staticmethod
    def get_price_at_date(
        ticker: str,
        as_of_date: str,
    ) -> float | None:
        """
        Get closing price for specific date.

        Args:
            ticker: Stock ticker
            as_of_date: Query date (YYYY-MM-DD)

        Returns:
            Closing price or None if not found
        """
        # Stub: Would look up date
        return None

    @staticmethod
    def bulk_get_prices(
        tickers: list[str],
        as_of_date: str,
    ) -> dict[str, float | None]:
        """
        Get prices for multiple tickers on same date.

        Useful for peer analysis and index calculations.

        Args:
            tickers: List of stock tickers
            as_of_date: Query date (YYYY-MM-DD)

        Returns:
            Dict mapping ticker → price (or None)
        """
        # Stub: Would query batch
        return {ticker: None for ticker in tickers}

    @staticmethod
    def get_index_constituents(
        index_name: str,
        as_of_date: str,
    ) -> list[str]:
        """
        Get index constituents at a point in time.

        Useful for peer benchmarking and survivor bias analysis.

        Args:
            index_name: Index name (e.g., "SP500", "NASDAQ100")
            as_of_date: Query date (YYYY-MM-DD)

        Returns:
            List of tickers in index at that date
        """
        # Stub: Would query historical index composition
        return []

    @staticmethod
    def data_availability_check(
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> dict[str, bool]:
        """
        Check what market data is available for a ticker/period.

        Returns:
            Dict with data type → availability flags
        """
        return {
            "price_data": False,
            "market_cap_data": False,
            "enterprise_value_data": False,
        }
