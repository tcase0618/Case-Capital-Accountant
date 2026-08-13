"""Point-in-time safe fundamental research backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class BacktestPeriodType(StrEnum):
    """Period type for backtesting."""

    IN_SAMPLE = "IN_SAMPLE"  # Training period
    VALIDATION = "VALIDATION"  # Validation period
    OUT_OF_SAMPLE = "OUT_OF_SAMPLE"  # Test period
    ROLLING = "ROLLING"  # Rolling window


class ResearchFactor(StrEnum):
    """Fundamental research factors for backtesting (NOT trading signals)."""

    HIGH_ROIC = "HIGH_ROIC"  # Strong return on capital
    HIGH_OE_YIELD = "HIGH_OE_YIELD"  # High owner earnings yield
    QUALITY_PLUS_VALUE = "QUALITY_PLUS_VALUE"  # Quality + attractive valuation
    OWNER_EARNINGS_GROWTH = "OWNER_EARNINGS_GROWTH"  # Strong earnings growth
    SAFE_BALANCE_SHEET = "SAFE_BALANCE_SHEET"  # Low leverage, strong credit
    CAPITAL_COMPOUNDER = "CAPITAL_COMPOUNDER"  # Strong incremental ROIC
    SHAREHOLDER_FRIENDLY = "SHAREHOLDER_FRIENDLY"  # Rational capital allocation
    ACCOUNTING_QUALITY = "ACCOUNTING_QUALITY"  # High quality financials
    PEERS_OUTPERFORMER = "PEERS_OUTPERFORMER"  # Top quartile vs peers
    RESEARCH_WATCHLIST = "RESEARCH_WATCHLIST"  # Monitor for future thesis


@dataclass(frozen=True)
class BacktestReturn:
    """Return metrics for a backtest cohort."""

    period_name: str
    start_date: str
    end_date: str
    factor_name: str
    cohort_size: int

    # Return metrics (NOT trading returns; research outcome tracking)
    # These show whether the research classification was predictive
    avg_total_return_pct: float | None  # Price + dividend return
    avg_owner_earnings_growth_pct: float | None  # Did selected companies grow earnings?
    avg_roic_change_bps: float | None  # Did ROIC improve?
    min_return_pct: float | None
    max_return_pct: float | None
    volatility_pct: float | None

    # Risk metrics
    max_drawdown_pct: float | None
    sharpe_ratio: float | None
    information_ratio: float | None

    # Peer comparison
    avg_peer_return_pct: float | None  # Benchmark return
    alpha_vs_peers_pct: float | None

    # Survivorship
    companies_delisted: int
    companies_acquired: int
    companies_bankruptcy_filed: int

    # Quality of research factor
    factor_predictive_power: float | None  # 0-1 correlation to future metrics


@dataclass(frozen=True)
class BacktestResults:
    """Complete backtest results for a research factor."""

    factor_name: str
    factor_version: str

    # Period results
    in_sample_return: BacktestReturn | None
    validation_return: BacktestReturn | None
    out_of_sample_return: BacktestReturn | None
    rolling_returns: list[BacktestReturn]

    # Summary statistics
    total_backtest_years: float
    avg_cohort_size: int
    total_companies_tested: int
    avg_annual_return_pct: float | None
    total_return_pct: float | None
    volatility_pct: float | None
    sharpe_ratio: float | None

    # Factor analysis
    success_rate_pct: float | None  # % years positive return
    hit_rate_pct: float | None  # % cohort members outperformed peers
    predictive_power_score: float | None  # How predictive was the factor?

    # Warnings
    warnings: list[str]
    notes: str


class FundamentalBacktestEngine:
    """
    Run point-in-time safe backtests on fundamental research factors.

    CRITICAL: All backtests use point-in-time data only (no lookahead bias).
    - For each historical date, only use data available AT that date
    - No future amendments to financial statements
    - No future price data
    - No future peer data
    - Must use original filing versions (not later restatements)
    """

    @staticmethod
    def build_cohort_at_date(
        companies: list[str],
        as_of_date: str,
        factor: ResearchFactor,
    ) -> list[str]:
        """
        Build cohort of companies matching factor at point in time.

        Uses only information available at as_of_date.
        No lookahead bias protection—implementation depends on
        PointInTimeResolver integration.

        Args:
            companies: Universe of companies to evaluate
            as_of_date: Evaluation date (YYYY-MM-DD)
            factor: Research factor to apply

        Returns:
            List of company_ids passing factor at that date
        """
        # Stub: Would query point-in-time data to classify each company
        return []

    @staticmethod
    def calculate_returns(
        price_start: float,
        price_end: float,
        dividends: float = 0.0,
    ) -> float:
        """Calculate total return including dividends."""
        if price_start <= 0:
            return 0.0
        return ((price_end - price_start + dividends) / price_start) * 100.0

    @staticmethod
    def calculate_cagr(
        start_value: float,
        end_value: float,
        years: float,
    ) -> float | None:
        """Calculate compound annual growth rate."""
        if start_value <= 0 or years <= 0:
            return None
        return (((end_value / start_value) ** (1.0 / years)) - 1.0) * 100.0

    @staticmethod
    def calculate_volatility(returns: list[float]) -> float | None:
        """Calculate annualized volatility from daily/monthly returns."""
        if not returns or len(returns) < 2:
            return None
        import statistics

        variance = statistics.variance(returns)
        daily_volatility = variance ** 0.5
        return daily_volatility * (252.0 ** 0.5) * 100.0

    @staticmethod
    def calculate_sharpe_ratio(
        returns: list[float],
        risk_free_rate: float = 2.0,
    ) -> float | None:
        """Calculate Sharpe ratio (annualized return / annualized volatility)."""
        if not returns or len(returns) < 2:
            return None
        volatility = FundamentalBacktestEngine.calculate_volatility(returns)
        if volatility is None or volatility == 0:
            return None
        avg_return = sum(returns) / len(returns)
        return (avg_return - risk_free_rate) / volatility

    @staticmethod
    def calculate_sortino_ratio(
        returns: list[float],
        risk_free_rate: float = 2.0,
    ) -> float | None:
        """Calculate Sortino ratio (downside deviation only)."""
        if not returns or len(returns) < 2:
            return None
        import statistics

        downside_returns = [r for r in returns if r < risk_free_rate]
        if not downside_returns:
            return None
        downside_variance = statistics.variance([max(r - risk_free_rate, 0) for r in returns])
        downside_deviation = (downside_variance ** 0.5) * (252.0 ** 0.5) * 100.0
        if downside_deviation == 0:
            return None
        avg_return = sum(returns) / len(returns)
        return (avg_return - risk_free_rate) / downside_deviation

    @staticmethod
    def calculate_max_drawdown(prices: list[float]) -> float | None:
        """Calculate maximum drawdown from price series."""
        if not prices or len(prices) < 2:
            return None
        max_price = prices[0]
        max_dd = 0.0
        for price in prices[1:]:
            if price > max_price:
                max_price = price
            drawdown = ((max_price - price) / max_price) * 100.0
            if drawdown > max_dd:
                max_dd = drawdown
        return max_dd if max_dd > 0 else 0.0

    @staticmethod
    def calculate_hit_rate(outcomes: list[bool]) -> float | None:
        """Calculate percentage of positive outcomes."""
        if not outcomes:
            return None
        hits = sum(1 for o in outcomes if o)
        return (hits / len(outcomes)) * 100.0

    @staticmethod
    def calculate_turnover(
        cohort_initial_size: int,
        cohort_final_size: int,
    ) -> float | None:
        """Calculate portfolio turnover rate."""
        if cohort_initial_size <= 0:
            return None
        # Assumes all changes are turnover (simplified)
        return (abs(cohort_final_size - cohort_initial_size) / cohort_initial_size) * 100.0

    @staticmethod
    def calculate_excess_return(
        portfolio_return: float,
        benchmark_return: float,
    ) -> float:
        """Calculate excess return vs benchmark (alpha)."""
        return portfolio_return - benchmark_return

    @staticmethod
    def calculate_rolling_returns(
        prices: list[float],
        window_days: int = 252,
    ) -> list[float]:
        """Calculate rolling period returns."""
        if len(prices) < window_days:
            return []
        returns = []
        for i in range(len(prices) - window_days):
            ret = ((prices[i + window_days] - prices[i]) / prices[i]) * 100.0
            returns.append(ret)
        return returns

    @staticmethod
    def calculate_cohort_returns(
        cohort: list[str],
        start_date: str,
        end_date: str,
        include_dividends: bool = True,
    ) -> BacktestReturn:
        """
        Calculate returns for cohort during period.

        Note: start_date is formation date (must use prices AFTER
        this date for consistency). End date is measurement date.

        Args:
            cohort: Companies in cohort
            start_date: Cohort formation date
            end_date: Return measurement end date
            include_dividends: Include dividend income in return

        Returns:
            BacktestReturn with performance metrics
        """
        # Stub: Would calculate actual returns, volatility, etc.
        return BacktestReturn(
            period_name="",
            start_date=start_date,
            end_date=end_date,
            factor_name="",
            cohort_size=len(cohort),
            avg_total_return_pct=None,
            avg_owner_earnings_growth_pct=None,
            avg_roic_change_bps=None,
            min_return_pct=None,
            max_return_pct=None,
            volatility_pct=None,
            max_drawdown_pct=None,
            sharpe_ratio=None,
            information_ratio=None,
            avg_peer_return_pct=None,
            alpha_vs_peers_pct=None,
            companies_delisted=0,
            companies_acquired=0,
            companies_bankruptcy_filed=0,
            factor_predictive_power=None,
        )

    @staticmethod
    def run_walk_forward_backtest(
        companies: list[str],
        factor: ResearchFactor,
        start_date: str,  # YYYY-MM-DD
        end_date: str,  # YYYY-MM-DD
        rebalance_frequency: str = "ANNUAL",  # ANNUAL, SEMI_ANNUAL, QUARTERLY
        in_sample_years: int = 5,
        validation_years: int = 1,
        out_of_sample_years: int = 3,
    ) -> BacktestResults:
        """
        Run walk-forward backtest: train-validate-test-repeat.

        Protocol:
        1. Split data into non-overlapping periods
        2. In-sample: Define factor rules using only training data
        3. Validation: Test factor on validation period (no re-optimization)
        4. Out-of-sample: Test factor on holdout period (no re-optimization)
        5. Repeat with rolling windows

        CRITICAL: Each cohort formation uses point-in-time data ONLY.

        Args:
            companies: Universe of companies to test
            factor: Research factor to backtest
            start_date: Backtest start date
            end_date: Backtest end date
            rebalance_frequency: How often to reform cohorts
            in_sample_years: Training period length
            validation_years: Validation period length
            out_of_sample_years: Test period length

        Returns:
            BacktestResults with all periods and summary statistics
        """
        # Stub implementation
        return BacktestResults(
            factor_name=factor.value,
            factor_version="V1",
            in_sample_return=None,
            validation_return=None,
            out_of_sample_return=None,
            rolling_returns=[],
            total_backtest_years=0.0,
            avg_cohort_size=0,
            total_companies_tested=len(companies),
            avg_annual_return_pct=None,
            total_return_pct=None,
            volatility_pct=None,
            sharpe_ratio=None,
            success_rate_pct=None,
            hit_rate_pct=None,
            predictive_power_score=None,
            warnings=["Implementation pending"],
            notes="Stub implementation",
        )

    @staticmethod
    def analyze_factor_persistence(
        results: BacktestResults,
    ) -> dict[str, float | str]:
        """
        Analyze whether factor persists across time periods.

        Returns metrics indicating:
        - Is out-of-sample performance similar to in-sample?
        - Does factor show consistent predictive power?
        - Are there regime changes (periods when factor breaks)?

        Args:
            results: BacktestResults from walk-forward test

        Returns:
            Dict with persistence metrics
        """
        return {
            "out_of_sample_vs_in_sample_ratio": None,
            "consistency_score": None,
            "regime_changes_detected": False,
            "notes": "Stub implementation",
        }

    @staticmethod
    def detect_lookahead_bias(
        cohort_formation_dates: list[str],
        financial_filing_dates: list[str],
        price_update_dates: list[str],
    ) -> list[str]:
        """
        Detect potential lookahead bias in backtest.

        Returns warnings if:
        - Cohort formation uses data from later filings
        - Prices used before data was publicly available
        - Amendments used instead of original filings

        Args:
            cohort_formation_dates: When cohorts were formed
            financial_filing_dates: When data became available
            price_update_dates: When prices were observable

        Returns:
            List of bias warnings (empty if no issues detected)
        """
        warnings = []

        # Stub: Real implementation would check exact timestamps
        # for each cohort to ensure no lookahead

        return warnings
