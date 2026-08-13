"""Tests for Owner Earnings and Maintenance CAPEX calculation engines."""

from accountant.calculations import (
    MAINTENANCE_CAPEX_DA_ANCHOR_V1,
    MAINTENANCE_CAPEX_GROWTH_SEPARATION_V1,
    MAINTENANCE_CAPEX_HISTORICAL_RATIO_V1,
    MAINTENANCE_CAPEX_RANGE_V1,
    OWNER_EARNINGS_CFO_V1,
    OWNER_EARNINGS_CONSERVATIVE_V1,
    OWNER_EARNINGS_MAINT_CAPEX_V1,
    CalculationContext,
    MaintenanceCapexEstimator,
    OwnerEarningsCalculator,
)
from accountant.financial.statement_builder import (
    IncomeStatementData,
    StatementLineData,
)


class TestMaintenanceCapexDAnchor:
    """Tests for D&A anchor method."""

    def test_da_anchor_valid(self):
        """Test D&A anchor with valid data."""
        # Create mock income statement with D&A
        stmt = IncomeStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date="2024-01-01",
            end_date="2024-12-31",
            lines={
                "CC_DEPRECIATION_AMORTIZATION": StatementLineData(
                    canonical_concept="CC_DEPRECIATION_AMORTIZATION",
                    value_numeric=1000.0,
                    value_text=None,
                    unit="USD",
                    reported_or_derived="reported",
                    derivation_formula=None,
                    mapping_confidence="HIGH",
                    selection_status="SELECTED",
                    warnings=[],
                ),
            },
            source_accessions=[],
            quality_status="GOOD",
            completeness=0.8,
        )

        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = MaintenanceCapexEstimator.estimate_da_anchor(
            stmt, context, da_multiple_low=0.9, da_multiple_base=1.0, da_multiple_high=1.1
        )

        assert result.calculation_status == "VALID"
        assert result.value == 1000.0
        assert result.metadata["low"] == 900.0
        assert result.metadata["high"] == 1100.0
        assert result.formula_version == MAINTENANCE_CAPEX_DA_ANCHOR_V1

    def test_da_anchor_missing_da(self):
        """Test D&A anchor with missing D&A."""
        stmt = IncomeStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date="2024-01-01",
            end_date="2024-12-31",
            lines={},
            source_accessions=[],
            quality_status="GOOD",
            completeness=0.8,
        )

        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = MaintenanceCapexEstimator.estimate_da_anchor(stmt, context)

        assert result.calculation_status == "INSUFFICIENT_DATA"
        assert result.value is None


class TestMaintenanceCapexHistoricalRatio:
    """Tests for historical CAPEX/PPE ratio method."""

    def test_historical_ratio_valid(self):
        """Test historical ratio with valid data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = MaintenanceCapexEstimator.estimate_historical_ratio(
            current_year_capex=1000.0, current_year_ppe=10000.0, context=context
        )

        assert result.calculation_status == "VALID"
        assert result.value == 650.0  # Base case 65% of CAPEX
        assert result.metadata["method"] == "HISTORICAL_RATIO"
        assert result.formula_version == MAINTENANCE_CAPEX_HISTORICAL_RATIO_V1

    def test_historical_ratio_missing_ppe(self):
        """Test historical ratio with missing PPE."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = MaintenanceCapexEstimator.estimate_historical_ratio(
            current_year_capex=1000.0, current_year_ppe=None, context=context
        )

        assert result.calculation_status == "INSUFFICIENT_DATA"


