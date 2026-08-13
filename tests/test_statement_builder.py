"""Tests for financial statement builders."""

from datetime import date

from accountant.financial.statement_builder import (
    BalanceSheetBuilder,
    BalanceSheetData,
    CashFlowStatementBuilder,
    CashFlowStatementData,
    IncomeStatementBuilder,
    IncomeStatementData,
    StatementLineData,
    StatementQualityChecker,
)


class TestStatementLineData:
    """Tests for StatementLineData."""

    def test_create_line_numeric(self):
        """Test creating a numeric line item."""
        line = StatementLineData(
            canonical_concept="CC_REVENUE",
            value_numeric=1000.0,
            unit="USD",
        )
        assert line.canonical_concept == "CC_REVENUE"
        assert line.value_numeric == 1000.0
        assert line.unit == "USD"
        assert line.reported_or_derived == "reported"
        assert line.mapping_confidence == "HIGH"
        assert line.selection_status == "SELECTED"

    def test_create_line_text(self):
        """Test creating a text line item."""
        line = StatementLineData(
            canonical_concept="CC_SEGMENT_NAME",
            value_text="North America",
            reported_or_derived="reported",
        )
        assert line.value_text == "North America"
        assert line.value_numeric is None


class TestIncomeStatementData:
    """Tests for IncomeStatementData."""

    def test_create_empty_statement(self):
        """Test creating empty income statement."""
        statement = IncomeStatementData(
            company_id="company1",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert statement.company_id == "company1"
        assert statement.fiscal_year == 2024
        assert statement.fiscal_quarter is None
        assert len(statement.lines) == 0
        assert statement.quality_status == "UNKNOWN"

    def test_add_lines_to_statement(self):
        """Test adding lines to income statement."""
        statement = IncomeStatementData(
            company_id="company1",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        revenue = StatementLineData(
            canonical_concept="CC_REVENUE",
            value_numeric=100000.0,
            unit="USD",
        )
        statement.lines["CC_REVENUE"] = revenue

        assert "CC_REVENUE" in statement.lines
        assert statement.lines["CC_REVENUE"].value_numeric == 100000.0


class TestBalanceSheetData:
    """Tests for BalanceSheetData."""

    def test_create_balance_sheet(self):
        """Test creating balance sheet."""
        statement = BalanceSheetData(
            company_id="company1",
            fiscal_year=2024,
            fiscal_quarter=None,
            instant_date=date(2024, 12, 31),
        )
        assert statement.company_id == "company1"
        assert statement.fiscal_year == 2024
        assert statement.instant_date == date(2024, 12, 31)


class TestCashFlowStatementData:
    """Tests for CashFlowStatementData."""

    def test_create_cash_flow_statement(self):
        """Test creating cash flow statement."""
        statement = CashFlowStatementData(
            company_id="company1",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert statement.company_id == "company1"
        assert statement.fiscal_year == 2024


class TestIncomeStatementBuilder:
    """Tests for IncomeStatementBuilder."""

    def test_builder_initialization(self):
        """Test builder initialization without session."""
        builder = IncomeStatementBuilder(session=None)
        assert builder.session is None
        assert builder.VERSION == "INCOME_STATEMENT_BUILDER_V1"

    def test_builder_concepts(self):
        """Test that builder has required concepts."""
        builder = IncomeStatementBuilder()
        assert "CC_REVENUE" in builder.CONCEPTS
        assert "CC_NET_INCOME" in builder.CONCEPTS
        assert len(builder.CONCEPTS) >= 10

    def test_builder_required_concepts(self):
        """Test that builder has required concepts."""
        builder = IncomeStatementBuilder()
        assert "CC_REVENUE" in builder.REQUIRED_CONCEPTS
        assert "CC_NET_INCOME" in builder.REQUIRED_CONCEPTS

    def test_build_empty_statement(self):
        """Test building an empty statement (no DB)."""
        builder = IncomeStatementBuilder(session=None)
        statement = builder.build(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
        )

        assert statement.company_id == "AAPL"
        assert statement.fiscal_year == 2024
        assert statement.fiscal_quarter is None
        assert statement.period_type == "FY"
        assert statement.quality_status == "INSUFFICIENT_DATA"

    def test_calculate_completeness_empty(self):
        """Test completeness calculation on empty statement."""
        builder = IncomeStatementBuilder()
        statement = IncomeStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        completeness = builder.calculate_completeness(statement)
        assert completeness == 0.0

    def test_calculate_completeness_full(self):
        """Test completeness calculation with all required concepts."""
        builder = IncomeStatementBuilder()
        statement = IncomeStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        for concept in builder.REQUIRED_CONCEPTS:
            statement.lines[concept] = StatementLineData(
                canonical_concept=concept,
                value_numeric=1000.0,
                unit="USD",
            )

        completeness = builder.calculate_completeness(statement)
        assert completeness == 1.0


class TestBalanceSheetBuilder:
    """Tests for BalanceSheetBuilder."""

    def test_builder_initialization(self):
        """Test builder initialization."""
        builder = BalanceSheetBuilder(session=None)
        assert builder.session is None
        assert builder.VERSION == "BALANCE_SHEET_BUILDER_V1"

    def test_builder_concepts(self):
        """Test that builder has assets and liabilities concepts."""
        builder = BalanceSheetBuilder()
        assert "CC_TOTAL_ASSETS" in builder.ASSET_CONCEPTS
        assert "CC_TOTAL_LIABILITIES" in builder.LIABILITY_EQUITY_CONCEPTS
        assert "CC_EQUITY" in builder.LIABILITY_EQUITY_CONCEPTS

    def test_build_empty_statement(self):
        """Test building empty balance sheet."""
        builder = BalanceSheetBuilder(session=None)
        statement = builder.build(
            company_id="AAPL",
            fiscal_year=2024,
            instant_date=date(2024, 12, 31),
            fiscal_quarter=None,
        )

        assert statement.company_id == "AAPL"
        assert statement.fiscal_year == 2024
        assert statement.instant_date == date(2024, 12, 31)
        assert len(statement.lines) == 0

    def test_calculate_completeness(self):
        """Test completeness calculation."""
        builder = BalanceSheetBuilder()
        statement = BalanceSheetData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            instant_date=date(2024, 12, 31),
        )

        # Add required concepts
        for concept in builder.REQUIRED_CONCEPTS:
            statement.lines[concept] = StatementLineData(
                canonical_concept=concept,
                value_numeric=1000.0,
                unit="USD",
            )

        completeness = builder.calculate_completeness(statement)
        assert completeness == 1.0


class TestCashFlowStatementBuilder:
    """Tests for CashFlowStatementBuilder."""

    def test_builder_initialization(self):
        """Test builder initialization."""
        builder = CashFlowStatementBuilder(session=None)
        assert builder.session is None
        assert builder.VERSION == "CASH_FLOW_STATEMENT_BUILDER_V1"

    def test_builder_concepts(self):
        """Test that builder has required concepts."""
        builder = CashFlowStatementBuilder()
        assert "CC_OPERATING_CASH_FLOW" in builder.CONCEPTS
        assert "CC_CAPEX" in builder.CONCEPTS
        assert "CC_OPERATING_CASH_FLOW" in builder.REQUIRED_CONCEPTS

    def test_build_empty_statement(self):
        """Test building empty cash flow statement."""
        builder = CashFlowStatementBuilder(session=None)
        statement = builder.build(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
        )

        assert statement.company_id == "AAPL"
        assert statement.fiscal_year == 2024
        assert len(statement.lines) == 0


class TestStatementQualityChecker:
    """Tests for StatementQualityChecker."""

    def test_checker_initialization(self):
        """Test checker initialization."""
        checker = StatementQualityChecker()
        assert checker.VERSION == "STATEMENT_QUALITY_V1"
        assert checker.DEFAULT_TOLERANCE_PERCENT == 0.01

    def test_balance_sheet_identity_pass(self):
        """Test balance sheet identity check that passes."""
        checker = StatementQualityChecker()
        statement = BalanceSheetData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            instant_date=date(2024, 12, 31),
        )

        # Assets = 100, Liabilities = 60, Equity = 40
        statement.lines["CC_TOTAL_ASSETS"] = StatementLineData(
            canonical_concept="CC_TOTAL_ASSETS",
            value_numeric=100.0,
            unit="USD",
        )
        statement.lines["CC_TOTAL_LIABILITIES"] = StatementLineData(
            canonical_concept="CC_TOTAL_LIABILITIES",
            value_numeric=60.0,
            unit="USD",
        )
        statement.lines["CC_EQUITY"] = StatementLineData(
            canonical_concept="CC_EQUITY",
            value_numeric=40.0,
            unit="USD",
        )

        report = checker.check_balance_sheet(statement)
        assert report.statement_type == "balance"
        assert len(report.identity_checks) == 1
        check = report.identity_checks[0]
        assert check.passed is True

    def test_balance_sheet_identity_fail(self):
        """Test balance sheet identity check that fails."""
        checker = StatementQualityChecker()
        statement = BalanceSheetData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            instant_date=date(2024, 12, 31),
        )

        # Assets = 100, Liabilities + Equity = 120 (mismatch)
        statement.lines["CC_TOTAL_ASSETS"] = StatementLineData(
            canonical_concept="CC_TOTAL_ASSETS",
            value_numeric=100.0,
            unit="USD",
        )
        statement.lines["CC_TOTAL_LIABILITIES"] = StatementLineData(
            canonical_concept="CC_TOTAL_LIABILITIES",
            value_numeric=70.0,
            unit="USD",
        )
        statement.lines["CC_EQUITY"] = StatementLineData(
            canonical_concept="CC_EQUITY",
            value_numeric=50.0,
            unit="USD",
        )

        report = checker.check_balance_sheet(statement)
        assert len(report.identity_checks) == 1
        check = report.identity_checks[0]
        assert check.passed is False

    def test_income_statement_identity_pass(self):
        """Test income statement identity check."""
        checker = StatementQualityChecker()
        statement = IncomeStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        # Revenue 100, CoR 60, Gross Profit 40
        statement.lines["CC_REVENUE"] = StatementLineData(
            canonical_concept="CC_REVENUE",
            value_numeric=100.0,
            unit="USD",
        )
        statement.lines["CC_COST_OF_REVENUE"] = StatementLineData(
            canonical_concept="CC_COST_OF_REVENUE",
            value_numeric=60.0,
            unit="USD",
        )
        statement.lines["CC_GROSS_PROFIT"] = StatementLineData(
            canonical_concept="CC_GROSS_PROFIT",
            value_numeric=40.0,
            unit="USD",
        )

        report = checker.check_income_statement(statement)
        assert len(report.identity_checks) == 1
        check = report.identity_checks[0]
        assert check.passed is True

    def test_cash_flow_check(self):
        """Test cash flow quality check."""
        checker = StatementQualityChecker()
        statement = CashFlowStatementData(
            company_id="AAPL",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_type="FY",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        report = checker.check_cash_flow(statement)
        assert report.statement_type == "cashflow"
        assert report.fiscal_year == 2024


__all__ = [
    "TestStatementLineData",
    "TestIncomeStatementData",
    "TestBalanceSheetData",
    "TestCashFlowStatementData",
    "TestIncomeStatementBuilder",
    "TestBalanceSheetBuilder",
    "TestCashFlowStatementBuilder",
    "TestStatementQualityChecker",
]
