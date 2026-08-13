"""Deterministic fundamental research classification engine (NOT trading signals)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class ResearchClassification(StrEnum):
    """Fundamental research classification statuses (NOT trading actions)."""

    CORE_RESEARCH_CANDIDATE = "CORE_RESEARCH_CANDIDATE"  # High-conviction thesis worthy
    HIGH_QUALITY = "HIGH_QUALITY"  # Quality metrics strong
    ATTRACTIVE_VALUATION = "ATTRACTIVE_VALUATION"  # Valuation compelling
    WATCHLIST = "WATCHLIST"  # Monitor for future opportunity
    FAIRLY_VALUED = "FAIRLY_VALUED"  # Fair price, no margin of safety
    EXPENSIVE = "EXPENSIVE"  # Valuation premium to fundamentals
    DETERIORATING = "DETERIORATING"  # Metrics declining
    CREDIT_CONCERN = "CREDIT_CONCERN"  # Debt/leverage problematic
    FORENSIC_CONCERN = "FORENSIC_CONCERN"  # Accounting red flags
    REJECTED_BY_RULES = "REJECTED_BY_RULES"  # Fails fundamental screen
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Missing critical data


@dataclass(frozen=True)
class ClassificationRule:
    """Single deterministic rule that supports a classification."""

    rule_id: str  # Unique identifier
    rule_name: str  # Human-readable name
    metric_name: str  # What metric this tests
    operator: str  # "gt" (>), "lt" (<), "gte" (>=), "lte" (<=), "eq" (==), "in"
    threshold: float | str | list  # Threshold value(s)
    actual_value: float | str | None  # Actual metric value
    triggered: bool  # Whether this rule triggered
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"


@dataclass(frozen=True)
class FundamentalResearchRecord:
    """Historical research classification for a company at a point in time."""

    company_id: str
    as_of_date: str  # YYYY-MM-DD (research date)

    # Classification
    classification: ResearchClassification
    rules_triggered: list[ClassificationRule]  # Rules that triggered
    rules_failed: list[ClassificationRule]  # Rules that did not trigger

    # Key metrics (supporting the classification)
    accounting_quality_score: float | None  # 0-100
    owner_earnings_yield_pct: float | None  # Owner Earnings / Market Cap
    owner_earnings_growth_pct: float | None  # YoY growth
    roic_pct: float | None  # Return on Invested Capital
    incremental_roic_pct: float | None  # ROIC on incremental capital
    capital_allocation_score: float | None  # 0-100
    credit_quality_score: float | None  # 0-100
    bear_case_risk_score: float | None  # 0-100 downside risk
    forensic_risk_score: float | None  # 0-100 accounting red flags
    valuation_range_low: float | None  # Intrinsic value low end
    valuation_range_high: float | None  # Intrinsic value high end
    current_price: float | None  # Market price at as_of_date
    margin_of_safety_pct: float | None  # Upside/downside to valuation
    peer_rank_quality: int | None  # Percentile rank vs peers (0-100)
    peer_rank_growth: int | None
    peer_rank_valuation: int | None
    peer_rank_safety: int | None

    # Warnings/notes
    warnings: list[str]
    classification_notes: str

    # Versioning
    rule_version: str  # FUNDAMENTAL_RESEARCH_CLASSIFICATION_V1
    feature_versions: dict[str, str]  # Map of feature_name -> version
    created_at: str  # ISO timestamp


@dataclass(frozen=True)
class ClassificationRuleSet:
    """Set of rules for a classification (versioned, immutable)."""

    version: str  # e.g., "FUNDAMENTAL_RESEARCH_CLASSIFICATION_V1"
    classification: ResearchClassification
    rules: list[ClassificationRule]
    weight: float  # Rule importance (0-1)
    description: str


class FundamentalResearchClassificationEngine:
    """Deterministic fundamental research classification (NOT trading)."""

    FUNDAMENTAL_RESEARCH_CLASSIFICATION_VERSION = "FUNDAMENTAL_RESEARCH_CLASSIFICATION_V1"

    # Quality thresholds
    HIGH_QUALITY_ACCOUNTING_QUALITY_MIN = 70  # 0-100
    HIGH_QUALITY_FORENSIC_RISK_MAX = 30  # 0-100 (lower = safer)
    HIGH_QUALITY_DILUTION_MAX = 10  # % annual dilution
    HIGH_QUALITY_ACCOUNTING_EARNINGS_CREDIBILITY_MIN = 0.80  # 0-1 ratio

    # Growth thresholds
    ATTRACTIVE_GROWTH_OE_GROWTH_MIN_PCT = 10  # YoY Owner Earnings growth
    ATTRACTIVE_GROWTH_ROIC_MIN_PCT = 12  # Incremental ROIC
    ATTRACTIVE_GROWTH_EBITDA_GROWTH_MIN_PCT = 8

    # Valuation thresholds
    ATTRACTIVE_VALUATION_MARGIN_OF_SAFETY_MIN_PCT = 30  # Upside to base case
    ATTRACTIVE_VALUATION_YIELD_MIN_PCT = 6  # OE Yield
    ATTRACTIVE_VALUATION_PB_MAX = 3.0  # Price-to-Book
    ATTRACTIVE_VALUATION_PE_MAX = 15  # Price-to-Earnings

    # Quality + Value combination
    QUALITY_PLUS_VALUE_QUALITY_MIN = 65
    QUALITY_PLUS_VALUE_ROIC_MIN_PCT = 10
    QUALITY_PLUS_VALUE_MARGIN_MIN_PCT = 20  # Valuation discount

    # Deterioration signals
    DETERIORATING_ROIC_DECLINE_MIN_PCT = -5  # Drop in ROIC
    DETERIORATING_REVENUE_DECLINE_MIN_PCT = -5
    DETERIORATING_MARGIN_DECLINE_MIN_BPS = -200  # Basis points

    # Credit concern
    CREDIT_CONCERN_LEVERAGE_MAX = 4.0  # Net Debt / EBITDA
    CREDIT_CONCERN_INTEREST_COVERAGE_MIN = 1.5  # EBIT / Interest
    CREDIT_CONCERN_FCF_COVERAGE_MIN = 1.0  # FCF / Debt Service

    # Forensic concern
    FORENSIC_CONCERN_RISK_MIN = 50  # 0-100 score

    # Rejection screens
    REJECT_IF_NEGATIVE_FCF = True
    REJECT_IF_DECLINING_REVENUE = True  # 2+ years
    REJECT_IF_ACCOUNTING_QUALITY_LT = 40

    @staticmethod
    def classify(
        company_id: str,
        as_of_date: str,
        accounting_quality_score: float | None = None,
        owner_earnings_yield_pct: float | None = None,
        owner_earnings_growth_pct: float | None = None,
        roic_pct: float | None = None,
        incremental_roic_pct: float | None = None,
        capital_allocation_score: float | None = None,
        credit_quality_score: float | None = None,
        bear_case_risk_score: float | None = None,
        forensic_risk_score: float | None = None,
        valuation_range_low: float | None = None,
        valuation_range_high: float | None = None,
        current_price: float | None = None,
        peer_rank_quality: int | None = None,
        peer_rank_growth: int | None = None,
        peer_rank_valuation: int | None = None,
        peer_rank_safety: int | None = None,
        negative_fcf: bool = False,
        declining_revenue: bool = False,
    ) -> FundamentalResearchRecord:
        """
        Classify company using deterministic versioned rules.

        Returns research classification (NOT trading signal) with full
        explainability: which rules triggered, which failed, why.

        Args:
            company_id: Company identifier
            as_of_date: Classification date (YYYY-MM-DD)
            Various metric inputs
            negative_fcf: Whether FCF is negative
            declining_revenue: Whether revenue declining 2+ years

        Returns:
            FundamentalResearchRecord with classification and rule details
        """
        rules_triggered = []
        rules_failed = []

        # Rule 1: Rejection screen - negative FCF
        if negative_fcf:
            rules_triggered.append(
                ClassificationRule(
                    rule_id="REJECT_FCF",
                    rule_name="Negative Free Cash Flow",
                    metric_name="FCF",
                    operator="lt",
                    threshold=0,
                    actual_value=None,
                    triggered=True,
                    severity="CRITICAL",
                )
            )

        # Rule 2: Rejection screen - declining revenue
        if declining_revenue:
            rules_triggered.append(
                ClassificationRule(
                    rule_id="REJECT_REVENUE",
                    rule_name="Declining Revenue 2+ Years",
                    metric_name="Revenue",
                    operator="lt",
                    threshold=0,
                    actual_value=None,
                    triggered=True,
                    severity="CRITICAL",
                )
            )

        # Rule 3: Accounting quality screen
        if (
            accounting_quality_score is not None
            and accounting_quality_score < FundamentalResearchClassificationEngine.REJECT_IF_ACCOUNTING_QUALITY_LT
        ):
            rules_triggered.append(
                ClassificationRule(
                    rule_id="REJECT_QUALITY",
                    rule_name="Accounting Quality Too Low",
                    metric_name="Accounting Quality Score",
                    operator="lt",
                    threshold=40,
                    actual_value=accounting_quality_score,
                    triggered=True,
                    severity="HIGH",
                )
            )

        # Determine classification
        if rules_triggered:
            classification = ResearchClassification.REJECTED_BY_RULES
        elif (
            accounting_quality_score
            and accounting_quality_score >= FundamentalResearchClassificationEngine.HIGH_QUALITY_ACCOUNTING_QUALITY_MIN
            and forensic_risk_score
            and forensic_risk_score <= FundamentalResearchClassificationEngine.HIGH_QUALITY_FORENSIC_RISK_MAX
        ):
            classification = ResearchClassification.HIGH_QUALITY
        elif (
            valuation_range_low
            and current_price
            and (valuation_range_high - current_price) / current_price >= 0.30
        ):
            classification = ResearchClassification.ATTRACTIVE_VALUATION
        elif (
            valuation_range_high
            and current_price
            and current_price > valuation_range_high * 1.15
        ):
            classification = ResearchClassification.EXPENSIVE
        elif accounting_quality_score is None or owner_earnings_yield_pct is None:
            classification = ResearchClassification.INSUFFICIENT_DATA
        else:
            classification = ResearchClassification.WATCHLIST

        # Calculate margin of safety
        margin_of_safety_pct = None
        if valuation_range_high and current_price and current_price > 0:
            margin_of_safety_pct = (
                (valuation_range_high - current_price) / current_price
            ) * 100

        return FundamentalResearchRecord(
            company_id=company_id,
            as_of_date=as_of_date,
            classification=classification,
            rules_triggered=rules_triggered,
            rules_failed=rules_failed,
            accounting_quality_score=accounting_quality_score,
            owner_earnings_yield_pct=owner_earnings_yield_pct,
            owner_earnings_growth_pct=owner_earnings_growth_pct,
            roic_pct=roic_pct,
            incremental_roic_pct=incremental_roic_pct,
            capital_allocation_score=capital_allocation_score,
            credit_quality_score=credit_quality_score,
            bear_case_risk_score=bear_case_risk_score,
            forensic_risk_score=forensic_risk_score,
            valuation_range_low=valuation_range_low,
            valuation_range_high=valuation_range_high,
            current_price=current_price,
            margin_of_safety_pct=margin_of_safety_pct,
            peer_rank_quality=peer_rank_quality,
            peer_rank_growth=peer_rank_growth,
            peer_rank_valuation=peer_rank_valuation,
            peer_rank_safety=peer_rank_safety,
            warnings=[],
            classification_notes="Research classification, not trading signal",
            rule_version=FundamentalResearchClassificationEngine.FUNDAMENTAL_RESEARCH_CLASSIFICATION_VERSION,
            feature_versions={},
            created_at=datetime.now().isoformat(),
        )