class TestMaintenanceCapexGrowthSeparation:
    """Tests for growth CAPEX separation method."""

    def test_growth_separation_valid(self):
        """Test growth separation with valid data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        # PPE grew $2000, CAPEX was $1500, revenue growth 10%
        result = MaintenanceCapexEstimator.estimate_growth_separation(
            current_year_capex=1500.0,
            prior_year_ppe=10000.0,
            current_year_ppe=12000.0,
            revenue_growth_rate=10.0,
            context=context,
        )

        assert result.calculation_status == "VALID"
        assert result.formula_version == MAINTENANCE_CAPEX_GROWTH_SEPARATION_V1
        # Growth CAPEX ≈ 2000 * 0.10 = 200, Maint CAPEX ≈ 1500 - 200 = 1300
        assert result.value == 1300.0

    def test_growth_separation_missing_data(self):
        """Test growth separation with missing CAPEX."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = MaintenanceCapexEstimator.estimate_growth_separation(
            current_year_capex=None,
            prior_year_ppe=10000.0,
            current_year_ppe=12000.0,
            revenue_growth_rate=10.0,
            context=context,
        )

        assert result.calculation_status == "INSUFFICIENT_DATA"


class TestMaintenanceCapexRange:
    """Tests for historical range method."""

    def test_range_valid(self):
        """Test range method with valid multi-year history."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        # 3 years of CAPEX and revenue
        capex_history = [500.0, 600.0, 700.0]
        revenue_history = [10000.0, 11000.0, 12000.0]

        result = MaintenanceCapexEstimator.estimate_range(
            capex_history, revenue_history, context
        )

        assert result.calculation_status == "VALID"
        assert result.formula_version == MAINTENANCE_CAPEX_RANGE_V1
        # CAPEX/Revenue ratios: 0.05, 0.0545, 0.0583
        # Average: ~0.0542
        # Current revenue 12000 * 0.0542 ≈ 650.4
        assert result.value > 0

    def test_range_insufficient_data(self):
        """Test range method with empty history."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = MaintenanceCapexEstimator.estimate_range([], [], context)

        assert result.calculation_status == "INSUFFICIENT_DATA"


class TestOwnerEarningsConservative:
    """Tests for conservative Owner Earnings model."""

    def test_conservative_valid(self):
        """Test conservative model with valid data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = OwnerEarningsCalculator.calculate_conservative(
            net_income=5000.0,
            noncash_charges=500.0,
            total_capex=1000.0,
            required_working_capital_investment=200.0,
            context=context,
            recurring_economic_adjustments=100.0,
        )

        assert result.calculation_status == "VALID"
        assert result.value == 4200.0  # 5000 + 500 - 1000 - 200 - 100
        assert result.formula_version == OWNER_EARNINGS_CONSERVATIVE_V1
        assert result.metadata["model"] == "CONSERVATIVE"

    def test_conservative_missing_ni(self):
        """Test conservative model with missing net income."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = OwnerEarningsCalculator.calculate_conservative(
            net_income=None,
            noncash_charges=500.0,
            total_capex=1000.0,
            required_working_capital_investment=200.0,
            context=context,
        )

        assert result.calculation_status == "INSUFFICIENT_DATA"
        assert result.value is None


class TestOwnerEarningsMaintenanceCapex:
    """Tests for Maintenance CAPEX Owner Earnings model."""

    def test_maintenance_capex_valid(self):
        """Test maintenance CAPEX model with valid data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = OwnerEarningsCalculator.calculate_maintenance_capex_model(
            net_income=5000.0,
            noncash_charges=500.0,
            maintenance_capex=600.0,
            required_working_capital_investment=200.0,
            context=context,
            recurring_economic_adjustments=100.0,
        )

        assert result.calculation_status == "VALID"
        assert result.value == 4600.0  # 5000 + 500 - 600 - 200 - 100
        assert result.formula_version == OWNER_EARNINGS_MAINT_CAPEX_V1
        assert result.metadata["model"] == "MAINTENANCE_CAPEX"

    def test_maintenance_capex_higher_than_conservative(self):
        """Test that maint capex model yields higher OE than conservative (growth CAPEX ignored)."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        conservative = OwnerEarningsCalculator.calculate_conservative(
            net_income=5000.0,
            noncash_charges=500.0,
            total_capex=1000.0,
            required_working_capital_investment=200.0,
            context=context,
        )

        maintenance = OwnerEarningsCalculator.calculate_maintenance_capex_model(
            net_income=5000.0,
            noncash_charges=500.0,
            maintenance_capex=600.0,
            required_working_capital_investment=200.0,
            context=context,
        )

        # Maintenance model should yield higher OE (lower CAPEX charge)
        assert maintenance.value > conservative.value
        assert conservative.value == 4300.0
        assert maintenance.value == 4700.0


