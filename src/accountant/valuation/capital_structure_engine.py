"""Capital structure analysis: excess cash, leverage opportunities, buyback capacity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class CapitalOpportunity(StrEnum):
    """Types of capital allocation opportunities."""

    EXCESS_CASH = "EXCESS_CASH"  # Idle cash above operational need
    UNDERLEVERAGED = "UNDERLEVERAGED"  # Below optimal debt capacity
    REFINANCE_DEBT = "REFINANCE_DEBT"  # Opportunity to refi at lower rates
    BUYBACK_ACCRETIVE = "BUYBACK_ACCRETIVE"  # Stock trading below intrinsic value
    DIVIDEND_EXPANSION = "DIVIDEND_EXPANSION"  # Sufficient FCF for higher dividends
    M_AND_A_CAPACITY = "M_AND_A_CAPACITY"  # Dry powder for acquisitions
    CONVERT_DEBT = "CONVERT_DEBT"  # Convertible opportunity to reduce dilution
    DEBT_REDUCTION = "DEBT_REDUCTION"  # Should reduce leverage


class CapStructureType(StrEnum):
    """Optimal capital structure classification."""

    CASH_RICH = "CASH_RICH"  # >20% of cap as cash
    UNDERLEVERAGED = "UNDERLEVERAGED"  # Net debt <1.0x EBITDA, room to borrow
    OPTIMAL = "OPTIMAL"  # 1.5-2.5x leverage, balanced
    OVERLEVERAGED = "OVERLEVERAGED"  # >3.5x leverage, should reduce debt
    FINANCIAL_DISTRESS = "FINANCIAL_DISTRESS"  # >4.0x leverage, severe stress


@dataclass(frozen=True)
class ExcessCashAnalysis:
    """Analysis of idle/excess cash."""

    total_cash_usd: float
    operating_cash_minimum_usd: float  # Minimum for smooth operations (30-90 days OpEx)
    excess_cash_usd: float  # Total - minimum
    excess_cash_pct_of_cap: float  # As % of total capital (E+D)
    cash_conversion_cycle_days: int | None  # Working capital cash cycle
    annualized_cash_burn: float | None  # Burn rate if relevant
    months_of_runway: float | None  # If burning cash


@dataclass(frozen=True)
class LeverageOpportunity:
    """Quantifies debt capacity and borrowing opportunity."""

    current_net_leverage_x: float  # Current leverage
    target_net_leverage_x: float  # Optimal for company/sector
    leverage_headroom_x: float  # Target - current (positive = can borrow)
    borrowing_capacity_usd: float  # Additional debt capacity (EBITDA × headroom)
    interest_rate_assumed_pct: float  # Rate on new borrowing
    annual_debt_service_new: float  # Annual interest cost on incremental debt
    fcf_coverage_after_debt: float  # FCF coverage after new debt
    recommendation: str  # BORROW, HOLD, REDUCE


@dataclass(frozen=True)
class BuybackOpportunity:
    """Buyback capacity and attractiveness assessment."""

    current_stock_price: float
    intrinsic_value_estimate: float  # DCF base case
    discount_to_intrinsic_pct: float  # (Intrinsic - Price) / Intrinsic
    buyback_is_accretive: bool  # True if discount >10%
    fcf_available_usd: float
    annual_buyback_capacity_pct: float  # Max % of shares annually
    max_shares_repurchasable: float | None  # With available FCF and leverage
    eps_accretion_pct: float | None  # EPS accretion if buyback executed
    recommendation: str  # AGGRESSIVE, MODERATE, CONSERVATIVE, NONE


@dataclass(frozen=True)
class DividendAnalysis:
    """Dividend sustainability and expansion capacity."""

    current_dividend_per_share: float | None
    current_dividend_payout_ratio: float | None  # Dividend / NI
    current_dividend_fcf_payout_ratio: float | None  # Dividend / FCF
    fcf_coverage_of_dividend: float | None  # FCF / annual dividend
    sustainable_dividend_per_share: float | None  # Max sustainable from FCF
    dividend_growth_capacity_pct: float | None  # Annual growth potential
    recommendation: str  # EXPAND, MAINTAIN, REDUCE


@dataclass(frozen=True)
class RefactoringOpportunity:
    """Debt refinancing or restructuring opportunity."""

    opportunity_type: str  # REFINANCE_LOWER_RATE, EXTEND_MATURITY, CONVERT_DEBT, REDUCE_DEBT
    debt_bucket: str | None  # Which maturity bucket (e.g., "2026 maturities")
    amount_usd: float  # Amount involved
    current_rate_pct: float | None
    refinance_rate_available_pct: float | None
    annual_interest_savings_usd: float | None
    npv_of_refactor_usd: float | None
    recommendation: str  # EXECUTE, MONITOR, DEFER


@dataclass(frozen=True)
class CapitalStructureResult:
    """Comprehensive capital structure opportunity analysis."""

    company_id: str
    fiscal_year: int
    as_of_date: str

    # Assessment
    current_cap_structure_type: CapStructureType
    current_net_leverage_x: float
    optimal_net_leverage_x: float

    # Excess cash
    excess_cash_analysis: ExcessCashAnalysis | None
    has_excess_cash: bool
    excess_cash_use_cases: list[str]  # Ranked uses (buyback, dividend, debt paydown, M&A)

    # Debt capacity
    leverage_opportunity: LeverageOpportunity | None
    can_borrow_more: bool

    # Buyback
    buyback_opportunity: BuybackOpportunity | None
    buyback_is_accretive: bool

    # Dividend
    dividend_analysis: DividendAnalysis | None
    can_expand_dividend: bool

    # Refinancing
    refactoring_opportunities: list[RefactoringOpportunity]

    # Overall recommendation
    top_priorities: list[str]  # Ranked capital allocation priorities (1=highest)
    optimal_capital_allocation: dict[str, float | str]  # {'dividends': 50%, 'buyback': 30%, 'debt_reduction': 20%}
    risk_factors: list[str]  # If structure changes
    tax_implications: list[str]  # Tax effects of proposed actions

    warnings: list[str]
    formula_version: str  # CAPITAL_STRUCTURE_V1
    calculated_at: str


class CapitalStructureEngine:
    """
    Capital structure opportunities: excess cash, leverage, buybacks, refinancing.

    Analyzes:
    1. Current capital structure vs. optimal
    2. Excess cash and uses
    3. Debt capacity and borrowing opportunity
    4. Buyback attractiveness and EPS accretion
    5. Dividend sustainability and growth
    6. Refinancing opportunities
    """

    CAPITAL_STRUCTURE_FORMULA_VERSION = "CAPITAL_STRUCTURE_V1"

    # Leverage thresholds
    OPTIMAL_NET_LEVERAGE_MIN = 1.5
    OPTIMAL_NET_LEVERAGE_MAX = 2.5
    UNDERLEVERAGED_THRESHOLD = 1.0
    OVERLEVERAGED_THRESHOLD = 3.5
    FINANCIAL_DISTRESS_THRESHOLD = 4.0

    # Cash thresholds
    EXCESS_CASH_MINIMUM_MONTHS_OPEX = 0.5  # 15 days minimum operating cash
    CASH_RICH_PCT_OF_CAP = 0.20  # >20% of capital = cash rich

    # Dividend thresholds
    SUSTAINABLE_FCF_PAYOUT_RATIO = 0.60  # Don't exceed 60% of FCF

    @staticmethod
    def analyze_excess_cash(
        cash_and_equivalents_usd: float,
        annualized_opex_usd: float | None = None,
        operating_cash_flow_usd: float | None = None,
    ) -> ExcessCashAnalysis:
        """Identify excess cash available for allocation."""
        if annualized_opex_usd is None:
            annualized_opex_usd = operating_cash_flow_usd if operating_cash_flow_usd else 0

        # Minimum operating cash (30-60 days of expenses)
        operating_cash_minimum = annualized_opex_usd * CapitalStructureEngine.EXCESS_CASH_MINIMUM_MONTHS_OPEX
        excess_cash = max(0, cash_and_equivalents_usd - operating_cash_minimum)

        return ExcessCashAnalysis(
            total_cash_usd=cash_and_equivalents_usd,
            operating_cash_minimum_usd=operating_cash_minimum,
            excess_cash_usd=excess_cash,
            excess_cash_pct_of_cap=0.0,  # Computed in full analysis
            cash_conversion_cycle_days=None,
            annualized_cash_burn=None,
            months_of_runway=None,
        )

    @staticmethod
    def analyze_leverage_opportunity(
        current_net_leverage_x: float,
        ebitda_usd: float,
        sector: str = "TECHNOLOGY",  # Default to tech
    ) -> LeverageOpportunity:
        """Quantify debt capacity and borrowing opportunity."""
        # Sector-based optimal leverage (simplified)
        sector_targets = {
            "TECHNOLOGY": 1.5,
            "INDUSTRIAL": 2.0,
            "UTILITY": 2.5,
            "FINANCIAL": 1.0,
            "CONSUMER": 2.0,
            "HEALTHCARE": 1.5,
        }
        target_leverage = sector_targets.get(sector.upper(), 2.0)

        # Headroom
        leverage_headroom = max(0, target_leverage - current_net_leverage_x)
        borrowing_capacity = leverage_headroom * ebitda_usd

        # Debt service
        assumed_rate = 0.055  # 5.5% on new borrowing
        annual_debt_service = borrowing_capacity * assumed_rate
        fcf_coverage_after = (ebitda_usd * 0.5) / max(1, annual_debt_service)  # Assume 50% conversion to FCF

        recommendation = "BORROW" if leverage_headroom > 0.5 else ("HOLD" if leverage_headroom > 0 else "REDUCE")

        return LeverageOpportunity(
            current_net_leverage_x=current_net_leverage_x,
            target_net_leverage_x=target_leverage,
            leverage_headroom_x=leverage_headroom,
            borrowing_capacity_usd=borrowing_capacity,
            interest_rate_assumed_pct=assumed_rate * 100,
            annual_debt_service_new=annual_debt_service,
            fcf_coverage_after_debt=fcf_coverage_after,
            recommendation=recommendation,
        )

    @staticmethod
    def analyze_buyback_opportunity(
        current_stock_price: float,
        intrinsic_value_estimate: float,
        shares_outstanding: float,
        annual_fcf: float,
        net_income: float,
    ) -> BuybackOpportunity:
        """Assess buyback attractiveness and EPS accretion."""
        discount_to_intrinsic = (intrinsic_value_estimate - current_stock_price) / intrinsic_value_estimate
        buyback_is_accretive = discount_to_intrinsic > 0.10

        # Buyback capacity
        annual_buyback_capacity_pct = annual_fcf / (current_stock_price * shares_outstanding)
        max_shares = annual_fcf / current_stock_price if current_stock_price > 0 else 0

        # EPS accretion
        eps_accretion = None
        if net_income > 0 and shares_outstanding > 0:
            current_eps = net_income / shares_outstanding
            new_shares = shares_outstanding - max_shares
            new_eps = net_income / max(1, new_shares) if new_shares > 0 else current_eps
            eps_accretion = ((new_eps - current_eps) / current_eps) * 100 if current_eps > 0 else 0

        # Recommendation
        if discount_to_intrinsic < 0:
            recommendation = "NONE"  # Trading above intrinsic
        elif discount_to_intrinsic > 0.20:
            recommendation = "AGGRESSIVE"  # >20% discount
        elif discount_to_intrinsic > 0.10:
            recommendation = "MODERATE"  # 10-20% discount
        else:
            recommendation = "CONSERVATIVE"  # <10% discount

        return BuybackOpportunity(
            current_stock_price=current_stock_price,
            intrinsic_value_estimate=intrinsic_value_estimate,
            discount_to_intrinsic_pct=discount_to_intrinsic * 100,
            buyback_is_accretive=buyback_is_accretive,
            fcf_available_usd=annual_fcf,
            annual_buyback_capacity_pct=annual_buyback_capacity_pct * 100,
            max_shares_repurchasable=max_shares,
            eps_accretion_pct=eps_accretion,
            recommendation=recommendation,
        )

    @staticmethod
    def analyze_dividend(
        annual_dividend_usd: float | None,
        annual_fcf: float,
        net_income: float,
        shares_outstanding: float,
    ) -> DividendAnalysis:
        """Assess dividend sustainability and expansion capacity."""
        current_dps = annual_dividend_usd / shares_outstanding if annual_dividend_usd and shares_outstanding > 0 else 0
        fcf_payout = annual_dividend_usd / annual_fcf if annual_dividend_usd and annual_fcf > 0 else 0
        ni_payout = annual_dividend_usd / net_income if annual_dividend_usd and net_income > 0 else 0
        fcf_coverage = annual_fcf / annual_dividend_usd if annual_dividend_usd and annual_dividend_usd > 0 else 0

        # Sustainable dividend (60% of FCF)
        sustainable_dividend = annual_fcf * CapitalStructureEngine.SUSTAINABLE_FCF_PAYOUT_RATIO
        sustainable_dps = sustainable_dividend / shares_outstanding if shares_outstanding > 0 else 0

        # Growth capacity
        growth_capacity = (sustainable_dps - current_dps) / current_dps * 100 if current_dps > 0 else 0

        # Recommendation
        if fcf_coverage < 1.0 or ni_payout > 0.60:
            recommendation = "REDUCE"
        elif fcf_payout < 0.30:
            recommendation = "EXPAND"
        else:
            recommendation = "MAINTAIN"

        return DividendAnalysis(
            current_dividend_per_share=current_dps,
            current_dividend_payout_ratio=ni_payout,
            current_dividend_fcf_payout_ratio=fcf_payout,
            fcf_coverage_of_dividend=fcf_coverage,
            sustainable_dividend_per_share=sustainable_dps,
            dividend_growth_capacity_pct=max(0, growth_capacity),
            recommendation=recommendation,
        )

    @staticmethod
    def calculate_capital_structure(
        company_id: str,
        fiscal_year: int,
        as_of_date: str,
        cash_usd: float,
        debt_usd: float,
        equity_market_cap_usd: float,
        ebitda_usd: float,
        fcf_annual_usd: float,
        net_income_usd: float,
        shares_outstanding: float,
        stock_price: float,
        intrinsic_value_estimate: float,
        sector: str = "TECHNOLOGY",
        current_dividend_usd: float | None = None,
        annual_opex: float | None = None,
    ) -> CapitalStructureResult:
        """Run comprehensive capital structure analysis."""
        warnings = []

        # Current structure
        total_capital = equity_market_cap_usd + debt_usd
        net_debt = debt_usd - cash_usd
        net_leverage = net_debt / ebitda_usd if ebitda_usd > 0 else 0

        # Classify current structure
        if cash_usd > total_capital * CapitalStructureEngine.CASH_RICH_PCT_OF_CAP:
            current_structure = CapStructureType.CASH_RICH
        elif net_leverage < CapitalStructureEngine.UNDERLEVERAGED_THRESHOLD:
            current_structure = CapStructureType.UNDERLEVERAGED
        elif net_leverage < CapitalStructureEngine.OVERLEVERAGED_THRESHOLD:
            current_structure = CapStructureType.OPTIMAL
        elif net_leverage < CapitalStructureEngine.FINANCIAL_DISTRESS_THRESHOLD:
            current_structure = CapStructureType.OVERLEVERAGED
        else:
            current_structure = CapStructureType.FINANCIAL_DISTRESS

        # Optimal leverage by sector
        sector_targets = {
            "TECHNOLOGY": 1.5,
            "INDUSTRIAL": 2.0,
            "UTILITY": 2.5,
            "FINANCIAL": 1.0,
            "CONSUMER": 2.0,
            "HEALTHCARE": 1.5,
        }
        optimal_leverage = sector_targets.get(sector.upper(), 2.0)

        # Analyses
        excess_cash_analysis = CapitalStructureEngine.analyze_excess_cash(cash_usd, annual_opex)
        excess_cash_analysis = ExcessCashAnalysis(
            total_cash_usd=excess_cash_analysis.total_cash_usd,
            operating_cash_minimum_usd=excess_cash_analysis.operating_cash_minimum_usd,
            excess_cash_usd=excess_cash_analysis.excess_cash_usd,
            excess_cash_pct_of_cap=excess_cash_analysis.excess_cash_usd / total_capital if total_capital > 0 else 0,
            cash_conversion_cycle_days=None,
            annualized_cash_burn=None,
            months_of_runway=None,
        )

        leverage_opportunity = CapitalStructureEngine.analyze_leverage_opportunity(net_leverage, ebitda_usd, sector)
        buyback_opportunity = CapitalStructureEngine.analyze_buyback_opportunity(
            stock_price,
            intrinsic_value_estimate,
            shares_outstanding,
            fcf_annual_usd,
            net_income_usd,
        )
        dividend_analysis = CapitalStructureEngine.analyze_dividend(
            current_dividend_usd or 0,
            fcf_annual_usd,
            net_income_usd,
            shares_outstanding,
        )

        # Priorities
        top_priorities: list[str] = []
        if excess_cash_analysis.excess_cash_usd > 0:
            top_priorities.append(f"Deploy ${excess_cash_analysis.excess_cash_usd:.0f}M excess cash")
        if buyback_opportunity.buyback_is_accretive:
            top_priorities.append(f"Execute {buyback_opportunity.recommendation} buyback ({buyback_opportunity.discount_to_intrinsic_pct:.0f}% discount)")
        if leverage_opportunity.recommendation == "BORROW":
            top_priorities.append(f"Borrow ${leverage_opportunity.borrowing_capacity_usd:.0f}M at {leverage_opportunity.interest_rate_assumed_pct:.1f}%")
        if dividend_analysis.recommendation == "EXPAND":
            top_priorities.append(f"Expand dividend {dividend_analysis.dividend_growth_capacity_pct:.0f}%")
        if net_leverage > CapitalStructureEngine.OVERLEVERAGED_THRESHOLD:
            top_priorities.append("Reduce debt (overleveraged)")

        # Optimal allocation (simplified)
        allocation = {}
        if excess_cash_analysis.excess_cash_usd > 0:
            if buyback_opportunity.buyback_is_accretive:
                allocation["buyback"] = f"${min(excess_cash_analysis.excess_cash_usd, buyback_opportunity.fcf_available_usd * 0.5):.0f}M"
            if dividend_analysis.recommendation == "EXPAND":
                allocation["dividend"] = f"${excess_cash_analysis.excess_cash_usd * 0.3:.0f}M"
            if net_leverage > CapitalStructureEngine.UNDERLEVERAGED_THRESHOLD:
                allocation["debt_reduction"] = f"${excess_cash_analysis.excess_cash_usd * 0.2:.0f}M"

        return CapitalStructureResult(
            company_id=company_id,
            fiscal_year=fiscal_year,
            as_of_date=as_of_date,
            current_cap_structure_type=current_structure,
            current_net_leverage_x=net_leverage,
            optimal_net_leverage_x=optimal_leverage,
            excess_cash_analysis=excess_cash_analysis,
            has_excess_cash=excess_cash_analysis.excess_cash_usd > 0,
            excess_cash_use_cases=["Debt reduction", "Acquisitions", "Buybacks", "Dividend expansion"],
            leverage_opportunity=leverage_opportunity,
            can_borrow_more=leverage_opportunity.leverage_headroom_x > 0,
            buyback_opportunity=buyback_opportunity,
            buyback_is_accretive=buyback_opportunity.buyback_is_accretive,
            dividend_analysis=dividend_analysis,
            can_expand_dividend=dividend_analysis.recommendation == "EXPAND",
            refactoring_opportunities=[],
            top_priorities=top_priorities,
            optimal_capital_allocation=allocation,
            risk_factors=[
                "Interest rate changes affect cost of debt",
                "Market valuation changes affect equity capacity",
                "FCF volatility affects all allocation decisions",
            ],
            tax_implications=[
                "Buybacks are tax-efficient vs. dividends for shareholders",
                "Interest deductibility reduces effective tax cost of debt",
                "Debt-financed dividends may trigger PFIC concerns",
            ],
            warnings=warnings,
            formula_version=CapitalStructureEngine.CAPITAL_STRUCTURE_FORMULA_VERSION,
            calculated_at=datetime.now().isoformat(),
        )
