"""Valuation engine: DCF, multiples, NAV, SOTP, and scenario-based valuations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class ValuationMethod(StrEnum):
    """Supported valuation methodologies."""

    DCF = "DCF"
    OWNER_EARNINGS = "OWNER_EARNINGS"
    FCFF = "FCFF"
    FCFE = "FCFE"
    DIVIDEND_DISCOUNT = "DIVIDEND_DISCOUNT"
    HISTORICAL_MULTIPLES = "HISTORICAL_MULTIPLES"
    PEER_MULTIPLES = "PEER_MULTIPLES"
    NET_ASSET_VALUE = "NET_ASSET_VALUE"
    SUM_OF_PARTS = "SUM_OF_PARTS"
    SCENARIO = "SCENARIO"


class ApplicabilityStatus(StrEnum):
    """Method applicability assessment."""

    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNRELIABLE_INPUTS = "UNRELIABLE_INPUTS"


class ValuationScenario(StrEnum):
    """Valuation scenario designations."""

    BEAR = "BEAR"
    BASE = "BASE"
    BULL = "BULL"


@dataclass(frozen=True)
class ValuationAssumption:
    """Single valuation assumption with version tracking."""

    name: str  # e.g., "terminal_growth_rate"
    value: float | None
    unit: str | None  # e.g., "%", "x", "bps"
    source: str  # EXPLICIT, FALLBACK, HISTORICAL_MEDIAN, CONFIGURED
    is_fallback: bool  # True if assumption was defaulted
    reasoning: str  # Why this assumption was used
    version: str  # Formula or assumption set version


@dataclass(frozen=True)
class DCFAssumptions:
    """Comprehensive DCF assumptions."""

    revenue_growth_rates: list[float | None]  # By year
    operating_margins: list[float | None]  # By year
    tax_rate: float | None
    reinvestment_rate: float | None
    working_capital_pct_revenue: float | None
    capex_pct_revenue: float | None
    nopat_margin: float | None
    forecast_horizon_years: int
    terminal_growth_rate: float | None
    discount_rate: float | None
    wacc: float | None
    assumptions: list[ValuationAssumption]
    notes: list[str]


@dataclass(frozen=True)
class WAACComponents:
    """WACC calculation components."""

    risk_free_rate: float | None
    equity_risk_premium: float | None
    beta: float | None
    cost_of_equity: float | None
    cost_of_debt: float | None
    tax_rate: float | None
    market_cap_usd: float | None
    debt_amount_usd: float | None
    equity_weight: float | None
    debt_weight: float | None
    wacc: float | None
    formula_version: str  # WACC_V1, etc.
    notes: list[str]


@dataclass(frozen=True)
class DCFValuation:
    """DCF valuation result."""

    company_id: str
    fiscal_year: int
    as_of_date: str

    # Scenarios
    bear_pv: float | None
    base_pv: float | None
    bull_pv: float | None

    # Implied shares
    bear_price_per_share: float | None
    base_price_per_share: float | None
    bull_price_per_share: float | None

    # Terminal value
    terminal_value: float | None
    terminal_growth_rate: float | None

    # Assumptions used
    assumptions: DCFAssumptions
    wacc_components: WAACComponents

    # Reference
    reference_market_price: float | None
    margin_of_safety_pct: float | None  # (Value - Price) / Price

    formula_version: str  # DCF_V1, etc.
    calculated_at: str


@dataclass(frozen=True)
class MultiplesValuation:
    """Multiples-based valuation."""

    company_id: str
    fiscal_year: int
    as_of_date: str

    # Historical multiples
    multiple_name: str  # P/E, EV/EBITDA, etc.
    company_multiple: float | None
    historical_median: float | None
    historical_percentile: float | None  # vs own history

    # Peer multiples
    peer_median: float | None
    peer_percentile: float | None  # percentile rank within peers

    # Implied valuation
    implied_value_per_share: float | None
    reference_market_price: float | None
    margin_of_safety_pct: float | None

    applicability: ApplicabilityStatus
    formula_version: str
    calculated_at: str


@dataclass(frozen=True)
class ValuationResult:
    """Complete valuation result for a company."""

    company_id: str
    ticker: str | None
    as_of_date: str

    # Method results
    dcf_valuation: DCFValuation | None
    owner_earnings_valuation: DCFValuation | None  # Uses OE as FCF proxy
    fcff_valuation: DCFValuation | None
    fcfe_valuation: DCFValuation | None
    multiples_valuations: list[MultiplesValuation]  # P/E, EV/EBITDA, etc.
    nav_valuation: MultiplesValuation | None
    sotp_valuation: MultiplesValuation | None

    # Aggregate metrics
    valuation_range_low: float | None  # Bear across methods
    valuation_range_high: float | None  # Bull across methods
    reference_market_price: float | None

    # Overall assessment
    implied_margin_of_safety: float | None  # Aggregate across methods
    warnings: list[str]
    data_quality_issues: list[str]

    # Provenance
    formula_versions: dict[str, str]  # Method → formula version
    calculation_date: str
    is_point_in_time: bool


class ValuationEngine:
    """
    Deterministic valuation engine supporting multiple methods.

    Consumes existing Accountant outputs:
    - Owner Earnings (calculations.owner_earnings)
    - Economic Debt (calculations.economic_debt_engine)
    - Cash flow metrics (calculations.framework)
    - Historical financials (calculations.calculators)
    - Peer data (analysis.peer_statistics_engine)
    """

    DCF_FORMULA_VERSION = "DCF_V1"
    WACC_FORMULA_VERSION = "WACC_V1"
    MULTIPLES_FORMULA_VERSION = "MULTIPLES_V1"
    NAV_FORMULA_VERSION = "NAV_V1"
    SOTP_FORMULA_VERSION = "SOTP_V1"

    # Fallback assumptions (explicit, versioned)
    DEFAULT_TERMINAL_GROWTH = 0.025  # 2.5%
    DEFAULT_FORECAST_HORIZON = 10  # years
    DEFAULT_EQUITY_RISK_PREMIUM = 0.06  # 6%
    DEFAULT_TAX_RATE = 0.21  # 21% (US federal)

    @staticmethod
    def calculate_dcf(
        company_id: str,
        fiscal_year: int,
        as_of_date: str,
        fcf_projections: list[float | None],
        terminal_growth: float | None = None,
        discount_rate: float | None = None,
        forecast_horizon: int | None = None,
        shares_outstanding: float | None = None,
        reference_price: float | None = None,
    ) -> DCFValuation:
        """
        Calculate DCF valuation using provided projections.

        Input: FCF projections, terminal growth, discount rate
        Output: DCFValuation with PV, per-share value, scenarios
        """
        if not fcf_projections or all(x is None for x in fcf_projections):
            return DCFValuation(
                company_id=company_id,
                fiscal_year=fiscal_year,
                as_of_date=as_of_date,
                bear_pv=None,
                base_pv=None,
                bull_pv=None,
                bear_price_per_share=None,
                base_price_per_share=None,
                bull_price_per_share=None,
                terminal_value=None,
                terminal_growth_rate=None,
                assumptions=DCFAssumptions(
                    revenue_growth_rates=[],
                    operating_margins=[],
                    tax_rate=None,
                    reinvestment_rate=None,
                    working_capital_pct_revenue=None,
                    capex_pct_revenue=None,
                    nopat_margin=None,
                    forecast_horizon_years=forecast_horizon or ValuationEngine.DEFAULT_FORECAST_HORIZON,
                    terminal_growth_rate=terminal_growth or ValuationEngine.DEFAULT_TERMINAL_GROWTH,
                    discount_rate=discount_rate,
                    wacc=discount_rate,
                    assumptions=[],
                    notes=["Insufficient FCF projections"],
                ),
                wacc_components=WAACComponents(
                    risk_free_rate=None,
                    equity_risk_premium=None,
                    beta=None,
                    cost_of_equity=None,
                    cost_of_debt=None,
                    tax_rate=None,
                    market_cap_usd=None,
                    debt_amount_usd=None,
                    equity_weight=None,
                    debt_weight=None,
                    wacc=discount_rate,
                    formula_version=ValuationEngine.WACC_FORMULA_VERSION,
                    notes=["Insufficient data for full WACC calculation"],
                ),
                reference_market_price=reference_price,
                margin_of_safety_pct=None,
                formula_version=ValuationEngine.DCF_FORMULA_VERSION,
                calculated_at=datetime.now().isoformat(),
            )

        # Ensure defaults
        tg = terminal_growth or ValuationEngine.DEFAULT_TERMINAL_GROWTH
        dr = discount_rate or 0.10  # Default 10% if not provided
        fh = forecast_horizon or ValuationEngine.DEFAULT_FORECAST_HORIZON

        # Calculate PV of explicit forecast period
        pv_fcf = 0.0
        valid_fcfs = []
        for i, fcf in enumerate(fcf_projections[:fh]):
            if fcf is not None:
                discount_factor = 1.0 / ((1.0 + dr) ** (i + 1))
                pv_fcf += fcf * discount_factor
                valid_fcfs.append(fcf)

        # Terminal value: last FCF × (1 + g) / (r - g)
        terminal_value = None
        if valid_fcfs and (dr - tg) > 0.001:
            final_fcf = valid_fcfs[-1]
            terminal_value = final_fcf * (1.0 + tg) / (dr - tg)
            pv_terminal = terminal_value / ((1.0 + dr) ** fh)
            pv_enterprise = pv_fcf + pv_terminal
        else:
            pv_enterprise = pv_fcf
            pv_terminal = None

        # Convert to per-share value
        base_price = None
        if shares_outstanding and shares_outstanding > 0:
            base_price = pv_enterprise / shares_outstanding

        # Margin of safety
        mos_pct = None
        if base_price and reference_price and reference_price > 0:
            mos_pct = (base_price - reference_price) / reference_price * 100

        assumptions = DCFAssumptions(
            revenue_growth_rates=[],
            operating_margins=[],
            tax_rate=ValuationEngine.DEFAULT_TAX_RATE,
            reinvestment_rate=None,
            working_capital_pct_revenue=None,
            capex_pct_revenue=None,
            nopat_margin=None,
            forecast_horizon_years=fh,
            terminal_growth_rate=tg,
            discount_rate=dr,
            wacc=dr,
            assumptions=[
                ValuationAssumption(
                    name="terminal_growth_rate",
                    value=tg,
                    unit="%",
                    source="EXPLICIT" if terminal_growth else "FALLBACK",
                    is_fallback=terminal_growth is None,
                    reasoning="Long-term GDP growth proxy",
                    version=ValuationEngine.DCF_FORMULA_VERSION,
                ),
                ValuationAssumption(
                    name="discount_rate",
                    value=dr,
                    unit="%",
                    source="EXPLICIT" if discount_rate else "FALLBACK",
                    is_fallback=discount_rate is None,
                    reasoning="WACC or default",
                    version=ValuationEngine.DCF_FORMULA_VERSION,
                ),
            ],
            notes=[],
        )

        return DCFValuation(
            company_id=company_id,
            fiscal_year=fiscal_year,
            as_of_date=as_of_date,
            bear_pv=pv_enterprise * 0.80 if pv_enterprise else None,
            base_pv=pv_enterprise,
            bull_pv=pv_enterprise * 1.20 if pv_enterprise else None,
            bear_price_per_share=base_price * 0.80 if base_price else None,
            base_price_per_share=base_price,
            bull_price_per_share=base_price * 1.20 if base_price else None,
            terminal_value=terminal_value,
            terminal_growth_rate=tg,
            assumptions=assumptions,
            wacc_components=WAACComponents(
                risk_free_rate=None,
                equity_risk_premium=None,
                beta=None,
                cost_of_equity=None,
                cost_of_debt=None,
                tax_rate=ValuationEngine.DEFAULT_TAX_RATE,
                market_cap_usd=None,
                debt_amount_usd=None,
                equity_weight=None,
                debt_weight=None,
                wacc=dr,
                formula_version=ValuationEngine.WACC_FORMULA_VERSION,
                notes=["Simplified WACC; full calculation would require beta, risk premium"],
            ),
            reference_market_price=reference_price,
            margin_of_safety_pct=mos_pct,
            formula_version=ValuationEngine.DCF_FORMULA_VERSION,
            calculated_at=datetime.now().isoformat(),
        )

    @staticmethod
    def assess_method_applicability(
        method: ValuationMethod,
        company_id: str,
        has_fcf_history: bool = False,
        has_dividend_history: bool = False,
        has_multiples_history: bool = False,
        has_segment_data: bool = False,
        has_peer_group: bool = False,
        is_financial_sector: bool = False,
        is_reit: bool = False,
    ) -> tuple[ApplicabilityStatus, str]:
        """
        Assess whether a valuation method is applicable for a company.

        Input: Company characteristics
        Output: (ApplicabilityStatus, reason)
        """
        if method == ValuationMethod.DCF:
            if is_financial_sector or is_reit:
                return (
                    ApplicabilityStatus.NOT_APPLICABLE,
                    "DCF not suitable for financial institutions; use FCFE or multiples",
                )
            if not has_fcf_history:
                return (
                    ApplicabilityStatus.INSUFFICIENT_DATA,
                    "FCF history required for DCF",
                )
            return (ApplicabilityStatus.APPLICABLE, "")

        elif method == ValuationMethod.DIVIDEND_DISCOUNT:
            if not has_dividend_history:
                return (
                    ApplicabilityStatus.NOT_APPLICABLE,
                    "No dividend history; use DCF or multiples",
                )
            return (ApplicabilityStatus.APPLICABLE, "")

        elif method == ValuationMethod.HISTORICAL_MULTIPLES:
            if not has_multiples_history:
                return (
                    ApplicabilityStatus.INSUFFICIENT_DATA,
                    "Need historical multiples (P/E, EV/EBITDA, etc.)",
                )
            return (ApplicabilityStatus.APPLICABLE, "")

        elif method == ValuationMethod.PEER_MULTIPLES:
            if not has_peer_group:
                return (
                    ApplicabilityStatus.INSUFFICIENT_DATA,
                    "Peer group required for multiple comparison",
                )
            return (ApplicabilityStatus.APPLICABLE, "")

        elif method == ValuationMethod.SUM_OF_PARTS:
            if not has_segment_data:
                return (
                    ApplicabilityStatus.NOT_APPLICABLE,
                    "Segment data required for SOTP; use DCF instead",
                )
            return (ApplicabilityStatus.APPLICABLE, "")

        elif method == ValuationMethod.NET_ASSET_VALUE:
            if is_financial_sector:
                return (
                    ApplicabilityStatus.APPLICABLE,
                    "NAV appropriate for banks, insurers",
                )
            if is_reit:
                return (
                    ApplicabilityStatus.APPLICABLE,
                    "NAV appropriate for REITs (FFO-based)",
                )
            return (
                ApplicabilityStatus.NOT_APPLICABLE,
                "NAV typically for financial/real estate; use DCF for corporates",
            )

        else:
            return (ApplicabilityStatus.INSUFFICIENT_DATA, "Method not recognized")