class TestOwnerEarningsCFO:
    """Tests for CFO Owner Earnings model."""

    def test_cfo_valid(self):
        """Test CFO model with valid data."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = OwnerEarningsCalculator.calculate_cfo_model(
            operating_cash_flow=4500.0,
            maintenance_capex=600.0,
            context=context,
            recurring_economic_adjustments=100.0,
        )

        assert result.calculation_status == "VALID"
        assert result.value == 3800.0  # 4500 - 600 - 100
        assert result.formula_version == OWNER_EARNINGS_CFO_V1
        assert result.metadata["model"] == "CFO"

    def test_cfo_missing_cash_flow(self):
        """Test CFO model with missing operating cash flow."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = OwnerEarningsCalculator.calculate_cfo_model(
            operating_cash_flow=None,
            maintenance_capex=600.0,
            context=context,
        )

        assert result.calculation_status == "INSUFFICIENT_DATA"


class TestModelComparison:
    """Tests comparing the three Owner Earnings models."""

    def test_three_models_inputs_same_ni_scenario(self):
        """Test all three models with same inputs."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        # Scenario: Capital-light company
        conservative = OwnerEarningsCalculator.calculate_conservative(
            net_income=1000.0,
            noncash_charges=100.0,
            total_capex=200.0,
            required_working_capital_investment=50.0,
            context=context,
        )

        maintenance = OwnerEarningsCalculator.calculate_maintenance_capex_model(
            net_income=1000.0,
            noncash_charges=100.0,
            maintenance_capex=120.0,
            required_working_capital_investment=50.0,
            context=context,
        )

        # Conservative: 1000 + 100 - 200 - 50 = 850
        # Maintenance: 1000 + 100 - 120 - 50 = 930
        assert conservative.value == 850.0
        assert maintenance.value == 930.0
        assert maintenance.value > conservative.value

    def test_capital_heavy_scenario(self):
        """Test with capital-heavy company (high total CAPEX)."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        conservative = OwnerEarningsCalculator.calculate_conservative(
            net_income=5000.0,
            noncash_charges=1000.0,
            total_capex=3000.0,
            required_working_capital_investment=500.0,
            context=context,
        )

        # 5000 + 1000 - 3000 - 500 = 2500
        assert conservative.value == 2500.0

    def test_high_sbc_adjustment(self):
        """Test with significant SBC economic adjustment."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = OwnerEarningsCalculator.calculate_conservative(
            net_income=3000.0,
            noncash_charges=200.0,
            total_capex=500.0,
            required_working_capital_investment=100.0,
            context=context,
            recurring_economic_adjustments=400.0,  # High SBC cost
        )

        # 3000 + 200 - 500 - 100 - 400 = 2200
        assert result.value == 2200.0


class TestOwnerEarningsProvenance:
    """Tests for provenance tracking in Owner Earnings calculations."""

    def test_conservative_captures_inputs(self):
        """Test that conservative model captures all input details."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = OwnerEarningsCalculator.calculate_conservative(
            net_income=5000.0,
            noncash_charges=500.0,
            total_capex=1000.0,
            required_working_capital_investment=200.0,
            context=context,
            recurring_economic_adjustments=100.0,
        )

        assert result.inputs["net_income"] == 5000.0
        assert result.inputs["total_capex"] == 1000.0
        assert result.metadata["net_income"] == 5000.0

    def test_maintenance_capex_captures_method(self):
        """Test that maintenance CAPEX model captures method details."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
        )

        result = OwnerEarningsCalculator.calculate_maintenance_capex_model(
            net_income=5000.0,
            noncash_charges=500.0,
            maintenance_capex=600.0,
            required_working_capital_investment=200.0,
            context=context,
        )

        assert result.metadata["model"] == "MAINTENANCE_CAPEX"
        assert "maintenance_capex" in result.metadata
