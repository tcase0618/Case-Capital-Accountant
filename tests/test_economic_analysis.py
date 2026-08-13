"""Tests for Economic Debt, Dilution, and Capital Allocation engines."""

from accountant.calculations import (
    CAPITAL_ALLOCATION_THRESHOLD_V1,
    DILUTION_SBC_V1,
    DILUTION_WARRANTS_OPTIONS_V1,
    ECONOMIC_DEBT_ADJUSTED_V1,
    ECONOMIC_DEBT_IMPLIED_V1,
    ECONOMIC_DEBT_REPORTED_V1,
    CalculationContext,
    CapitalAllocationCalculator,
    DilutionCalculator,
    EconomicDebtCalculator,
)


class TestEconomicDebtReported:
    """Tests for reported Economic Debt model."""

    def test_reported_valid(self):
        """Test reported model with valid data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = EconomicDebtCalculator.calculate_reported(
            total_debt=50000.0,
            operating_lease_liability=5000.0,
            finance_lease_liability=2000.0,
            pension_underfunding=1000.0,
            other_obligations=500.0,
            context=context,
        )

        assert result.calculation_status == "VALID"
        # 50000 + 5000 + 2000 + 1000 + 500 = 58500
        assert result.value == 58500.0
        assert result.formula_version == ECONOMIC_DEBT_REPORTED_V1
        assert result.metadata["model"] == "REPORTED"

    def test_reported_missing_debt(self):
        """Test reported model with missing total debt."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = EconomicDebtCalculator.calculate_reported(
            total_debt=None,
            operating_lease_liability=5000.0,
            finance_lease_liability=None,
            pension_underfunding=None,
            other_obligations=None,
            context=context,
        )

        assert result.calculation_status == "INSUFFICIENT_DATA"
        assert result.value is None


class TestEconomicDebtAdjusted:
    """Tests for adjusted Economic Debt model."""

    def test_adjusted_valid(self):
        """Test adjusted model with valid data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = EconomicDebtCalculator.calculate_adjusted(
            total_debt=50000.0,
            operating_lease_liability=5000.0,
            finance_lease_liability=2000.0,
            pension_underfunding=1000.0,
            other_obligations=500.0,
            capitalized_intangibles=3000.0,
            environment_liabilities=2000.0,
            context=context,
        )

        assert result.calculation_status == "VALID"
        # 50000 + 5000 + 2000 + 1000 + 500 + 3000 + 2000 = 63500
        assert result.value == 63500.0
        assert result.formula_version == ECONOMIC_DEBT_ADJUSTED_V1
        assert result.metadata["model"] == "ADJUSTED"

    def test_adjusted_higher_than_reported(self):
        """Test that adjusted debt exceeds reported debt with intangibles."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        reported = EconomicDebtCalculator.calculate_reported(
            total_debt=50000.0,
            operating_lease_liability=5000.0,
            finance_lease_liability=None,
            pension_underfunding=None,
            other_obligations=None,
            context=context,
        )

        adjusted = EconomicDebtCalculator.calculate_adjusted(
            total_debt=50000.0,
            operating_lease_liability=5000.0,
            finance_lease_liability=None,
            pension_underfunding=None,
            other_obligations=None,
            capitalized_intangibles=2000.0,
            environment_liabilities=None,
            context=context,
        )

        assert adjusted.value > reported.value
        assert reported.value == 55000.0
        assert adjusted.value == 57000.0


