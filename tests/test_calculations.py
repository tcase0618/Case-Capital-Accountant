"""Tests for calculation framework and calculators."""

from datetime import date

from accountant.calculations.calculators import (
    CashFlowCalculator,
    NOPATCalculator,
    ProfitabilityCalculator,
    ROICCalculator,
)
from accountant.calculations.framework import (
    CalculationContext,
    CalculationDef,
    CalculationRegistry,
    CalculationResult,
    get_calculation_registry,
)
from accountant.financial.statement_builder import (
    BalanceSheetData,
    CashFlowStatementData,
    IncomeStatementData,
    StatementLineData,
)


class TestCalculationResult:
    """Tests for CalculationResult."""

    def test_create_result(self):
        """Test creating a calculation result."""
        result = CalculationResult(
            calculation_id="TEST_CALC",
            formula_version="V1",
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            value=50.0,
            unit="%",
            formula="X / Y",
        )

        assert result.calculation_id == "TEST_CALC"
        assert result.value == 50.0
        assert result.calculation_status == "VALID"

    def test_add_warning(self):
        """Test adding warnings to result."""
        result = CalculationResult(
            calculation_id="TEST",
            formula_version="V1",
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            value=None,
            unit="USD",
            formula="X + Y",
        )

        result.add_warning("Test warning")
        assert len(result.warnings) == 1
        assert "Test warning" in result.warnings

        # Adding same warning twice should not duplicate
        result.add_warning("Test warning")
        assert len(result.warnings) == 1


class TestCalculationContext:
    """Tests for CalculationContext."""

    def test_create_context(self):
        """Test creating calculation context."""
        context = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=4,
        )

        assert context.company_id == "AAPL"
        assert context.fiscal_year == 2024
        assert context.fiscal_quarter == 4

    def test_prior_year_context(self):
        """Test attaching prior year context."""
        context_2024 = CalculationContext(
            company_id="AAPL",
            fiscal_year=2024,
        )
        context_2023 = CalculationContext(
            company_id="AAPL",
            fiscal_year=2023,
        )

        context_2024.with_prior_year(context_2023)
        assert context_2024.prior_year_context is not None
        assert context_2024.prior_year_context.fiscal_year == 2023


class TestCalculationRegistry:
    """Tests for CalculationRegistry."""

    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = CalculationRegistry()
        assert registry.count() == 0

    def test_register_calculation(self):
        """Test registering a calculation."""
        registry = CalculationRegistry()

        calc_def = CalculationDef(
            calculation_id="TEST_CALC",
            formula_version="V1",
            category="test",
            label="Test Calculation",
            formula_text="X / Y",
            unit="%",
            inputs=["X", "Y"],
        )

        registry.register(calc_def)
        assert registry.count() == 1
        assert registry.get("TEST_CALC") is not None

    def test_list_calculations(self):
        """Test listing all calculations."""
        registry = CalculationRegistry()

        calc1 = CalculationDef(
            calculation_id="CALC_1",
            formula_version="V1",
            category="profitability",
            label="Calc 1",
            formula_text="X",
            unit="USD",
            inputs=["X"],
        )
        calc2 = CalculationDef(
            calculation_id="CALC_2",
            formula_version="V1",
            category="cash_flow",
            label="Calc 2",
            formula_text="Y",
            unit="USD",
            inputs=["Y"],
        )

        registry.register(calc1)
        registry.register(calc2)

        all_calcs = registry.list_all()
        assert len(all_calcs) == 2

    def test_list_by_category(self):
        """Test listing calculations by category."""
        registry = CalculationRegistry()

        for i in range(3):
            registry.register(
                CalculationDef(
                    calculation_id=f"PROF_{i}",
                    formula_version="V1",
                    category="profitability",
                    label=f"Profitability {i}",
                    formula_text="X",
                    unit="%",
                    inputs=["X"],
                )
            )

        registry.register(
            CalculationDef(
                calculation_id="CASH_1",
                formula_version="V1",
                category="cash_flow",
                label="Cash Flow",
                formula_text="Y",
                unit="USD",
                inputs=["Y"],
            )
        )

        prof_calcs = registry.list_by_category("profitability")
        assert len(prof_calcs) == 3

        cf_calcs = registry.list_by_category("cash_flow")
        assert len(cf_calcs) == 1


class TestCanonicalRegistry:
    """Tests for canonical calculation registry."""

    def test_get_canonical_registry(self):
        """Test getting canonical registry singleton."""
        registry = get_calculation_registry()
        assert registry is not None
        assert registry.count() > 0

    def test_registry_has_margin_calcs(self):
        """Test that registry has margin calculations."""
        registry = get_calculation_registry()
        assert registry.get("GROSS_MARGIN") is not None
        assert registry.get("OPERATING_MARGIN") is not None
        assert registry.get("NET_MARGIN") is not None

    def test_registry_has_roic_calcs(self):
        """Test that registry has ROIC calculations."""
        registry = get_calculation_registry()
        assert registry.get("NOPAT") is not None
        assert registry.get("INVESTED_CAPITAL_OPERATING") is not None
        assert registry.get("ROIC") is not None
        assert registry.get("INCREMENTAL_ROIC_1Y") is not None

    def test_registry_categories(self):
        """Test listing registry categories."""
        registry = get_calculation_registry()
        calcs = registry.list_all()
        assert len(calcs) > 0


