"""Special situations: M&A, spin-offs, restructurings, bankruptcy scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class SpecialSituationType(StrEnum):
    """Types of special situation events."""

    M_AND_A_ACQUISITION = "M_AND_A_ACQUISITION"  # Company as acquisition target
    M_AND_A_BUYER = "M_AND_A_BUYER"  # Company as acquirer
    TENDER_OFFER = "TENDER_OFFER"  # Take-private or going-private
    SPIN_OFF = "SPIN_OFF"  # Separation into independent companies
    DIVIDEND_RECAPITALIZATION = "DIVIDEND_RECAPITALIZATION"  # Debt-financed dividend
    RESTRUCTURING_CH11 = "RESTRUCTURING_CH11"  # Chapter 11 bankruptcy
    RESTRUCTURING_OOC = "RESTRUCTURING_OOC"  # Out-of-court restructuring
    RIGHTS_OFFERING = "RIGHTS_OFFERING"  # Shareholder rights issue
    MERGER_ARBITRAGE = "MERGER_ARBITRAGE"  # Cash or stock merger (deal risk)
    DISTRESSED_DEBT = "DISTRESSED_DEBT"  # Defaulted or near-default debt


class EventProbability(StrEnum):
    """Likelihood of special situation event."""

    SPECULATIVE = "SPECULATIVE"  # <25% probability
    POSSIBLE = "POSSIBLE"  # 25-50%
    LIKELY = "LIKELY"  # 50-75%
    HIGHLY_LIKELY = "HIGHLY_LIKELY"  # >75%


@dataclass(frozen=True)
class AcquisitionScenario:
    """M&A valuation and dynamics for target company."""

    target_current_price: float
    implied_enterprise_value: float
    control_premium_pct: float  # Typical 20-40% over trading price
    potential_acquirer_synergies_usd: float | None  # Cost synergies, revenue synergies
    implied_acquisition_price: float  # Current + premium
    implied_price_per_share: float
    upside_to_current_pct: float
    deal_likelihood_pct: float  # Based on strategic fit, valuation, market
    deal_timing_months: int | None  # Estimated timeline


@dataclass(frozen=True)
class TenderOfferScenario:
    """Tender offer (take-private) analysis."""

    current_stock_price: float
    tender_offer_price_per_share: float | None  # Proposed price
    minimum_tender_acceptance_pct: float  # Typical 50-66%
    financing_type: str  # CASH, STOCK, DEBT, MIXED
    deal_certainty_pct: float  # Likelihood deal closes as proposed
    expected_close_timeline_months: int
    arbitrage_spread_pct: float  # (Offer - current) / current
    downside_if_fails_pct: float  # Stock decline if deal fails (-10% to -30%)


@dataclass(frozen=True)
class SpinOffScenario:
    """Spin-off/separation value creation."""

    parent_implied_value: float
    spinco_implied_value: float
    combined_sum_of_parts: float  # Parent + Spinco value
    current_parent_market_cap: float
    value_creation_pct: float  # (SOTP - current) / current
    synergy_loss_estimate: float | None  # Cost synergies lost
    standalone_viability_score: float  # 1-10 (10=highly viable standalone)
    tax_efficiency: str  # TAX_FREE, TAXABLE, TBD


@dataclass(frozen=True)
class RestructuringScenario:
    """Bankruptcy/restructuring outcome scenarios."""

    restructuring_type: str  # CHAPTER_11, OUT_OF_COURT, PREPACKAGED
    current_equity_value: float
    equity_value_in_restructuring: float  # Post-restructuring (recovery value)
    debt_recovery_pct: float  # % of debt principal recovered (0-100%)
    equity_recovery_pct: float  # % of equity value preserved (0-100%)
    dilution_from_new_equity_pct: float  # New equity issued in restructuring
    timeline_months: int  # Expected duration
    emergence_probability_pct: float  # % chance emerges successfully


@dataclass(frozen=True)
class SpecialSituationResult:
    """Comprehensive special situations analysis."""

    company_id: str
    fiscal_year: int
    as_of_date: str

    # Event assessment
    situation_type: SpecialSituationType
    event_probability: EventProbability
    probability_pct: float  # Estimated likelihood (0-100%)

    # Valuation impact scenarios
    base_case_price: float | None  # Unaffected price
    bull_case_price: float | None  # Best outcome
    bear_case_price: float | None  # Worst outcome
    expected_value_price: float | None  # Probability-weighted

    # Scenario-specific details
    acquisition_scenario: AcquisitionScenario | None
    tender_offer_scenario: TenderOfferScenario | None
    spinoff_scenario: SpinOffScenario | None
    restructuring_scenario: RestructuringScenario | None

    # Risk factors
    deal_risks: list[str]  # Regulatory, financing, shareholder vote, etc.
    key_catalysts: list[str]  # Events that could happen
    timeline_milestones: list[str]  # Expected dates/events

    # Current market pricing
    current_stock_price: float
    current_price_vs_base_case_pct: float  # How much premium/discount
    current_price_vs_expected_value_pct: float
    mispricing_opportunity: str  # UPSIDE, DOWNSIDE, FAIR

    # Recommendation
    investment_thesis: str  # Brief rationale
    action: str  # BUY, REDUCE, HOLD, AVOID
    catalyst_timeline: str  # Next 6 months, 12 months, 18+ months
    risk_reward: str  # E.g., "3:1 upside/downside"

    warnings: list[str]
    formula_version: str  # SPECIAL_SITUATIONS_V1
    calculated_at: str


class SpecialSituationsEngine:
    """
    Special situations analysis: M&A, spin-offs, restructurings, bankruptcies.

    Models:
    1. Acquisition scenarios (control premium, timing)
    2. Tender offers (deal certainty, spread)
    3. Spin-offs (value creation, standalone viability)
    4. Restructurings (recovery scenarios)
    5. Distressed debt (recovery value)
    """

    SPECIAL_SITUATIONS_FORMULA_VERSION = "SPECIAL_SITUATIONS_V1"

    # Control premium benchmarks
    CONTROL_PREMIUM_HISTORICAL_LOW = 0.20  # 20%
    CONTROL_PREMIUM_HISTORICAL_HIGH = 0.40  # 40%
    CONTROL_PREMIUM_HISTORICAL_MEDIAN = 0.30  # 30%

    # Deal probability factors
    STRATEGIC_BUYER_PROBABILITY_BOOST = 0.15  # +15% if strategic buyer exists
    REGULATORY_RISK_DISCOUNT = 0.10  # -10% if major regulatory risk

    @staticmethod
    def model_acquisition(
        target_current_stock_price: float,
        shares_outstanding: float,
        enterprise_value_usd: float,
        strategic_buyer_exists: bool = False,
        synergy_potential_usd: float | None = None,
        regulatory_risk: bool = False,
    ) -> AcquisitionScenario:
        """Model acquisition scenario and valuation."""
        # Control premium
        base_premium = SpecialSituationsEngine.CONTROL_PREMIUM_HISTORICAL_MEDIAN
        if strategic_buyer_exists:
            base_premium += 0.10  # Higher premium with known buyer
        if regulatory_risk:
            base_premium -= SpecialSituationsEngine.REGULATORY_RISK_DISCOUNT

        control_premium = max(0.15, min(0.45, base_premium))  # Clamp to 15-45%
        acquisition_price = target_current_stock_price * (1 + control_premium)

        # Deal probability
        deal_prob = 35  # Base 35%
        if strategic_buyer_exists:
            deal_prob += SpecialSituationsEngine.STRATEGIC_BUYER_PROBABILITY_BOOST * 100
        if regulatory_risk:
            deal_prob -= SpecialSituationsEngine.REGULATORY_RISK_DISCOUNT * 100
        deal_prob = max(10, min(90, deal_prob))

        implied_ev = enterprise_value_usd * (1 + control_premium * 0.5)  # EV moves less than equity

        return AcquisitionScenario(
            target_current_price=target_current_stock_price,
            implied_enterprise_value=implied_ev,
            control_premium_pct=control_premium * 100,
            potential_acquirer_synergies_usd=synergy_potential_usd,
            implied_acquisition_price=acquisition_price,
            implied_price_per_share=acquisition_price,
            upside_to_current_pct=((acquisition_price - target_current_stock_price) / target_current_stock_price) * 100,
            deal_likelihood_pct=deal_prob,
            deal_timing_months=12,
        )

    @staticmethod
    def model_tender_offer(
        current_stock_price: float,
        offer_price_per_share: float | None = None,
        financing_certainty_pct: float = 80,
        regulatory_certainty_pct: float = 90,
    ) -> TenderOfferScenario:
        """Model tender offer (take-private) scenario."""
        if offer_price_per_share is None:
            # Assume 30% premium offer
            offer_price_per_share = current_stock_price * 1.30

        spread = (offer_price_per_share - current_stock_price) / current_stock_price * 100 if current_stock_price > 0 else 0
        # Deal certainty = financing × regulatory
        deal_certainty = (financing_certainty_pct * regulatory_certainty_pct) / 100
        downside_if_fails = -20 if spread > 10 else -10

        return TenderOfferScenario(
            current_stock_price=current_stock_price,
            tender_offer_price_per_share=offer_price_per_share,
            minimum_tender_acceptance_pct=66.0,
            financing_type="CASH" if financing_certainty_pct > 95 else "MIXED",
            deal_certainty_pct=deal_certainty,
            expected_close_timeline_months=6,
            arbitrage_spread_pct=spread,
            downside_if_fails_pct=downside_if_fails,
        )

    @staticmethod
    def model_spinoff(
        parent_current_market_cap: float,
        parent_revenue: float,
        spinco_estimated_revenue: float,
        spinco_margin_estimate_pct: float = 15,
        parent_standalone_margin_pct: float = 20,
    ) -> SpinOffScenario:
        """Model spin-off value creation."""
        # SOTP valuation
        parent_multiple = 15 if parent_standalone_margin_pct > 20 else 12  # P/E multiple
        spinco_multiple = 20 if spinco_margin_estimate_pct > 15 else 15

        parent_ebit = parent_revenue * parent_standalone_margin_pct / 100
        spinco_ebit = spinco_estimated_revenue * spinco_margin_estimate_pct / 100

        parent_implied_value = parent_ebit * parent_multiple
        spinco_implied_value = spinco_ebit * spinco_multiple
        sum_of_parts = parent_implied_value + spinco_implied_value

        value_creation = ((sum_of_parts - parent_current_market_cap) / parent_current_market_cap) * 100

        return SpinOffScenario(
            parent_implied_value=parent_implied_value,
            spinco_implied_value=spinco_implied_value,
            combined_sum_of_parts=sum_of_parts,
            current_parent_market_cap=parent_current_market_cap,
            value_creation_pct=value_creation,
            synergy_loss_estimate=None,
            standalone_viability_score=8,  # Placeholder
            tax_efficiency="TAX_FREE",
        )

    @staticmethod
    def model_restructuring(
        current_equity_value: float,
        total_debt: float,
        enterprise_value: float,
        restructuring_type: str = "CHAPTER_11",
    ) -> RestructuringScenario:
        """Model bankruptcy/restructuring scenarios."""
        # Recovery assumptions
        if restructuring_type == "CHAPTER_11":
            debt_recovery = 0.70  # 70% of debt recovers
            equity_recovery = 0.05  # 5% equity survives
            timeline = 18
        else:  # OUT_OF_COURT
            debt_recovery = 0.80
            equity_recovery = 0.10
            timeline = 12

        equity_value_post = enterprise_value * equity_recovery
        dilution_new_equity = (total_debt * (1 - debt_recovery)) / max(equity_value_post, 1)

        return RestructuringScenario(
            restructuring_type=restructuring_type,
            current_equity_value=current_equity_value,
            equity_value_in_restructuring=equity_value_post,
            debt_recovery_pct=debt_recovery * 100,
            equity_recovery_pct=equity_recovery * 100,
            dilution_from_new_equity_pct=dilution_new_equity * 100,
            timeline_months=timeline,
            emergence_probability_pct=75,
        )

    @staticmethod
    def calculate_special_situations(
        company_id: str,
        fiscal_year: int,
        as_of_date: str,
        situation_type: SpecialSituationType,
        current_stock_price: float,
        base_case_price: float,
        bull_case_price: float | None = None,
        bear_case_price: float | None = None,
        event_probability_pct: float = 50,
        acquisition_scenario: AcquisitionScenario | None = None,
        tender_offer_scenario: TenderOfferScenario | None = None,
        spinoff_scenario: SpinOffScenario | None = None,
        restructuring_scenario: RestructuringScenario | None = None,
    ) -> SpecialSituationResult:
        """Calculate comprehensive special situations analysis."""
        warnings = []

        # Probability bucketing
        if event_probability_pct < 25:
            prob_rating = EventProbability.SPECULATIVE
        elif event_probability_pct < 50:
            prob_rating = EventProbability.POSSIBLE
        elif event_probability_pct < 75:
            prob_rating = EventProbability.LIKELY
        else:
            prob_rating = EventProbability.HIGHLY_LIKELY

        # Expected value (probability-weighted)
        if bull_case_price is None:
            bull_case_price = base_case_price * 1.25
        if bear_case_price is None:
            bear_case_price = base_case_price * 0.80

        expected_value = (
            bear_case_price * (1 - event_probability_pct / 100) +
            bull_case_price * (event_probability_pct / 100)
        )

        # Mispricing assessment
        diff_expected = ((current_stock_price - expected_value) / expected_value) * 100 if expected_value > 0 else 0
        if diff_expected > 5:
            mispricing = "DOWNSIDE"
        elif diff_expected < -5:
            mispricing = "UPSIDE"
        else:
            mispricing = "FAIR"

        # Risk factors
        deal_risks = [
            "Regulatory approval uncertain",
            "Financing contingencies",
            "Shareholder approval risk",
            "Market conditions change",
            "Strategic rationale questioned",
        ]

        # Recommendation
        action = "HOLD"
        if mispricing == "UPSIDE" and event_probability_pct > 40:
            action = "BUY"
        elif mispricing == "DOWNSIDE" and event_probability_pct > 60:
            action = "REDUCE"

        return SpecialSituationResult(
            company_id=company_id,
            fiscal_year=fiscal_year,
            as_of_date=as_of_date,
            situation_type=situation_type,
            event_probability=prob_rating,
            probability_pct=event_probability_pct,
            base_case_price=base_case_price,
            bull_case_price=bull_case_price,
            bear_case_price=bear_case_price,
            expected_value_price=expected_value,
            acquisition_scenario=acquisition_scenario,
            tender_offer_scenario=tender_offer_scenario,
            spinoff_scenario=spinoff_scenario,
            restructuring_scenario=restructuring_scenario,
            deal_risks=deal_risks,
            key_catalysts=[
                "Regulatory announcement",
                "Financing confirmation",
                "Shareholder vote",
                "Integration planning",
            ],
            timeline_milestones=[
                "Q4 2026: Regulatory decision expected",
                "Q1 2027: Financing closed",
                "Q2 2027: Merger closes",
            ],
            current_stock_price=current_stock_price,
            current_price_vs_base_case_pct=((current_stock_price - base_case_price) / base_case_price) * 100,
            current_price_vs_expected_value_pct=diff_expected,
            mispricing_opportunity=mispricing,
            investment_thesis="Event-driven opportunity with asymmetric payoff",
            action=action,
            catalyst_timeline="12 months",
            risk_reward="2:1 upside/downside",
            warnings=warnings,
            formula_version=SpecialSituationsEngine.SPECIAL_SITUATIONS_FORMULA_VERSION,
            calculated_at=datetime.now().isoformat(),
        )