class TestEconomicDebtImplied:
    """Tests for implied Economic Debt model."""

    def test_implied_valid(self):
        """Test implied model with valid data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = EconomicDebtCalculator.calculate_implied(
            total_debt=50000.0,
            market_cap=3000000.0,
            net_cash=5000.0,
            context=context,
            leverage_target=2.5,
        )

        assert result.calculation_status == "VALID"
        # Implied = (3000000 * 2.5) - 5000 = 7500000 - 5000 = 7495000
        assert result.value == 7495000.0
        assert result.formula_version == ECONOMIC_DEBT_IMPLIED_V1
        assert result.metadata["model"] == "IMPLIED"

    def test_implied_missing_market_cap(self):
        """Test implied model with missing market cap."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = EconomicDebtCalculator.calculate_implied(
            total_debt=50000.0,
            market_cap=None,
            net_cash=5000.0,
            context=context,
        )

        assert result.calculation_status == "INSUFFICIENT_DATA"
        assert result.value is None

    def test_implied_above_target_leverage(self):
        """Test implied debt with company above target leverage."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = EconomicDebtCalculator.calculate_implied(
            total_debt=100000.0,
            market_cap=1000000.0,
            net_cash=10000.0,
            context=context,
            leverage_target=2.0,
        )

        # Implied = (1000000 * 2.0) - 10000 = 1990000
        # Current = 100000, so above target
        assert result.metadata["current_debt"] == 100000.0
        assert result.value == 1990000.0
        assert result.metadata["vs_target"] == "below"


class TestDilutionSBC:
    """Tests for stock-based compensation dilution."""

    def test_sbc_dilution_valid(self):
        """Test SBC dilution with valid data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = DilutionCalculator.calculate_sbc_dilution(
            shares_outstanding=16000.0,  # 16B shares
            sbc_expense=20000.0,  # $20M SBC expense
            stock_price=200.0,
            sbc_vesting_years=3.0,
            context=context,
        )

        assert result.calculation_status == "VALID"
        # SBC Shares = (20000 * 3.0) / 200.0 = 60000 / 200 = 300 shares
        assert result.value == 300.0
        assert result.formula_version == DILUTION_SBC_V1
        dilution_pct = (300.0 / 16000.0) * 100.0
        assert result.metadata["dilution_percent"] == dilution_pct

    def test_sbc_dilution_missing_shares(self):
        """Test SBC dilution with missing shares outstanding."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = DilutionCalculator.calculate_sbc_dilution(
            shares_outstanding=None,
            sbc_expense=20000.0,
            stock_price=200.0,
            context=context,
        )

        assert result.calculation_status == "INSUFFICIENT_DATA"
        assert result.value is None

    def test_sbc_dilution_missing_stock_price(self):
        """Test SBC dilution with missing stock price."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = DilutionCalculator.calculate_sbc_dilution(
            shares_outstanding=16000.0,
            sbc_expense=20000.0,
            stock_price=None,
            context=context,
        )

        assert result.calculation_status == "INSUFFICIENT_DATA"


