"""Financial statement builders for income, balance, and cash flow statements."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

INCOME_STATEMENT_BUILDER_V1 = "INCOME_STATEMENT_BUILDER_V1"
BALANCE_SHEET_BUILDER_V1 = "BALANCE_SHEET_BUILDER_V1"
CASH_FLOW_BUILDER_V1 = "CASH_FLOW_STATEMENT_BUILDER_V1"
STATEMENT_QUALITY_V1 = "STATEMENT_QUALITY_V1"


@dataclass
class StatementLineData:
    """Represents a single line item in a statement."""

    canonical_concept: str
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    reported_or_derived: str = "reported"
    derivation_formula: str | None = None
    derivation_method: str | None = None
    mapping_confidence: str = "HIGH"
    selection_status: str = "SELECTED"
    canonical_fact_id: str | None = None
    raw_fact_id: str | None = None
    accession_number: str | None = None
    warnings: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass
class IncomeStatementData:
    """Reconstructed income statement."""

    company_id: str
    fiscal_year: int
    fiscal_quarter: int | None
    period_type: str
    start_date: date | None
    end_date: date | None
    lines: dict[str, StatementLineData] = field(default_factory=dict)
    source_accessions: list[str] = field(default_factory=list)
    quality_status: str = "UNKNOWN"
    completeness: float | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class BalanceSheetData:
    """Reconstructed balance sheet."""

    company_id: str
    fiscal_year: int
    fiscal_quarter: int | None
    instant_date: date | None
    lines: dict[str, StatementLineData] = field(default_factory=dict)
    source_accessions: list[str] = field(default_factory=list)
    quality_status: str = "UNKNOWN"
    completeness: float | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class CashFlowStatementData:
    """Reconstructed cash flow statement."""

    company_id: str
    fiscal_year: int
    fiscal_quarter: int | None
    period_type: str
    start_date: date | None
    end_date: date | None
    lines: dict[str, StatementLineData] = field(default_factory=dict)
    source_accessions: list[str] = field(default_factory=list)
    quality_status: str = "UNKNOWN"
    completeness: float | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class QualityCheckResult:
    """Result of a quality check."""

    check_name: str
    passed: bool
    message: str | None = None
    tolerance: float | None = None
    expected: float | None = None
    actual: float | None = None


@dataclass
class StatementQualityReport:
    """Quality report for a reconstructed statement."""

    statement_type: str  # income, balance, cashflow
    fiscal_year: int
    fiscal_quarter: int | None
    overall_status: str = "UNKNOWN"  # PASS, WARNING, FAIL, INSUFFICIENT_DATA
    completeness: float | None = None
    checks: list[QualityCheckResult] = field(default_factory=list)
    identity_checks: list[QualityCheckResult] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


class IncomeStatementBuilder:
    """Builder for reconstructed income statements."""

    VERSION = INCOME_STATEMENT_BUILDER_V1

    # Canonical concepts for income statement (in order)
    CONCEPTS = [
        "CC_REVENUE",
        "CC_COST_OF_REVENUE",
        "CC_GROSS_PROFIT",
        "CC_R_AND_D",
        "CC_SG_AND_A",
        "CC_OPERATING_EXPENSES",
        "CC_OPERATING_INCOME",
        "CC_INTEREST_EXPENSE",
        "CC_PRETAX_INCOME",
        "CC_INCOME_TAX",
        "CC_NET_INCOME",
        "CC_BASIC_SHARES",
        "CC_DILUTED_SHARES",
    ]

    # Required for completeness (non-derivable)
    REQUIRED_CONCEPTS = [
        "CC_REVENUE",
        "CC_NET_INCOME",
    ]

    def __init__(self, session: Session | None = None):
        """Initialize builder.

        Args:
            session: Optional SQLAlchemy session for queries.
        """
        self.session = session

    def build(self, company_id: str, fiscal_year: int, fiscal_quarter: int | None = None,
              period_type: str = "FY") -> IncomeStatementData:
        """Build an income statement.

        Args:
            company_id: Company UUID
            fiscal_year: Fiscal year
            fiscal_quarter: Fiscal quarter (1-4) or None for FY
            period_type: Period type (Q1-Q4, FY, YTD_Q2, etc.)

        Returns:
            IncomeStatementData with reconstructed lines.
        """
        statement = IncomeStatementData(
            company_id=company_id,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            period_type=period_type,
            start_date=None,
            end_date=None,
        )

        # Query logic will be implemented when database is populated
        # For now, return empty statement with metadata
        statement.quality_status = "INSUFFICIENT_DATA"
        if not self.session:
            statement.warnings.append("No database session provided")

        return statement

    def calculate_completeness(self, statement: IncomeStatementData) -> float:
        """Calculate statement completeness as % of required concepts.

        Args:
            statement: Income statement

        Returns:
            Completeness score 0.0-1.0
        """
        if not self.REQUIRED_CONCEPTS:
            return 1.0

        present = sum(1 for c in self.REQUIRED_CONCEPTS if c in statement.lines)
        return present / len(self.REQUIRED_CONCEPTS)


class BalanceSheetBuilder:
    """Builder for reconstructed balance sheets."""

    VERSION = BALANCE_SHEET_BUILDER_V1

    # Canonical concepts for balance sheet
    ASSET_CONCEPTS = [
        "CC_CASH",
        "CC_SHORT_TERM_INVESTMENTS",
        "CC_ACCOUNTS_RECEIVABLE",
        "CC_INVENTORY",
        "CC_CURRENT_ASSETS",
        "CC_PPE_NET",
        "CC_GOODWILL",
        "CC_INTANGIBLES",
        "CC_TOTAL_ASSETS",
    ]

    LIABILITY_EQUITY_CONCEPTS = [
        "CC_ACCOUNTS_PAYABLE",
        "CC_CURRENT_LIABILITIES",
        "CC_SHORT_TERM_DEBT",
        "CC_LONG_TERM_DEBT",
        "CC_LEASE_LIABILITY",
        "CC_TOTAL_LIABILITIES",
        "CC_EQUITY",
    ]

    REQUIRED_CONCEPTS = [
        "CC_TOTAL_ASSETS",
        "CC_TOTAL_LIABILITIES",
        "CC_EQUITY",
    ]

    def __init__(self, session: Session | None = None):
        """Initialize builder.

        Args:
            session: Optional SQLAlchemy session for queries.
        """
        self.session = session

    def build(self, company_id: str, fiscal_year: int, instant_date: date | None = None,
              fiscal_quarter: int | None = None) -> BalanceSheetData:
        """Build a balance sheet.

        Args:
            company_id: Company UUID
            fiscal_year: Fiscal year
            instant_date: Instant date (usually period end)
            fiscal_quarter: Fiscal quarter (1-4) or None for FY

        Returns:
            BalanceSheetData with reconstructed lines.
        """
        statement = BalanceSheetData(
            company_id=company_id,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            instant_date=instant_date,
        )

        # Query logic will be implemented when database is populated
        # For now, return empty statement with metadata
        statement.quality_status = "INSUFFICIENT_DATA"
        if not self.session:
            statement.warnings.append("No database session provided")

        return statement

    def calculate_completeness(self, statement: BalanceSheetData) -> float:
        """Calculate statement completeness as % of required concepts.

        Args:
            statement: Balance sheet

        Returns:
            Completeness score 0.0-1.0
        """
        if not self.REQUIRED_CONCEPTS:
            return 1.0

        present = sum(1 for c in self.REQUIRED_CONCEPTS if c in statement.lines)
        return present / len(self.REQUIRED_CONCEPTS)


class CashFlowStatementBuilder:
    """Builder for reconstructed cash flow statements."""

    VERSION = CASH_FLOW_BUILDER_V1

    CONCEPTS = [
        "CC_OPERATING_CASH_FLOW",
        "CC_CAPEX",
        "CC_INVESTING_CASH_FLOW",
        "CC_FINANCING_CASH_FLOW",
        "CC_DEPRECIATION_AMORTIZATION",
        "CC_STOCK_BASED_COMPENSATION",
        "CC_DIVIDENDS",
        "CC_SHARE_REPURCHASES",
    ]

    REQUIRED_CONCEPTS = [
        "CC_OPERATING_CASH_FLOW",
    ]

    def __init__(self, session: Session | None = None):
        """Initialize builder.

        Args:
            session: Optional SQLAlchemy session for queries.
        """
        self.session = session

    def build(self, company_id: str, fiscal_year: int, fiscal_quarter: int | None = None,
              period_type: str = "FY") -> CashFlowStatementData:
        """Build a cash flow statement.

        Args:
            company_id: Company UUID
            fiscal_year: Fiscal year
            fiscal_quarter: Fiscal quarter (1-4) or None for FY
            period_type: Period type (Q1-Q4, FY, YTD_Q2, etc.)

        Returns:
            CashFlowStatementData with reconstructed lines.
        """
        statement = CashFlowStatementData(
            company_id=company_id,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            period_type=period_type,
            start_date=None,
            end_date=None,
        )

        # Query logic will be implemented when database is populated
        # For now, return empty statement with metadata
        statement.quality_status = "INSUFFICIENT_DATA"
        if not self.session:
            statement.warnings.append("No database session provided")

        return statement

    def calculate_completeness(self, statement: CashFlowStatementData) -> float:
        """Calculate statement completeness as % of required concepts.

        Args:
            statement: Cash flow statement

        Returns:
            Completeness score 0.0-1.0
        """
        if not self.REQUIRED_CONCEPTS:
            return 1.0

        present = sum(1 for c in self.REQUIRED_CONCEPTS if c in statement.lines)
        return present / len(self.REQUIRED_CONCEPTS)


class StatementQualityChecker:
    """Checks financial statement quality and accounting identities."""

    VERSION = STATEMENT_QUALITY_V1

    # Default tolerances (configurable)
    DEFAULT_TOLERANCE_PERCENT = 0.01  # 1%

    def check_balance_sheet(self, statement: BalanceSheetData,
                           tolerance_percent: float | None = None) -> StatementQualityReport:
        """Check balance sheet accounting identity.

        Args:
            statement: Reconstructed balance sheet
            tolerance_percent: Tolerance for identity check (default 1%)

        Returns:
            StatementQualityReport with identity checks.
        """
        report = StatementQualityReport(
            statement_type="balance",
            fiscal_year=statement.fiscal_year,
            fiscal_quarter=statement.fiscal_quarter,
        )

        tolerance = tolerance_percent or self.DEFAULT_TOLERANCE_PERCENT

        # Check: Assets = Liabilities + Equity
        assets = statement.lines.get("CC_TOTAL_ASSETS")
        liabilities = statement.lines.get("CC_TOTAL_LIABILITIES")
        equity = statement.lines.get("CC_EQUITY")

        if assets and liabilities and equity:
            assets_val = assets.value_numeric or 0
            liab_equity_val = (liabilities.value_numeric or 0) + (equity.value_numeric or 0)

            if assets_val != 0:
                diff_pct = abs(assets_val - liab_equity_val) / abs(assets_val)
                check = QualityCheckResult(
                    check_name="Assets = Liabilities + Equity",
                    passed=diff_pct <= tolerance,
                    message=f"Difference: {diff_pct * 100:.2f}%",
                    tolerance=tolerance,
                    expected=assets_val,
                    actual=liab_equity_val,
                )
                report.identity_checks.append(check)

        return report

    def check_income_statement(self, statement: IncomeStatementData,
                              tolerance_percent: float | None = None) -> StatementQualityReport:
        """Check income statement accounting identities.

        Args:
            statement: Reconstructed income statement
            tolerance_percent: Tolerance for identity checks (default 1%)

        Returns:
            StatementQualityReport with identity checks.
        """
        report = StatementQualityReport(
            statement_type="income",
            fiscal_year=statement.fiscal_year,
            fiscal_quarter=statement.fiscal_quarter,
        )

        tolerance = tolerance_percent or self.DEFAULT_TOLERANCE_PERCENT

        # Check: Revenue - CoR = Gross Profit
        revenue = statement.lines.get("CC_REVENUE")
        cost = statement.lines.get("CC_COST_OF_REVENUE")
        gross = statement.lines.get("CC_GROSS_PROFIT")

        if revenue and cost and gross:
            rev_val = revenue.value_numeric or 0
            cost_val = cost.value_numeric or 0
            gross_val = gross.value_numeric or 0
            expected = rev_val - cost_val

            if expected != 0:
                diff_pct = abs(gross_val - expected) / abs(expected)
                check = QualityCheckResult(
                    check_name="Revenue - CoR = Gross Profit",
                    passed=diff_pct <= tolerance,
                    message=f"Difference: {diff_pct * 100:.2f}%",
                    tolerance=tolerance,
                    expected=expected,
                    actual=gross_val,
                )
                report.identity_checks.append(check)

        return report

    def check_cash_flow(self, statement: CashFlowStatementData,
                       tolerance_percent: float | None = None) -> StatementQualityReport:
        """Check cash flow statement quality.

        Args:
            statement: Reconstructed cash flow statement
            tolerance_percent: Tolerance for checks (default 1%)

        Returns:
            StatementQualityReport with quality checks.
        """
        report = StatementQualityReport(
            statement_type="cashflow",
            fiscal_year=statement.fiscal_year,
            fiscal_quarter=statement.fiscal_quarter,
        )

        # Stub: Basic checks would include CAPEX sign, etc.
        return report


__all__ = [
    "IncomeStatementBuilder",
    "BalanceSheetBuilder",
    "CashFlowStatementBuilder",
    "StatementQualityChecker",
    "IncomeStatementData",
    "BalanceSheetData",
    "CashFlowStatementData",
    "StatementQualityReport",
    "StatementLineData",
    "INCOME_STATEMENT_BUILDER_V1",
    "BALANCE_SHEET_BUILDER_V1",
    "CASH_FLOW_BUILDER_V1",
    "STATEMENT_QUALITY_V1",
]
