"""Tests for fundamental backtest engine."""

import pytest

from accountant.research.backtest_engine import (
    BacktestPeriodType,
    BacktestResults,
    BacktestReturn,
    FundamentalBacktestEngine,
    ResearchFactor,
)


class TestBacktestReturn:
    def test_backtest_return_creation(self):
        ret = BacktestReturn(
            period_name="IN_SAMPLE",
            start_date="2020-01-01",
            end_date="2024-12-31",
            factor_name="HIGH_ROIC",
            cohort_size=50,
            avg_total_return_pct=12.5,
            avg_owner_earnings_growth_pct=8.0,
            avg_roic_change_bps=150,
            min_return_pct=-5.0,
            max_return_pct=45.0,
            volatility_pct=15.0,
            max_drawdown_pct=-25.0,
            sharpe_ratio=0.83,
            information_ratio=0.65,
            avg_peer_return_pct=10.0,
            alpha_vs_peers_pct=2.5,
            companies_delisted=0,
            companies_acquired=2,
            companies_bankruptcy_filed=0,
            factor_predictive_power=0.72,
        )
        assert ret.cohort_size == 50
        assert ret.avg_total_return_pct == 12.5
        assert ret.factor_predictive_power == 0.72

    def test_backtest_return_immutable(self):
        ret = BacktestReturn(
            period_name="TEST",
            start_date="2020-01-01",
            end_date="2024-12-31",
            factor_name="TEST_FACTOR",
            cohort_size=25,
            avg_total_return_pct=10.0,
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
        with pytest.raises(AttributeError):
            ret.cohort_size = 30  # type: ignore


class TestBacktestResults:
    def test_backtest_results_creation(self):
        results = BacktestResults(
            factor_name="HIGH_ROIC",
            factor_version="V1",
            in_sample_return=None,
            validation_return=None,
            out_of_sample_return=None,
            rolling_returns=[],
            total_backtest_years=5.0,
            avg_cohort_size=50,
            total_companies_tested=100,
            avg_annual_return_pct=12.5,
            total_return_pct=75.0,
            volatility_pct=15.0,
            sharpe_ratio=0.83,
            success_rate_pct=80.0,
            hit_rate_pct=65.0,
            predictive_power_score=0.72,
            warnings=[],
            notes="Backtest complete",
        )
        assert results.factor_name == "HIGH_ROIC"
        assert results.avg_annual_return_pct == 12.5
        assert results.predictive_power_score == 0.72

    def test_backtest_results_immutable(self):
        results = BacktestResults(
            factor_name="TEST",
            factor_version="V1",
            in_sample_return=None,
            validation_return=None,
            out_of_sample_return=None,
            rolling_returns=[],
            total_backtest_years=0.0,
            avg_cohort_size=0,
            total_companies_tested=10,
            avg_annual_return_pct=None,
            total_return_pct=None,
            volatility_pct=None,
            sharpe_ratio=None,
            success_rate_pct=None,
            hit_rate_pct=None,
            predictive_power_score=None,
            warnings=[],
            notes="",
        )
        with pytest.raises(AttributeError):
            results.factor_name = "OTHER"  # type: ignore


class TestResearchFactor:
    def test_all_research_factors_exist(self):
        factors = [
            ResearchFactor.HIGH_ROIC,
            ResearchFactor.HIGH_OE_YIELD,
            ResearchFactor.QUALITY_PLUS_VALUE,
            ResearchFactor.OWNER_EARNINGS_GROWTH,
            ResearchFactor.SAFE_BALANCE_SHEET,
            ResearchFactor.CAPITAL_COMPOUNDER,
            ResearchFactor.SHAREHOLDER_FRIENDLY,
            ResearchFactor.ACCOUNTING_QUALITY,
            ResearchFactor.PEERS_OUTPERFORMER,
            ResearchFactor.RESEARCH_WATCHLIST,
        ]
        assert len(factors) == 10

    def test_factor_values(self):
        assert ResearchFactor.HIGH_ROIC.value == "HIGH_ROIC"
        assert ResearchFactor.ACCOUNTING_QUALITY.value == "ACCOUNTING_QUALITY"


class TestFundamentalBacktestEngine:
    def test_build_cohort_at_date(self):
        cohort = FundamentalBacktestEngine.build_cohort_at_date(
            companies=["AAPL", "MSFT", "GOOG", "AMZN"],
            as_of_date="2024-01-01",
            factor=ResearchFactor.HIGH_ROIC,
        )
        assert isinstance(cohort, list)

    def test_calculate_cohort_returns_basic(self):
        ret = FundamentalBacktestEngine.calculate_cohort_returns(
            cohort=["AAPL", "MSFT"],
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
        assert ret.cohort_size == 2
        assert ret.start_date == "2024-01-01"
        assert ret.end_date == "2024-12-31"

    def test_run_walk_forward_backtest(self):
        results = FundamentalBacktestEngine.run_walk_forward_backtest(
            companies=["AAPL", "MSFT", "GOOG"],
            factor=ResearchFactor.QUALITY_PLUS_VALUE,
            start_date="2020-01-01",
            end_date="2024-12-31",
            in_sample_years=3,
            validation_years=1,
            out_of_sample_years=1,
        )
        assert results.factor_name == "QUALITY_PLUS_VALUE"
        assert results.total_companies_tested == 3
        assert isinstance(results.rolling_returns, list)

    def test_analyze_factor_persistence(self):
        results = BacktestResults(
            factor_name="HIGH_ROIC",
            factor_version="V1",
            in_sample_return=None,
            validation_return=None,
            out_of_sample_return=None,
            rolling_returns=[],
            total_backtest_years=5.0,
            avg_cohort_size=50,
            total_companies_tested=100,
            avg_annual_return_pct=12.5,
            total_return_pct=None,
            volatility_pct=None,
            sharpe_ratio=None,
            success_rate_pct=None,
            hit_rate_pct=None,
            predictive_power_score=None,
            warnings=[],
            notes="",
        )
        analysis = FundamentalBacktestEngine.analyze_factor_persistence(results)
        assert isinstance(analysis, dict)

    def test_detect_lookahead_bias(self):
        warnings = FundamentalBacktestEngine.detect_lookahead_bias(
            cohort_formation_dates=["2024-01-15"],
            financial_filing_dates=["2024-02-15"],
            price_update_dates=["2024-01-16"],
        )
        assert isinstance(warnings, list)

    def test_backtest_period_types(self):
        assert BacktestPeriodType.IN_SAMPLE == "IN_SAMPLE"
        assert BacktestPeriodType.VALIDATION == "VALIDATION"
        assert BacktestPeriodType.OUT_OF_SAMPLE == "OUT_OF_SAMPLE"
        assert BacktestPeriodType.ROLLING == "ROLLING"
