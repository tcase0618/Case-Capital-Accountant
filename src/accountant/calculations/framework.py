"""Calculation framework for deterministic financial metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Calculation version constants
REVENUE_GROWTH_V1 = "REVENUE_GROWTH_V1"
GROSS_MARGIN_V1 = "GROSS_MARGIN_V1"
OPERATING_MARGIN_V1 = "OPERATING_MARGIN_V1"
PRETAX_MARGIN_V1 = "PRETAX_MARGIN_V1"
NET_MARGIN_V1 = "NET_MARGIN_V1"
FCF_V1 = "FCF_V1"
FCF_MARGIN_V1 = "FCF_MARGIN_V1"
CFO_NI_RATIO_V1 = "CFO_NI_RATIO_V1"
FCF_NI_RATIO_V1 = "FCF_NI_RATIO_V1"
CFO_MARGIN_V1 = "CFO_MARGIN_V1"
WORKING_CAPITAL_V1 = "WORKING_CAPITAL_V1"
NET_WORKING_CAPITAL_V1 = "NET_WORKING_CAPITAL_V1"
NWC_REVENUE_V1 = "NWC_REVENUE_V1"
CHANGE_NWC_V1 = "CHANGE_NWC_V1"
ROA_V1 = "ROA_V1"
ROE_AVG_EQUITY_V1 = "ROE_AVG_EQUITY_V1"
NOPAT_V1 = "NOPAT_V1"
INVESTED_CAPITAL_OPERATING_V1 = "INVESTED_CAPITAL_OPERATING_V1"
INVESTED_CAPITAL_FINANCING_V1 = "INVESTED_CAPITAL_FINANCING_V1"
ROIC_V1 = "ROIC_V1"
INCREMENTAL_ROIC_1Y_V1 = "INCREMENTAL_ROIC_1Y_V1"
INCREMENTAL_ROIC_3Y_V1 = "INCREMENTAL_ROIC_3Y_V1"
INCREMENTAL_ROIC_5Y_V1 = "INCREMENTAL_ROIC_5Y_V1"
REINVESTMENT_RATE_V1 = "REINVESTMENT_RATE_V1"
ACCRUAL_RATIO_V1 = "ACCRUAL_RATIO_V1"

# Owner Earnings versions
OWNER_EARNINGS_CONSERVATIVE_V1 = "OWNER_EARNINGS_CONSERVATIVE_V1"
OWNER_EARNINGS_MAINT_CAPEX_V1 = "OWNER_EARNINGS_MAINT_CAPEX_V1"
OWNER_EARNINGS_CFO_V1 = "OWNER_EARNINGS_CFO_V1"

# Maintenance CAPEX versions
MAINTENANCE_CAPEX_DA_ANCHOR_V1 = "MAINTENANCE_CAPEX_DA_ANCHOR_V1"
MAINTENANCE_CAPEX_HISTORICAL_RATIO_V1 = "MAINTENANCE_CAPEX_HISTORICAL_RATIO_V1"
MAINTENANCE_CAPEX_GROWTH_SEPARATION_V1 = "MAINTENANCE_CAPEX_GROWTH_SEPARATION_V1"
MAINTENANCE_CAPEX_RANGE_V1 = "MAINTENANCE_CAPEX_RANGE_V1"

# Economic Debt versions
ECONOMIC_DEBT_REPORTED_V1 = "ECONOMIC_DEBT_REPORTED_V1"
ECONOMIC_DEBT_ADJUSTED_V1 = "ECONOMIC_DEBT_ADJUSTED_V1"
ECONOMIC_DEBT_IMPLIED_V1 = "ECONOMIC_DEBT_IMPLIED_V1"

# Dilution versions
DILUTION_SBC_V1 = "DILUTION_SBC_V1"
DILUTION_WARRANTS_OPTIONS_V1 = "DILUTION_WARRANTS_OPTIONS_V1"

# Capital Allocation versions
CAPITAL_ALLOCATION_THRESHOLD_V1 = "CAPITAL_ALLOCATION_THRESHOLD_V1"


@dataclass
class CalculationResult:
    """Result of a single metric calculation."""

    calculation_id: str
    formula_version: str
    company_id: str
    fiscal_year: int
    fiscal_quarter: int | None
    value: float | None
    unit: str
    formula: str
    inputs: dict[str, Any] = field(default_factory=dict)
    source_statement_snapshot_ids: list[str] = field(default_factory=list)
    source_statement_line_ids: list[str] = field(default_factory=list)
    source_canonical_fact_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime | None = None
    calculation_status: str = "VALID"

    def add_warning(self, warning: str) -> None:
        """Add a warning to the calculation."""
        if warning not in self.warnings:
            self.warnings.append(warning)

    def __repr__(self) -> str:
        val_str = f"{self.value:.4f}" if self.value is not None else "None"
        return f"<{self.calculation_id} {val_str} {self.unit} FY{self.fiscal_year}>"


@dataclass
class CalculationContext:
    """Context for a calculation including inputs and configuration."""

    company_id: str
    fiscal_year: int
    fiscal_quarter: int | None = None
    period_type: str | None = None
    fiscal_year_end: str | None = None
    prior_year_context: CalculationContext | None = None
    configuration: dict[str, Any] = field(default_factory=dict)

    def with_prior_year(self, prior_context: CalculationContext) -> None:
        """Attach prior year context."""
        self.prior_year_context = prior_context


class CalculationRegistry:
    """Registry of all available calculations."""

    def __init__(self):
        """Initialize registry."""
        self._calculations: dict[str, CalculationDef] = {}

    def register(self, calc_def: CalculationDef) -> None:
        """Register a calculation."""
        self._calculations[calc_def.calculation_id] = calc_def

    def get(self, calculation_id: str) -> CalculationDef | None:
        """Get calculation definition by ID."""
        return self._calculations.get(calculation_id)

    def list_all(self) -> list[CalculationDef]:
        """List all registered calculations."""
        return list(self._calculations.values())

    def list_by_category(self, category: str) -> list[CalculationDef]:
        """List calculations by category."""
        return [c for c in self._calculations.values() if c.category == category]

    def count(self) -> int:
        """Count total calculations."""
        return len(self._calculations)


@dataclass
class CalculationDef:
    """Definition of a calculation."""

    calculation_id: str
    formula_version: str
    category: str
    label: str
    formula_text: str
    unit: str
    inputs: list[str]
    requires_prior_year: bool = False
    sector_limitations: list[str] = field(default_factory=list)
    description: str = ""

    def __hash__(self) -> int:
        return hash(self.calculation_id)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, CalculationDef):
            return NotImplemented
        return self.calculation_id == other.calculation_id


def build_canonical_registry() -> CalculationRegistry:
    """Build the canonical calculations registry."""
    registry = CalculationRegistry()

    # Profitability metrics
    registry.register(CalculationDef(
        calculation_id="REVENUE_GROWTH_YOY",
        formula_version=REVENUE_GROWTH_V1,
        category="profitability",
        label="Revenue Growth YoY",
        formula_text="(Revenue_Current - Revenue_Prior) / Revenue_Prior",
        unit="%",
        inputs=["CC_REVENUE"],
        requires_prior_year=True,
        description="Year-over-year revenue growth rate",
    ))

    registry.register(CalculationDef(
        calculation_id="GROSS_MARGIN",
        formula_version=GROSS_MARGIN_V1,
        category="profitability",
        label="Gross Margin",
        formula_text="Gross Profit / Revenue",
        unit="%",
        inputs=["CC_GROSS_PROFIT", "CC_REVENUE"],
        description="Gross profit as percentage of revenue",
    ))

    registry.register(CalculationDef(
        calculation_id="OPERATING_MARGIN",
        formula_version=OPERATING_MARGIN_V1,
        category="profitability",
        label="Operating Margin",
        formula_text="Operating Income / Revenue",
        unit="%",
        inputs=["CC_OPERATING_INCOME", "CC_REVENUE"],
        description="Operating income as percentage of revenue",
    ))

    registry.register(CalculationDef(
        calculation_id="PRETAX_MARGIN",
        formula_version=PRETAX_MARGIN_V1,
        category="profitability",
        label="Pretax Margin",
        formula_text="Pretax Income / Revenue",
        unit="%",
        inputs=["CC_PRETAX_INCOME", "CC_REVENUE"],
        description="Pretax income as percentage of revenue",
    ))

    registry.register(CalculationDef(
        calculation_id="NET_MARGIN",
        formula_version=NET_MARGIN_V1,
        category="profitability",
        label="Net Profit Margin",
        formula_text="Net Income / Revenue",
        unit="%",
        inputs=["CC_NET_INCOME", "CC_REVENUE"],
        description="Net income as percentage of revenue",
    ))

    # Cash flow metrics
    registry.register(CalculationDef(
        calculation_id="FCF",
        formula_version=FCF_V1,
        category="cash_flow",
        label="Free Cash Flow",
        formula_text="Operating Cash Flow - CapEx",
        unit="USD",
        inputs=["CC_OPERATING_CASH_FLOW", "CC_CAPEX"],
        description="Cash available after capital expenditures; FCF = CFO - CAPEX",
    ))

    registry.register(CalculationDef(
        calculation_id="FCF_MARGIN",
        formula_version=FCF_MARGIN_V1,
        category="cash_flow",
        label="FCF Margin",
        formula_text="Free Cash Flow / Revenue",
        unit="%",
        inputs=["CC_OPERATING_CASH_FLOW", "CC_CAPEX", "CC_REVENUE"],
        description="FCF as percentage of revenue",
    ))

    registry.register(CalculationDef(
        calculation_id="CFO_NI_RATIO",
        formula_version=CFO_NI_RATIO_V1,
        category="cash_flow",
        label="CFO / Net Income",
        formula_text="Operating Cash Flow / Net Income",
        unit="x",
        inputs=["CC_OPERATING_CASH_FLOW", "CC_NET_INCOME"],
        description="Ratio of operating cash flow to net income; quality of earnings metric",
    ))

    registry.register(CalculationDef(
        calculation_id="FCF_NI_RATIO",
        formula_version=FCF_NI_RATIO_V1,
        category="cash_flow",
        label="FCF / Net Income",
        formula_text="Free Cash Flow / Net Income",
        unit="x",
        inputs=["CC_OPERATING_CASH_FLOW", "CC_CAPEX", "CC_NET_INCOME"],
        description="FCF to net income ratio",
    ))

    registry.register(CalculationDef(
        calculation_id="CFO_MARGIN",
        formula_version=CFO_MARGIN_V1,
        category="cash_flow",
        label="CFO Margin",
        formula_text="Operating Cash Flow / Revenue",
        unit="%",
        inputs=["CC_OPERATING_CASH_FLOW", "CC_REVENUE"],
        description="Operating cash flow as percentage of revenue",
    ))

    # Balance sheet metrics
    registry.register(CalculationDef(
        calculation_id="WORKING_CAPITAL",
        formula_version=WORKING_CAPITAL_V1,
        category="balance_sheet",
        label="Working Capital",
        formula_text="Current Assets - Current Liabilities",
        unit="USD",
        inputs=["CC_CURRENT_ASSETS", "CC_CURRENT_LIABILITIES"],
        description="Short-term operating capital",
    ))

    registry.register(CalculationDef(
        calculation_id="NET_WORKING_CAPITAL",
        formula_version=NET_WORKING_CAPITAL_V1,
        category="balance_sheet",
        label="Net Working Capital",
        formula_text="(AR + Inventory - AP)",
        unit="USD",
        inputs=["CC_ACCOUNTS_RECEIVABLE", "CC_INVENTORY", "CC_ACCOUNTS_PAYABLE"],
        description="Operating working capital excluding cash and short-term debt",
    ))

    registry.register(CalculationDef(
        calculation_id="DEBT_TO_EQUITY",
        formula_version="DEBT_EQUITY_V1",
        category="leverage",
        label="Debt / Equity",
        formula_text="Total Debt / Total Equity",
        unit="x",
        inputs=["CC_TOTAL_DEBT", "CC_EQUITY"],
        description="Leverage ratio",
    ))

    registry.register(CalculationDef(
        calculation_id="NET_DEBT_TO_EQUITY",
        formula_version="NET_DEBT_EQUITY_V1",
        category="leverage",
        label="Net Debt / Equity",
        formula_text="(Total Debt - Cash) / Equity",
        unit="x",
        inputs=["CC_SHORT_TERM_DEBT", "CC_LONG_TERM_DEBT", "CC_CASH", "CC_EQUITY"],
        description="Leverage ratio adjusting for cash",
    ))

    # Returns metrics
    registry.register(CalculationDef(
        calculation_id="ROA",
        formula_version=ROA_V1,
        category="returns",
        label="Return on Assets",
        formula_text="Net Income / Average Total Assets",
        unit="%",
        inputs=["CC_NET_INCOME", "CC_TOTAL_ASSETS"],
        requires_prior_year=True,
        description="Net income as percentage of average total assets",
    ))

    registry.register(CalculationDef(
        calculation_id="ROE",
        formula_version=ROE_AVG_EQUITY_V1,
        category="returns",
        label="Return on Equity (Avg)",
        formula_text="Net Income / Average Equity",
        unit="%",
        inputs=["CC_NET_INCOME", "CC_EQUITY"],
        requires_prior_year=True,
        description="Net income as percentage of average equity",
    ))

    # NOPAT & Invested Capital
    registry.register(CalculationDef(
        calculation_id="NOPAT",
        formula_version=NOPAT_V1,
        category="roic",
        label="NOPAT",
        formula_text="Operating Income × (1 - Tax Rate)",
        unit="USD",
        inputs=["CC_OPERATING_INCOME", "CC_INCOME_TAX", "CC_PRETAX_INCOME"],
        description="Net Operating Profit After Tax; foundation for ROIC",
    ))

    registry.register(CalculationDef(
        calculation_id="INVESTED_CAPITAL_OPERATING",
        formula_version=INVESTED_CAPITAL_OPERATING_V1,
        category="roic",
        label="Invested Capital (Operating)",
        formula_text="Operating Assets - Operating Liabilities",
        unit="USD",
        inputs=["CC_TOTAL_ASSETS", "CC_ACCOUNTS_PAYABLE", "CC_CURRENT_LIABILITIES"],
        requires_prior_year=True,
        description="Capital deployed in operating business",
    ))

    registry.register(CalculationDef(
        calculation_id="INVESTED_CAPITAL_FINANCING",
        formula_version=INVESTED_CAPITAL_FINANCING_V1,
        category="roic",
        label="Invested Capital (Financing)",
        formula_text="Debt + Equity - Excess Cash",
        unit="USD",
        inputs=["CC_TOTAL_DEBT", "CC_EQUITY", "CC_CASH"],
        requires_prior_year=True,
        description="Capital from financing side; alternative approach",
    ))

    registry.register(CalculationDef(
        calculation_id="ROIC",
        formula_version=ROIC_V1,
        category="roic",
        label="Return on Invested Capital",
        formula_text="NOPAT / Average Invested Capital",
        unit="%",
        inputs=["CC_OPERATING_INCOME", "CC_INCOME_TAX", "CC_PRETAX_INCOME", "CC_TOTAL_ASSETS"],
        requires_prior_year=True,
        description="Returns generated on invested capital",
    ))

    registry.register(CalculationDef(
        calculation_id="INCREMENTAL_ROIC_1Y",
        formula_version=INCREMENTAL_ROIC_1Y_V1,
        category="roic",
        label="Incremental ROIC (1Y)",
        formula_text="Change in NOPAT / Change in Invested Capital",
        unit="%",
        inputs=["CC_OPERATING_INCOME", "CC_INCOME_TAX", "CC_TOTAL_ASSETS"],
        requires_prior_year=True,
        description="Returns on incremental capital deployed in last year",
    ))

    registry.register(CalculationDef(
        calculation_id="INCREMENTAL_ROIC_3Y",
        formula_version=INCREMENTAL_ROIC_3Y_V1,
        category="roic",
        label="Incremental ROIC (3Y)",
        formula_text="Change in NOPAT / Change in Invested Capital",
        unit="%",
        inputs=["CC_OPERATING_INCOME", "CC_INCOME_TAX", "CC_TOTAL_ASSETS"],
        requires_prior_year=True,
        description="Returns on incremental capital deployed over 3 years",
    ))

    registry.register(CalculationDef(
        calculation_id="INCREMENTAL_ROIC_5Y",
        formula_version=INCREMENTAL_ROIC_5Y_V1,
        category="roic",
        label="Incremental ROIC (5Y)",
        formula_text="Change in NOPAT / Change in Invested Capital",
        unit="%",
        inputs=["CC_OPERATING_INCOME", "CC_INCOME_TAX", "CC_TOTAL_ASSETS"],
        requires_prior_year=True,
        description="Returns on incremental capital deployed over 5 years",
    ))

    # Accrual quality
    registry.register(CalculationDef(
        calculation_id="ACCRUAL_RATIO",
        formula_version=ACCRUAL_RATIO_V1,
        category="quality",
        label="Accrual Ratio",
        formula_text="(Net Income - Operating Cash Flow) / Average Total Assets",
        unit="%",
        inputs=["CC_NET_INCOME", "CC_OPERATING_CASH_FLOW", "CC_TOTAL_ASSETS"],
        requires_prior_year=True,
        description="Quality of earnings; lower is better",
    ))

    return registry


# Global registry singleton
_GLOBAL_REGISTRY: CalculationRegistry | None = None


def get_calculation_registry() -> CalculationRegistry:
    """Get the global calculation registry (singleton)."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = build_canonical_registry()
    return _GLOBAL_REGISTRY


__all__ = [
    "CalculationResult",
    "CalculationContext",
    "CalculationRegistry",
    "CalculationDef",
    "get_calculation_registry",
    # Version constants
    "REVENUE_GROWTH_V1",
    "GROSS_MARGIN_V1",
    "OPERATING_MARGIN_V1",
    "PRETAX_MARGIN_V1",
    "NET_MARGIN_V1",
    "FCF_V1",
    "FCF_MARGIN_V1",
    "NOPAT_V1",
    "INVESTED_CAPITAL_OPERATING_V1",
    "INVESTED_CAPITAL_FINANCING_V1",
    "ROIC_V1",
    "INCREMENTAL_ROIC_1Y_V1",
    "INCREMENTAL_ROIC_3Y_V1",
    "INCREMENTAL_ROIC_5Y_V1",
    "REINVESTMENT_RATE_V1",
    "ACCRUAL_RATIO_V1",
]
