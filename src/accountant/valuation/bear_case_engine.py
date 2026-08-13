"""Bear case analysis: thesis breakers, downside scenarios, and risk scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class ThesisBreaker(StrEnum):
    """Automatic disqualification from bullish thesis."""

    NEGATIVE_FCF = "NEGATIVE_FCF"  # Free cash flow is negative
    DECLINING_REVENUE = "DECLINING_REVENUE"  # Revenue trending down
    UNSUSTAINABLE_DEBT = "UNSUSTAINABLE_DEBT"  # Leverage >4x with declining FCF coverage
    CASH_BURN = "CASH_BURN"  # Burning cash despite profitability
    BROKEN_MOAT = "BROKEN_MOAT"  # Competitive position deteriorating
    REGULATORY_RISK = "REGULATORY_RISK"  # Material regulatory threat
    CUSTOMER_CONCENTRATION = "CUSTOMER_CONCENTRATION"  # Top 3 customers >50% revenue
    CAPEX_INFLATION = "CAPEX_INFLATION"  # Capex rising faster than revenue
    GOODWILL_IMPAIRMENT = "GOODWILL_IMPAIRMENT"  # Recent acquisition impairment


class BearRiskFactor(StrEnum):
    """Quantifiable downside risks (not automatic disqualifiers)."""

    MARKET_SHARE_LOSS = "MARKET_SHARE_LOSS"  # -2% to -5% market share
    MARGIN_COMPRESSION = "MARGIN_COMPRESSION"  # Operating margin decline 100-200bps
    MULTIPLE_DERATING = "MULTIPLE_DERATING"  # P/E contraction (15% to 30%)
    RECESSION_IMPACT = "RECESSION_IMPACT"  # Demand decline 10%-20% in downturn
    COST_INFLATION = "COST_INFLATION"  # COGS or OpEx inflation >2% real
    REFINANCING_RISK = "REFINANCING_RISK"  # Near-term debt >20% of total, rates higher
    EXECUTION_RISK = "EXECUTION_RISK"  # New product, market entry, turnaround
    LITIGATION_RISK = "LITIGATION_RISK"  # Pending or likely legal exposure
    MACRO_SENSITIVITY = "MACRO_SENSITIVITY"  # High beta, cyclical business
    LEADERSHIP_TRANSITION = "LEADERSHIP_TRANSITION"  # CEO/CFO change, execution uncertainty


@dataclass(frozen=True)
class ThesisBreakerFlag:
    """Identifies a thesis breaker and its severity."""

    breaker: ThesisBreaker
    description: str  # Why this breaks the thesis
    severity: str  # CRITICAL, HIGH
    threshold_metric: str | None  # What metric triggered (e.g., "FCF < $0")
    remediation: str | None  # How the company could fix it


@dataclass(frozen=True)
class BearRiskAssessment:
    """Quantified downside risk for a single factor."""

    risk_factor: BearRiskFactor
    base_case_value: float | None  # Current metric (e.g., 22% margin)
    bear_case_value: float | None  # Stressed metric (e.g., 20% margin)
    probability_pct: float  # Likelihood of stress scenario (0-100%)
    revenue_impact_pct: float  # Revenue impact if materialized (-5% to +5%)
    margin_impact_bps: float  # Margin impact in basis points (-200 to +200)
    score_contribution: float  # Points toward bear case score (0-10 per factor)


@dataclass(frozen=True)
class BearCaseScenario:
    """Stressed scenario valuation output."""

    scenario_name: str  # RECESSION, MARGIN_COMPRESSION, REGULATORY, COMBINED
    revenue_impact_pct: float  # -20% to 0%
    ebitda_margin_bps: float  # Basis point reduction from base
    fcf_impact_pct: float  # Impact on FCF generation
    wacc_increase_bps: float  # Risk premium increase
    multiple_compression_pct: float  # P/E or EV/EBITDA multiple reduction
    implied_enterprise_value: float | None  # EV in stressed case
    implied_price_per_share: float | None  # Stock price in stressed scenario
    probability_pct: float  # Likelihood of scenario (sum across scenarios ≤ 100%)


@dataclass(frozen=True)
class BearCaseResult:
    """Comprehensive bear case analysis."""

    company_id: str
    fiscal_year: int
    as_of_date: str

    # Thesis assessment
    thesis_breakers: list[ThesisBreakerFlag]
    thesis_is_broken: bool  # True if any CRITICAL breaker triggered

    # Risk assessment
    risk_factors: list[BearRiskAssessment]
    bear_case_score: float  # 0-100 (higher = more downside risk)

    # Scenario modeling
    recession_scenario: BearCaseScenario | None
    margin_compression_scenario: BearCaseScenario | None
    regulatory_scenario: BearCaseScenario | None
    combined_downside_scenario: BearCaseScenario | None

    # Consensus comparison
    consensus_target_price: float | None
    bear_case_implied_price: float | None
    downside_to_consensus_pct: float | None  # (bear - consensus) / consensus
    downside_is_material: bool  # >15% downside to consensus

    # Key risks
    top_risks: list[str]  # Ranked list of top 3-5 risks
    black_swan_risks: list[str]  # Low probability, high impact

    # Recommendations
    bear_case_action: str  # AVOID, REDUCE, HOLD, RELATIVE_VALUE
    trigger_points: list[str]  # Events that would validate bear thesis

    warnings: list[str]
    formula_version: str  # BEAR_CASE_V1
    calculated_at: str


class BearCaseEngine:
    """
    Bear case analysis: thesis breakers, scenario modeling, risk scoring.

    A bear case is the opposing thesis to base case investment. It identifies:
    1. Automatic thesis breakers (negative FCF, declining revenue, etc.)
    2. Quantifiable risks (market share, margin compression, etc.)
    3. Stressed scenarios (recession, competitive loss, regulatory)
    4. Downside vs. consensus (price target at risk)
    5. Key risks and trigger points
    """

    BEAR_CASE_FORMULA_VERSION = "BEAR_CASE_V1"

    # Thesis breaker thresholds
    NEGATIVE_FCF_THRESHOLD = 0.0
    DECLINING_REVENUE_TREND_YEARS = 2  # Revenue down 2+ consecutive years
    UNSUSTAINABLE_DEBT_THRESHOLD_LEVERAGE = 4.0  # >4x net leverage
    UNSUSTAINABLE_DEBT_THRESHOLD_COVERAGE = 1.5  # <1.5x FCF coverage
    CUSTOMER_CONCENTRATION_THRESHOLD = 0.50  # Top 3 customers >50%
    CAPEX_INFLATION_RATIO = 1.15  # Capex growing 15%+ faster than revenue

    @staticmethod
    def assess_thesis_breakers(
        fcf_current: float | None,
        revenue_trend: list[float] | None,  # Last 3 years revenue
        net_leverage_x: float | None,
        fcf_coverage_x: float | None,
        customer_concentration_pct: float | None,
        capex_last_year: float | None,
        capex_prior_year: float | None,
        revenue_last_year: float | None,
        revenue_prior_year: float | None,
        regulatory_risk_flag: bool = False,
        goodwill_impairment_flag: bool = False,
    ) -> list[ThesisBreakerFlag]:
        """
        Assess automatic thesis breakers.

        Returns: List of ThesisBreakerFlag for each breaker detected.
        """
        breakers: list[ThesisBreakerFlag] = []

        # Negative FCF
        if fcf_current is not None and fcf_current < BearCaseEngine.NEGATIVE_FCF_THRESHOLD:
            remediation_msg = (
                "Improve working capital management, reduce capex, or improve profitability"
            )
            breakers.append(
                ThesisBreakerFlag(
                    breaker=ThesisBreaker.NEGATIVE_FCF,
                    description=f"Free cash flow is negative (${fcf_current}M)",
                    severity="CRITICAL",
                    threshold_metric=f"FCF < $0 (actual: ${fcf_current}M)",
                    remediation=remediation_msg,
                )
            )

        # Declining revenue trend
        if revenue_trend and len(revenue_trend) >= BearCaseEngine.DECLINING_REVENUE_TREND_YEARS:
            declining_years = 0
            for i in range(len(revenue_trend) - 1):
                if revenue_trend[i + 1] < revenue_trend[i]:
                    declining_years += 1
            if declining_years >= BearCaseEngine.DECLINING_REVENUE_TREND_YEARS:
                breakers.append(
                    ThesisBreakerFlag(
                        breaker=ThesisBreaker.DECLINING_REVENUE,
                        description=f"Revenue declining for {declining_years}+ consecutive years",
                        severity="CRITICAL",
                        threshold_metric=f"Revenue trend: {[f'${r}M' for r in revenue_trend]}",
                        remediation="Stabilize market share, launch new products, expand into new markets",
                    )
                )

        # Unsustainable debt
        if (
            net_leverage_x is not None
            and net_leverage_x > BearCaseEngine.UNSUSTAINABLE_DEBT_THRESHOLD_LEVERAGE
            and fcf_coverage_x is not None
            and fcf_coverage_x < BearCaseEngine.UNSUSTAINABLE_DEBT_THRESHOLD_COVERAGE
        ):
            breakers.append(
                ThesisBreakerFlag(
                    breaker=ThesisBreaker.UNSUSTAINABLE_DEBT,
                    description=f"Net leverage {net_leverage_x:.1f}x with weak FCF coverage {fcf_coverage_x:.1f}x",
                    severity="CRITICAL",
                    threshold_metric=f"Leverage {net_leverage_x:.1f}x > 4.0x AND Coverage {fcf_coverage_x:.1f}x < 1.5x",
                    remediation="Reduce debt, improve profitability, or restructure balance sheet",
                )
            )

        # Customer concentration
        if customer_concentration_pct is not None and customer_concentration_pct > BearCaseEngine.CUSTOMER_CONCENTRATION_THRESHOLD:
            breakers.append(
                ThesisBreakerFlag(
                    breaker=ThesisBreaker.CUSTOMER_CONCENTRATION,
                    description=f"Top 3 customers represent {customer_concentration_pct*100:.0f}% of revenue",
                    severity="HIGH",
                    threshold_metric=f"Customer concentration {customer_concentration_pct*100:.0f}% > 50%",
                    remediation="Diversify customer base, reduce dependency on largest customers",
                )
            )

        # Capex inflation
        if (
            capex_last_year is not None
            and capex_prior_year is not None
            and capex_prior_year > 0
            and revenue_last_year is not None
            and revenue_prior_year is not None
            and revenue_prior_year > 0
        ):
            capex_growth = capex_last_year / capex_prior_year
            revenue_growth = revenue_last_year / revenue_prior_year
            if capex_growth > 0 and revenue_growth > 0 and capex_growth / revenue_growth > BearCaseEngine.CAPEX_INFLATION_RATIO:
                breakers.append(
                    ThesisBreakerFlag(
                        breaker=ThesisBreaker.CAPEX_INFLATION,
                        description=f"Capex growing {capex_growth*100:.0f}% vs revenue {revenue_growth*100:.0f}%",
                        severity="HIGH",
                        threshold_metric=f"Capex growth {capex_growth:.2f}x > revenue growth {revenue_growth:.2f}x × 1.15",
                        remediation="Optimize capex efficiency, improve capex ROI, or reduce growth investments",
                    )
                )

        # Regulatory risk
        if regulatory_risk_flag:
            breakers.append(
                ThesisBreakerFlag(
                    breaker=ThesisBreaker.REGULATORY_RISK,
                    description="Material regulatory threat identified",
                    severity="HIGH",
                    threshold_metric="Regulatory risk flag = True",
                    remediation="Monitor regulatory proceedings, assess potential fines or restrictions",
                )
            )

        # Goodwill impairment
        if goodwill_impairment_flag:
            breakers.append(
                ThesisBreakerFlag(
                    breaker=ThesisBreaker.GOODWILL_IMPAIRMENT,
                    description="Recent goodwill impairment indicates acquisition value destruction",
                    severity="HIGH",
                    threshold_metric="Goodwill impairment flag = True",
                    remediation="Assess integration success, reevaluate synergies, plan exit if necessary",
                )
            )

        return breakers

    @staticmethod
    def assess_risk_factors(
        current_market_share_pct: float | None,
        historical_market_share_pct: float | None,
        current_operating_margin_pct: float | None,
        historical_operating_margin_pct: float | None,
        current_pe_multiple: float | None,
        historical_pe_multiple: float | None,
        gross_revenue: float | None,
        roe: float | None,
        debt_to_fcf_x: float | None,
        capex_intensity_pct: float | None,
        r_and_d_intensity_pct: float | None,
    ) -> list[BearRiskAssessment]:
        """
        Assess quantifiable bear case risks.

        Returns: List of BearRiskAssessment for each risk factor.
        """
        risks: list[BearRiskAssessment] = []

        # Market share loss risk
        if current_market_share_pct is not None and historical_market_share_pct is not None:
            share_loss = current_market_share_pct - historical_market_share_pct
            if share_loss < 0:
                prob = min(100, abs(share_loss) * 20)  # Each 1% loss = 20% probability
                risks.append(
                    BearRiskAssessment(
                        risk_factor=BearRiskFactor.MARKET_SHARE_LOSS,
                        base_case_value=current_market_share_pct,
                        bear_case_value=current_market_share_pct - 3.0,  # Additional 3% loss
                        probability_pct=min(100, prob),
                        revenue_impact_pct=-3.0,
                        margin_impact_bps=-50,
                        score_contribution=min(10, prob / 10),
                    )
                )

        # Margin compression risk
        if current_operating_margin_pct is not None and historical_operating_margin_pct is not None:
            margin_decline = current_operating_margin_pct - historical_operating_margin_pct
            if margin_decline < 0:
                prob = min(100, abs(margin_decline) * 10)  # Each 1% decline = 10% probability continuation
                risks.append(
                    BearRiskAssessment(
                        risk_factor=BearRiskFactor.MARGIN_COMPRESSION,
                        base_case_value=current_operating_margin_pct,
                        bear_case_value=current_operating_margin_pct - 1.5,  # Additional 150bps compression
                        probability_pct=min(100, prob),
                        revenue_impact_pct=0.0,
                        margin_impact_bps=-150,
                        score_contribution=min(10, prob / 10),
                    )
                )

        # Multiple derating risk
        if current_pe_multiple is not None and historical_pe_multiple is not None and current_pe_multiple > historical_pe_multiple * 1.2:  # Premium to historical
            prob = 60  # 60% probability of multiple compression in downturn
            multiple_compression = current_pe_multiple * 0.15  # 15% compression
            risks.append(
                BearRiskAssessment(
                    risk_factor=BearRiskFactor.MULTIPLE_DERATING,
                    base_case_value=current_pe_multiple,
                    bear_case_value=current_pe_multiple - multiple_compression,
                    probability_pct=prob,
                    revenue_impact_pct=0.0,
                    margin_impact_bps=0,
                    score_contribution=min(10, prob / 10),
                )
            )

        # Recession impact (cyclicality)
        if gross_revenue is not None:
            # Assume 2% beta for non-cyclical, 1.5x for cyclical
            prob = 40  # 40% recession probability in 12-24 month horizon
            risks.append(
                BearRiskAssessment(
                    risk_factor=BearRiskFactor.RECESSION_IMPACT,
                    base_case_value=None,
                    bear_case_value=None,
                    probability_pct=prob,
                    revenue_impact_pct=-12.0,  # Average 12% revenue decline in recession
                    margin_impact_bps=-200,  # Fixed cost deleverage
                    score_contribution=min(10, prob / 10),
                )
            )

        # Capex/R&D intensity (leverage risk)
        if capex_intensity_pct is not None and capex_intensity_pct > 0.08:  # >8% capex/revenue
            prob = 50  # 50% risk of capex needing to increase further
            risks.append(
                BearRiskAssessment(
                    risk_factor=BearRiskFactor.CAPEX_INFLATION,
                    base_case_value=capex_intensity_pct,
                    bear_case_value=capex_intensity_pct + 0.02,
                    probability_pct=prob,
                    revenue_impact_pct=0.0,
                    margin_impact_bps=-100,
                    score_contribution=min(10, prob / 10),
                )
            )

        # Refinancing risk
        if debt_to_fcf_x is not None and debt_to_fcf_x > 3.0:  # >3 years to payoff
            prob = 70  # High probability of refinancing need
            risks.append(
                BearRiskAssessment(
                    risk_factor=BearRiskFactor.REFINANCING_RISK,
                    base_case_value=debt_to_fcf_x,
                    bear_case_value=debt_to_fcf_x + 1.0,  # Increased rates, lower FCF
                    probability_pct=prob,
                    revenue_impact_pct=-2.0,  # From higher rates
                    margin_impact_bps=-100,
                    score_contribution=min(10, prob / 10),
                )
            )

        return risks

    @staticmethod
    def calculate_bear_case(
        company_id: str,
        fiscal_year: int,
        as_of_date: str,
        thesis_breakers: list[ThesisBreakerFlag] | None = None,
        risk_factors: list[BearRiskAssessment] | None = None,
        consensus_target_price: float | None = None,
        base_enterprise_value: float | None = None,
        shares_outstanding: float | None = None,
        current_stock_price: float | None = None,
    ) -> BearCaseResult:
        """
        Calculate comprehensive bear case analysis.
        """
        if thesis_breakers is None:
            thesis_breakers = []
        if risk_factors is None:
            risk_factors = []

        warnings = []
        thesis_is_broken = any(b.severity == "CRITICAL" for b in thesis_breakers)

        # Score calculation (0-100)
        bear_case_score = 0.0
        if thesis_is_broken:
            bear_case_score = 75.0  # High score if thesis broken
        if risk_factors:
            bear_case_score += sum(r.score_contribution for r in risk_factors)
        bear_case_score = min(100.0, bear_case_score)

        # Scenario modeling
        recession_scenario = None
        margin_compression_scenario = None
        regulatory_scenario = None
        combined_downside_scenario = None

        if base_enterprise_value is not None and shares_outstanding and shares_outstanding > 0:
            base_price = base_enterprise_value / shares_outstanding if shares_outstanding > 0 else None

            # Recession scenario: -12% revenue, -200bps margin, 50bps WACC increase, 20% multiple compression
            if base_price is not None:
                recession_price = base_price * (1 - 0.12) * (1 - 0.02) * (1 - 0.20)  # Revenue × margin × multiple
                recession_scenario = BearCaseScenario(
                    scenario_name="RECESSION",
                    revenue_impact_pct=-12.0,
                    ebitda_margin_bps=-200,
                    fcf_impact_pct=-15.0,
                    wacc_increase_bps=50,
                    multiple_compression_pct=20.0,
                    implied_enterprise_value=base_enterprise_value * 0.68,
                    implied_price_per_share=recession_price,
                    probability_pct=35,
                )

            # Margin compression: -150bps, -10% multiple compression
            if base_price is not None:
                margin_price = base_price * (1 - 0.015) * (1 - 0.10)
                margin_compression_scenario = BearCaseScenario(
                    scenario_name="MARGIN_COMPRESSION",
                    revenue_impact_pct=0.0,
                    ebitda_margin_bps=-150,
                    fcf_impact_pct=-20.0,
                    wacc_increase_bps=0,
                    multiple_compression_pct=10.0,
                    implied_enterprise_value=base_enterprise_value * 0.85,
                    implied_price_per_share=margin_price,
                    probability_pct=30,
                )

            # Regulatory scenario: -5% revenue, -100bps margin, 30% multiple compression
            if base_price is not None:
                regulatory_price = base_price * (1 - 0.05) * (1 - 0.01) * (1 - 0.30)
                regulatory_scenario = BearCaseScenario(
                    scenario_name="REGULATORY",
                    revenue_impact_pct=-5.0,
                    ebitda_margin_bps=-100,
                    fcf_impact_pct=-15.0,
                    wacc_increase_bps=75,
                    multiple_compression_pct=30.0,
                    implied_enterprise_value=base_enterprise_value * 0.64,
                    implied_price_per_share=regulatory_price,
                    probability_pct=20,
                )

            # Combined downside (weighted average)
            if recession_scenario and margin_compression_scenario and regulatory_scenario:
                combined_price = (
                    recession_scenario.implied_price_per_share * 0.35 * 0.33
                    + margin_compression_scenario.implied_price_per_share * 0.30 * 0.33
                    + regulatory_scenario.implied_price_per_share * 0.20 * 0.33
                )
                combined_downside_scenario = BearCaseScenario(
                    scenario_name="COMBINED",
                    revenue_impact_pct=-6.0,
                    ebitda_margin_bps=-150,
                    fcf_impact_pct=-17.0,
                    wacc_increase_bps=40,
                    multiple_compression_pct=20.0,
                    implied_enterprise_value=base_enterprise_value * 0.72,
                    implied_price_per_share=combined_price,
                    probability_pct=85,
                )

        # Consensus comparison
        bear_case_implied_price = combined_downside_scenario.implied_price_per_share if combined_downside_scenario else None
        downside_to_consensus_pct = None
        downside_is_material = False
        if bear_case_implied_price is not None and consensus_target_price is not None and consensus_target_price > 0:
            downside_to_consensus_pct = (bear_case_implied_price - consensus_target_price) / consensus_target_price * 100
            downside_is_material = downside_to_consensus_pct < -15.0

        # Top risks
        sorted_risks = sorted(risk_factors, key=lambda r: r.score_contribution, reverse=True)
        top_risks = [f"{r.risk_factor.value}: {r.score_contribution:.0f}pts" for r in sorted_risks[:3]]

        # Black swan risks (low prob, high impact)
        black_swan_risks = [
            "Acquisition of major competitor invalidates market share thesis",
            "Disruptive new technology obsoletes product line",
            "Key executive departure disrupts strategy",
            "Supply chain disruption forces major restructuring",
            "Material litigation or regulatory action",
        ]

        # Bear case action
        bear_case_action = "HOLD"
        if bear_case_score >= 75:
            bear_case_action = "AVOID"
        elif bear_case_score >= 60:
            bear_case_action = "REDUCE"
        elif downside_is_material:
            bear_case_action = "RELATIVE_VALUE"

        # Trigger points
        price_trigger = f"Stock price breaks below ${bear_case_implied_price:.2f}" if bear_case_implied_price else "N/A"
        trigger_points = [
            "Revenue misses consensus for 2+ consecutive quarters",
            "Operating margin compression >100bps vs consensus",
            "Free cash flow turns negative",
            price_trigger,
            "Guidance reduced >10% YoY",
        ]

        return BearCaseResult(
            company_id=company_id,
            fiscal_year=fiscal_year,
            as_of_date=as_of_date,
            thesis_breakers=thesis_breakers,
            thesis_is_broken=thesis_is_broken,
            risk_factors=risk_factors,
            bear_case_score=bear_case_score,
            recession_scenario=recession_scenario,
            margin_compression_scenario=margin_compression_scenario,
            regulatory_scenario=regulatory_scenario,
            combined_downside_scenario=combined_downside_scenario,
            consensus_target_price=consensus_target_price,
            bear_case_implied_price=bear_case_implied_price,
            downside_to_consensus_pct=downside_to_consensus_pct,
            downside_is_material=downside_is_material,
            top_risks=top_risks,
            black_swan_risks=black_swan_risks,
            bear_case_action=bear_case_action,
            trigger_points=trigger_points,
            warnings=warnings,
            formula_version=BearCaseEngine.BEAR_CASE_FORMULA_VERSION,
            calculated_at=datetime.now().isoformat(),
        )