class TestProfitabilityCalculator:
    """Tests for ProfitabilityCalculator."""

    def test_gross_margin_normal(self):
        """Test calculating gross margin."""
        statement = IncomeStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        statement.lines["CC_GROSS_PROFIT"] = StatementLineData(
            canonical_concept="CC_GROSS_PROFIT",
            value_numeric=40.0,
        )
        statement.lines["CC_REVENUE"] = StatementLineData(
            canonical_concept="CC_REVENUE",
            value_numeric=100.0,
        )

        context = CalculationContext(company_id="AAPL", fiscal_year=2024)
        result = ProfitabilityCalculator.gross_margin(statement, context)

        assert result.value == 40.0
        assert result.calculation_status == "VALID"

    def test_operating_margin_normal(self):
        """Test calculating operating margin."""
        statement = IncomeStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        statement.lines["CC_OPERATING_INCOME"] = StatementLineData(
            canonical_concept="CC_OPERATING_INCOME",
            value_numeric=20.0,
        )
        statement.lines["CC_REVENUE"] = StatementLineData(
            canonical_concept="CC_REVENUE",
            value_numeric=100.0,
        )

        context = CalculationContext(company_id="AAPL", fiscal_year=2024)
        result = ProfitabilityCalculator.operating_margin(statement, context)

        assert result.value == 20.0
        assert result.calculation_status == "VALID"

    def test_net_margin_missing_data(self):
        """Test net margin with missing data."""
        statement = IncomeStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        context = CalculationContext(company_id="AAPL", fiscal_year=2024)
        result = ProfitabilityCalculator.net_margin(statement, context)

        assert result.value is None
        assert result.calculation_status == "INSUFFICIENT_DATA"
        assert len(result.warnings) > 0


class TestCashFlowCalculator:
    """Tests for CashFlowCalculator."""

    def test_free_cash_flow(self):
        """Test calculating free cash flow."""
        statement = CashFlowStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        statement.lines["CC_OPERATING_CASH_FLOW"] = StatementLineData(
            canonical_concept="CC_OPERATING_CASH_FLOW",
            value_numeric=100.0,
        )
        statement.lines["CC_CAPEX"] = StatementLineData(
            canonical_concept="CC_CAPEX",
            value_numeric=-20.0,  # Negative per convention
        )

        context = CalculationContext(company_id="AAPL", fiscal_year=2024)
        result = CashFlowCalculator.free_cash_flow(statement, context)

        assert result.value == 80.0
        assert result.calculation_status == "VALID"


class TestNOPATCalculator:
    """Tests for NOPATCalculator."""

    def test_nopat_with_tax_rate(self):
        """Test NOPAT calculation with explicit tax rate."""
        statement = IncomeStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        statement.lines["CC_OPERATING_INCOME"] = StatementLineData(
            canonical_concept="CC_OPERATING_INCOME",
            value_numeric=100.0,
        )

        context = CalculationContext(company_id="AAPL", fiscal_year=2024)
        result = NOPATCalculator.calculate_nopat(statement, context, tax_rate_override=0.21)

        # NOPAT = 100 * (1 - 0.21) = 79
        assert result.value == 79.0
        assert result.calculation_status == "VALID"

    def test_nopat_missing_oi(self):
        """Test NOPAT with missing operating income."""
        statement = IncomeStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        context = CalculationContext(company_id="AAPL", fiscal_year=2024)
        result = NOPATCalculator.calculate_nopat(statement, context)

        assert result.value is None
        assert result.calculation_status == "INSUFFICIENT_DATA"


class TestROICCalculator:
    """Tests for ROICCalculator."""

    def test_roic_calculation(self):
        """Test ROIC calculation."""
        income_stmt = IncomeStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        income_stmt.lines["CC_OPERATING_INCOME"] = StatementLineData(
            canonical_concept="CC_OPERATING_INCOME",
            value_numeric=100.0,
        )

        bs_current = BalanceSheetData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            instant_date=date(2024, 12, 31),
        )
        bs_current.lines["CC_TOTAL_ASSETS"] = StatementLineData(
            canonical_concept="CC_TOTAL_ASSETS",
            value_numeric=500.0,
        )

        context = CalculationContext(company_id="AAPL", fiscal_year=2024)
        result = ROICCalculator.calculate_roic(
            income_stmt, bs_current, None, context, tax_rate_override=0.21
        )

        # NOPAT = 100 * 0.79 = 79, IC = 500
        # ROIC = 79 / 500 * 100 = 15.8%
        assert result.value is not None
        assert 15 < result.value < 16
        assert result.calculation_status == "VALID"


__all__ = [
    "TestCalculationResult",
    "TestCalculationContext",
    "TestCalculationRegistry",
    "TestCanonicalRegistry",
    "TestProfitabilityCalculator",
    "TestCashFlowCalculator",
    "TestNOPATCalculator",
    "TestROICCalculator",
]