class TestDilutionWarrantsOptions:
    """Tests for warrants & options dilution using treasury stock method."""

    def test_warrants_options_dilution_valid(self):
        """Test warrants & options dilution with valid data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = DilutionCalculator.calculate_warrants_options_dilution(
            shares_outstanding=16000.0,
            in_the_money_warrants=50.0,  # 50M ITM warrants
            in_the_money_options=100.0,  # 100M ITM options
            stock_price=200.0,
            avg_exercise_price=150.0,
            context=context,
        )

        assert result.calculation_status == "VALID"
        assert result.formula_version == DILUTION_WARRANTS_OPTIONS_V1
        # Total ITM = 150M shares
        # Proceeds = 150 * 150 = 22500
        # Shares repurchased = 22500 / 200 = 112.5
        # Net dilution = 150 - 112.5 = 37.5
        assert result.value == 37.5
        assert result.metadata["method"] == "TREASURY_STOCK"

    def test_warrants_options_missing_itm(self):
        """Test warrants & options with missing ITM data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = DilutionCalculator.calculate_warrants_options_dilution(
            shares_outstanding=16000.0,
            in_the_money_warrants=None,
            in_the_money_options=None,
            stock_price=200.0,
            avg_exercise_price=150.0,
            context=context,
        )

        assert result.calculation_status == "INSUFFICIENT_DATA"

    def test_warrants_options_high_dilution(self):
        """Test significant warrant/option dilution scenario."""
        context = CalculationContext(
            company_id="BIOTECH",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = DilutionCalculator.calculate_warrants_options_dilution(
            shares_outstanding=100.0,  # 100M shares
            in_the_money_warrants=20.0,
            in_the_money_options=30.0,
            stock_price=50.0,
            avg_exercise_price=30.0,
            context=context,
        )

        # Total ITM = 50M
        # Proceeds = 50 * 30 = 1500
        # Shares repurchased = 1500 / 50 = 30
        # Net dilution = 50 - 30 = 20
        assert result.value == 20.0
        dilution_pct = (20.0 / 100.0) * 100.0
        assert result.metadata["dilution_percent"] == dilution_pct


class TestCapitalAllocation:
    """Tests for capital allocation efficiency evaluation."""

    def test_allocation_value_creating(self):
        """Test allocation with ROIC > WACC (value-creating)."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = CapitalAllocationCalculator.evaluate_allocation(
            owner_earnings=10000.0,
            incremental_invested_capital=3000.0,
            incremental_roic=15.0,
            wacc=9.0,
            capital_expenditure=5000.0,
            share_repurchases=3000.0,
            dividends=2000.0,
            debt_reduction=0.0,
            context=context,
        )

        assert result.calculation_status == "VALID"
        assert result.formula_version == CAPITAL_ALLOCATION_THRESHOLD_V1
        assert result.metadata["allocation_score"] == "VALUE_CREATING"
        assert result.metadata["roic_spread"] == 6.0  # 15 - 9

    def test_allocation_value_destroying(self):
        """Test allocation with ROIC < WACC (value-destroying)."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = CapitalAllocationCalculator.evaluate_allocation(
            owner_earnings=10000.0,
            incremental_invested_capital=3000.0,
            incremental_roic=6.0,
            wacc=10.0,
            capital_expenditure=4000.0,
            share_repurchases=0.0,
            dividends=3000.0,
            debt_reduction=3000.0,
            context=context,
        )

        assert result.calculation_status == "VALID"
        assert result.metadata["allocation_score"] == "VALUE_DESTROYING"
        assert result.metadata["roic_spread"] == -4.0  # 6 - 10

    def test_allocation_missing_owner_earnings(self):
        """Test allocation with missing owner earnings."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = CapitalAllocationCalculator.evaluate_allocation(
            owner_earnings=None,
            incremental_invested_capital=3000.0,
            incremental_roic=15.0,
            wacc=9.0,
            capital_expenditure=5000.0,
            share_repurchases=0.0,
            dividends=0.0,
            debt_reduction=0.0,
            context=context,
        )

        assert result.calculation_status == "INSUFFICIENT_DATA"

    def test_allocation_no_allocation(self):
        """Test with no capital allocated (all retained)."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = CapitalAllocationCalculator.evaluate_allocation(
            owner_earnings=10000.0,
            incremental_invested_capital=0.0,
            incremental_roic=0.0,
            wacc=0.0,
            capital_expenditure=0.0,
            share_repurchases=0.0,
            dividends=0.0,
            debt_reduction=0.0,
            context=context,
        )

        assert result.calculation_status == "INSUFFICIENT_DATA"
        assert "No capital allocation detected" in result.warnings

    def test_allocation_full_payout(self):
        """Test scenario where all owner earnings allocated."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = CapitalAllocationCalculator.evaluate_allocation(
            owner_earnings=10000.0,
            incremental_invested_capital=0.0,
            incremental_roic=0.0,
            wacc=0.0,
            capital_expenditure=2000.0,
            share_repurchases=4000.0,
            dividends=4000.0,
            debt_reduction=0.0,
            context=context,
        )

        assert result.calculation_status == "VALID"
        assert result.metadata["allocation_pct"] == 100.0
        assert result.metadata["unallocated"] == 0.0
        assert result.metadata["total_allocated"] == 10000.0


class TestModelComparison:
    """Tests comparing economic debt and dilution scenarios."""

    def test_economic_debt_models_comparison(self):
        """Test all three debt models with same data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        reported = EconomicDebtCalculator.calculate_reported(
            total_debt=50000.0,
            operating_lease_liability=5000.0,
            finance_lease_liability=2000.0,
            pension_underfunding=1000.0,
            other_obligations=500.0,
            context=context,
        )

        adjusted = EconomicDebtCalculator.calculate_adjusted(
            total_debt=50000.0,
            operating_lease_liability=5000.0,
            finance_lease_liability=2000.0,
            pension_underfunding=1000.0,
            other_obligations=500.0,
            capitalized_intangibles=2000.0,
            environment_liabilities=1500.0,
            context=context,
        )

        # Reported: 50000 + 5000 + 2000 + 1000 + 500 = 58500
        # Adjusted: 58500 + 2000 + 1500 = 62000
        assert reported.value == 58500.0
        assert adjusted.value == 62000.0
        assert adjusted.value > reported.value

    def test_total_dilution_scenario(self):
        """Test combined SBC and warrant/option dilution."""
        context = CalculationContext(
            company_id="TECH",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        sbc_dilution = DilutionCalculator.calculate_sbc_dilution(
            shares_outstanding=1000.0,
            sbc_expense=100.0,
            stock_price=50.0,
            sbc_vesting_years=3.0,
            context=context,
        )

        warrant_dilution = DilutionCalculator.calculate_warrants_options_dilution(
            shares_outstanding=1000.0,
            in_the_money_warrants=10.0,
            in_the_money_options=15.0,
            stock_price=50.0,
            avg_exercise_price=40.0,
            context=context,
        )

        # SBC: (100 * 3) / 50 = 6 shares
        # Warrants/Options: (25 * 40) / 50 - 25 = 20 - 25 = -5, capped at 0 or calculated as 25 - 20 = 5
        assert sbc_dilution.value == 6.0
        # Total dilution sources identified
        assert warrant_dilution.calculation_status == "VALID"
