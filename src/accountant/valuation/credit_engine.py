"""Credit risk engine: leverage, coverage, maturity analysis, and credit scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CreditQuality(StrEnum):
    """Credit quality classification (investment grade to distressed)."""

    VERY_STRONG = "VERY_STRONG"  # Score 85-100
    STRONG = "STRONG"  # Score 65-84
    ADEQUATE = "ADEQUATE"  # Score 45-64
    WEAK = "WEAK"  # Score 25-44
    DISTRESSED = "DISTRESSED"  # Score <25


@dataclass(frozen=True)
class LeverageMetrics:
    """Leverage ratio calculations."""

    gross_debt_usd: float | None
    cash_and_equivalents_usd: float | None
    net_debt_usd: float | None
    ebitda_usd: float | None
    owner_earnings_usd: float | None

    gross_leverage_x: float | None  # Debt / EBITDA
    net_leverage_x: float | None  # Net Debt / EBITDA
    debt_to_fcf_x: float | None  # Debt / Free Cash Flow
    debt_to_owner_earnings_x: float | None  # Debt / Owner Earnings
    net_leverage_conservative_x: float | None  # Debt / Operating CF


@dataclass(frozen=True)
class CoverageMetrics:
    """Debt coverage ratio calculations."""

    interest_expense_usd: float | None
    ebitda_usd: float | None
    operating_cash_flow_usd: float | None
    free_cash_flow_usd: float | None
    owner_earnings_usd: float | None
    current_debt_service_usd: float | None  # Annual payments

    interest_coverage_x: float | None  # EBITDA / Interest Expense
    fcf_coverage_x: float | None  # Free Cash Flow / Interest Expense
    owner_earnings_coverage_x: float | None  # Owner Earnings / Interest Expense
    debt_service_coverage_x: float | None  # Operating CF / (Interest + Principal)


@dataclass(frozen=True)
class MaturityAnalysis:
    """Debt maturity profile."""

    due_within_1_year_usd: float | None
    due_within_1_3_years_usd: float | None
    due_within_3_5_years_usd: float | None
    due_after_5_years_usd: float | None
    total_debt_usd: float | None

    near_term_refinancing_risk: float | None  # % due <1 year
    maturity_concentration_risk: str  # CONCENTRATED, BALANCED, LADDERED
    avg_maturity_years: float | None
    refinancing_needs_next_2yrs_usd: float | None


@dataclass(frozen=True)
class CreditQualityScore:
    """Composite credit quality score (0-100, versioned)."""

    leverage_score: float | None  # 0-25 points
    coverage_score: float | None  # 0-25 points
    liquidity_score: float | None  # 0-25 points
    maturity_score: float | None  # 0-25 points
    total_score: float | None  # Sum of subscores

    quality_classification: CreditQuality | None
    formula_version: str  # CREDIT_QUALITY_V1, etc.


@dataclass(frozen=True)
class CreditRiskResult:
    """Complete credit risk analysis result."""

    company_id: str
    fiscal_year: int
    as_of_date: str

    # Components
    leverage_metrics: LeverageMetrics
    coverage_metrics: CoverageMetrics
    maturity_analysis: MaturityAnalysis
    credit_quality_score: CreditQualityScore

    # Key metrics summary
    primary_leverage_metric: float | None  # Usually net leverage
    primary_coverage_metric: float | None  # Usually interest coverage
    trend_assessment: str  # IMPROVING, STABLE, DETERIORATING

    # Risk factors
    key_risks: list[str]
    key_strengths: list[str]

    # Quality
    data_quality_issues: list[str]

    formula_version: str  # CREDIT_RISK_V1, etc.
    calculated_at: str


class CreditRiskEngine:
    """
    Deterministic credit risk engine.

    Calculates:
    - Leverage ratios (gross, net, debt/FCF, debt/Owner Earnings)
    - Coverage ratios (interest, FCF, Owner Earnings, debt service)
    - Maturity profile and refinancing risk
    - Composite credit quality score (0-100, versioned)

    Uses explicit assumptions:
    - Debt from balance sheet
    - EBITDA = operating income + D&A (conservative)
    - Owner Earnings for cash generation
    - Interest expense from P&L
    """

    CREDIT_RISK_FORMULA_VERSION = "CREDIT_RISK_V1"
    CREDIT_QUALITY_FORMULA_VERSION = "CREDIT_QUALITY_SCORE_V1"

    # Scoring thresholds (leverage component)
    LEVERAGE_EXCELLENT_NET = 1.0  # ≤1.0x net leverage → 25 pts
    LEVERAGE_STRONG_NET = 2.0  # ≤2.0x
    LEVERAGE_ADEQUATE_NET = 3.0  # ≤3.0x
    LEVERAGE_WEAK_NET = 4.0  # ≤4.0x

    # Scoring thresholds (coverage component)
    COVERAGE_EXCELLENT_ICR = 8.0  # ≥8.0x interest coverage → 25 pts
    COVERAGE_STRONG_ICR = 5.0  # ≥5.0x
    COVERAGE_ADEQUATE_ICR = 3.0  # ≥3.0x
    COVERAGE_WEAK_ICR = 1.5  # ≥1.5x

    @staticmethod
    def calculate_leverage_metrics(
        gross_debt_usd: float | None,
        cash_and_equivalents_usd: float | None,
        ebitda_usd: float | None,
        fcf_usd: float | None,
        owner_earnings_usd: float | None,
        operating_cf_usd: float | None,
    ) -> LeverageMetrics:
        """Calculate all leverage ratios."""
        cash = cash_and_equivalents_usd or 0.0
        net_debt = None
        if gross_debt_usd and gross_debt_usd >= 0:
            net_debt = gross_debt_usd - cash

        gross_lev = None
        if ebitda_usd and ebitda_usd > 0 and gross_debt_usd and gross_debt_usd > 0:
            gross_lev = gross_debt_usd / ebitda_usd

        net_lev = None
        if ebitda_usd and ebitda_usd > 0 and net_debt and net_debt > 0:
            net_lev = net_debt / ebitda_usd

        debt_fcf = None
        if fcf_usd and fcf_usd > 0 and gross_debt_usd and gross_debt_usd > 0:
            debt_fcf = gross_debt_usd / fcf_usd

        debt_oe = None
        if owner_earnings_usd and owner_earnings_usd > 0 and gross_debt_usd and gross_debt_usd > 0:
            debt_oe = gross_debt_usd / owner_earnings_usd

        net_lev_conservative = None
        if operating_cf_usd and operating_cf_usd > 0 and net_debt and net_debt > 0:
            net_lev_conservative = net_debt / operating_cf_usd

        return LeverageMetrics(
            gross_debt_usd=gross_debt_usd,
            cash_and_equivalents_usd=cash if cash > 0 else None,
            net_debt_usd=net_debt,
            ebitda_usd=ebitda_usd,
            owner_earnings_usd=owner_earnings_usd,
            gross_leverage_x=gross_lev,
            net_leverage_x=net_lev,
            debt_to_fcf_x=debt_fcf,
            debt_to_owner_earnings_x=debt_oe,
            net_leverage_conservative_x=net_lev_conservative,
        )

    @staticmethod
    def calculate_coverage_metrics(
        interest_expense_usd: float | None,
        ebitda_usd: float | None,
        fcf_usd: float | None,
        owner_earnings_usd: float | None,
        operating_cf_usd: float | None,
        debt_service_usd: float | None,
    ) -> CoverageMetrics:
        """Calculate all coverage ratios."""
        icr = None
        if ebitda_usd and ebitda_usd > 0 and interest_expense_usd and interest_expense_usd > 0:
            icr = ebitda_usd / interest_expense_usd

        fcf_cov = None
        if fcf_usd and fcf_usd > 0 and interest_expense_usd and interest_expense_usd > 0:
            fcf_cov = fcf_usd / interest_expense_usd

        oe_cov = None
        if owner_earnings_usd and owner_earnings_usd > 0 and interest_expense_usd and interest_expense_usd > 0:
            oe_cov = owner_earnings_usd / interest_expense_usd

        dscr = None
        if operating_cf_usd and operating_cf_usd > 0 and debt_service_usd and debt_service_usd > 0:
            dscr = operating_cf_usd / debt_service_usd

        return CoverageMetrics(
            interest_expense_usd=interest_expense_usd,
            ebitda_usd=ebitda_usd,
            operating_cash_flow_usd=operating_cf_usd,
            free_cash_flow_usd=fcf_usd,
            owner_earnings_usd=owner_earnings_usd,
            current_debt_service_usd=debt_service_usd,
            interest_coverage_x=icr,
            fcf_coverage_x=fcf_cov,
            owner_earnings_coverage_x=oe_cov,
            debt_service_coverage_x=dscr,
        )

    @staticmethod
    def calculate_maturity_analysis(
        due_within_1_year_usd: float | None,
        due_within_1_3_years_usd: float | None,
        due_within_3_5_years_usd: float | None,
        due_after_5_years_usd: float | None,
    ) -> MaturityAnalysis:
        """Analyze debt maturity profile."""
        yr1 = due_within_1_year_usd or 0.0
        yr13 = due_within_1_3_years_usd or 0.0
        yr35 = due_within_3_5_years_usd or 0.0
        yr5 = due_after_5_years_usd or 0.0

        total_debt = yr1 + yr13 + yr35 + yr5
        refinancing_next_2yrs = yr1 + (yr13 / 2.0)  # Estimate for year 2

        near_term_pct = None
        if total_debt > 0:
            near_term_pct = (yr1 / total_debt) * 100

        # Concentration: <30% per bucket = balanced
        maturity_type = "BALANCED"
        if total_debt > 0:
            max_bucket = max(yr1, yr13, yr35, yr5) / total_debt
            if max_bucket > 0.5:
                maturity_type = "CONCENTRATED"
            elif max_bucket < 0.20:
                maturity_type = "LADDERED"

        # Average maturity (simplified)
        avg_mat = None
        if total_debt > 0:
            avg_mat = (yr1 * 0.5 + yr13 * 2.0 + yr35 * 4.0 + yr5 * 7.0) / total_debt

        return MaturityAnalysis(
            due_within_1_year_usd=yr1 if yr1 > 0 else None,
            due_within_1_3_years_usd=yr13 if yr13 > 0 else None,
            due_within_3_5_years_usd=yr35 if yr35 > 0 else None,
            due_after_5_years_usd=yr5 if yr5 > 0 else None,
            total_debt_usd=total_debt if total_debt > 0 else None,
            near_term_refinancing_risk=near_term_pct,
            maturity_concentration_risk=maturity_type,
            avg_maturity_years=avg_mat,
            refinancing_needs_next_2yrs_usd=refinancing_next_2yrs if refinancing_next_2yrs > 0 else None,
        )

    @staticmethod
    def score_leverage(net_leverage: float | None) -> float | None:
        """Score leverage component (0-25 points)."""
        if net_leverage is None:
            return None
        if net_leverage <= CreditRiskEngine.LEVERAGE_EXCELLENT_NET:
            return 25.0
        elif net_leverage <= CreditRiskEngine.LEVERAGE_STRONG_NET:
            return 20.0
        elif net_leverage <= CreditRiskEngine.LEVERAGE_ADEQUATE_NET:
            return 15.0
        elif net_leverage <= CreditRiskEngine.LEVERAGE_WEAK_NET:
            return 8.0
        else:
            return 2.0

    @staticmethod
    def score_coverage(interest_coverage: float | None) -> float | None:
        """Score coverage component (0-25 points)."""
        if interest_coverage is None:
            return None
        if interest_coverage >= CreditRiskEngine.COVERAGE_EXCELLENT_ICR:
            return 25.0
        elif interest_coverage >= CreditRiskEngine.COVERAGE_STRONG_ICR:
            return 20.0
        elif interest_coverage >= CreditRiskEngine.COVERAGE_ADEQUATE_ICR:
            return 15.0
        elif interest_coverage >= CreditRiskEngine.COVERAGE_WEAK_ICR:
            return 8.0
        else:
            return 2.0

    @staticmethod
    def score_liquidity(cash_usd: float | None, annual_debt_service: float | None) -> float | None:
        """Score liquidity component (0-25 points)."""
        if not cash_usd or not annual_debt_service or annual_debt_service <= 0:
            return None
        liquidity_coverage = cash_usd / annual_debt_service
        if liquidity_coverage >= 1.5:
            return 25.0
        elif liquidity_coverage >= 1.0:
            return 20.0
        elif liquidity_coverage >= 0.75:
            return 15.0
        elif liquidity_coverage >= 0.5:
            return 8.0
        else:
            return 2.0

    @staticmethod
    def score_maturity(near_term_refinancing_pct: float | None) -> float | None:
        """Score maturity component (0-25 points)."""
        if near_term_refinancing_pct is None:
            return None
        if near_term_refinancing_pct <= 20.0:
            return 25.0
        elif near_term_refinancing_pct <= 30.0:
            return 20.0
        elif near_term_refinancing_pct <= 40.0:
            return 15.0
        elif near_term_refinancing_pct <= 50.0:
            return 8.0
        else:
            return 2.0

    @staticmethod
    def classify_credit_quality(score: float | None) -> CreditQuality | None:
        """Classify credit quality from score."""
        if score is None:
            return None
        if score >= 85:
            return CreditQuality.VERY_STRONG
        elif score >= 65:
            return CreditQuality.STRONG
        elif score >= 45:
            return CreditQuality.ADEQUATE
        elif score >= 25:
            return CreditQuality.WEAK
        else:
            return CreditQuality.DISTRESSED

    @staticmethod
    def calculate_credit_risk(
        company_id: str,
        fiscal_year: int,
        as_of_date: str,
        gross_debt_usd: float | None,
        cash_and_equivalents_usd: float | None,
        ebitda_usd: float | None,
        fcf_usd: float | None,
        owner_earnings_usd: float | None,
        operating_cf_usd: float | None,
        interest_expense_usd: float | None,
        debt_service_annual_usd: float | None,
        due_within_1_year_usd: float | None,
        due_within_1_3_years_usd: float | None,
        due_within_3_5_years_usd: float | None,
        due_after_5_years_usd: float | None,
    ) -> CreditRiskResult:
        """Calculate complete credit risk profile."""
        # Leverage
        leverage = CreditRiskEngine.calculate_leverage_metrics(
            gross_debt_usd=gross_debt_usd,
            cash_and_equivalents_usd=cash_and_equivalents_usd,
            ebitda_usd=ebitda_usd,
            fcf_usd=fcf_usd,
            owner_earnings_usd=owner_earnings_usd,
            operating_cf_usd=operating_cf_usd,
        )

        # Coverage
        coverage = CreditRiskEngine.calculate_coverage_metrics(
            interest_expense_usd=interest_expense_usd,
            ebitda_usd=ebitda_usd,
            fcf_usd=fcf_usd,
            owner_earnings_usd=owner_earnings_usd,
            operating_cf_usd=operating_cf_usd,
            debt_service_usd=debt_service_annual_usd,
        )

        # Maturity
        maturity = CreditRiskEngine.calculate_maturity_analysis(
            due_within_1_year_usd=due_within_1_year_usd,
            due_within_1_3_years_usd=due_within_1_3_years_usd,
            due_within_3_5_years_usd=due_within_3_5_years_usd,
            due_after_5_years_usd=due_after_5_years_usd,
        )

        # Scoring
        lev_score = CreditRiskEngine.score_leverage(leverage.net_leverage_x)
        cov_score = CreditRiskEngine.score_coverage(coverage.interest_coverage_x)
        liq_score = CreditRiskEngine.score_liquidity(cash_and_equivalents_usd, debt_service_annual_usd)
        mat_score = CreditRiskEngine.score_maturity(maturity.near_term_refinancing_risk)

        total_score = None
        if all([lev_score is not None, cov_score is not None, liq_score is not None, mat_score is not None]):
            total_score = lev_score + cov_score + liq_score + mat_score

        credit_quality = CreditRiskEngine.classify_credit_quality(total_score)

        cq_score = CreditQualityScore(
            leverage_score=lev_score,
            coverage_score=cov_score,
            liquidity_score=liq_score,
            maturity_score=mat_score,
            total_score=total_score,
            quality_classification=credit_quality,
            formula_version=CreditRiskEngine.CREDIT_QUALITY_FORMULA_VERSION,
        )

        # Assessment
        primary_lev = leverage.net_leverage_x
        primary_cov = coverage.interest_coverage_x
        trend = "STABLE"

        risks = []
        if primary_lev and primary_lev > 3.0:
            risks.append(f"High leverage: {primary_lev:.1f}x net debt/EBITDA")
        if primary_cov and primary_cov < 3.0:
            risks.append(f"Weak coverage: {primary_cov:.1f}x interest coverage")
        if maturity.near_term_refinancing_risk and maturity.near_term_refinancing_risk > 40:
            risks.append(f"Refinancing concentration: {maturity.near_term_refinancing_risk:.0f}% due <1yr")

        strengths = []
        if primary_lev and primary_lev < 2.0:
            strengths.append(f"Conservative leverage: {primary_lev:.1f}x")
        if primary_cov and primary_cov > 6.0:
            strengths.append(f"Strong coverage: {primary_cov:.1f}x")

        data_issues = []
        if not ebitda_usd:
            data_issues.append("Missing EBITDA")
        if not interest_expense_usd:
            data_issues.append("Missing interest expense")

        return CreditRiskResult(
            company_id=company_id,
            fiscal_year=fiscal_year,
            as_of_date=as_of_date,
            leverage_metrics=leverage,
            coverage_metrics=coverage,
            maturity_analysis=maturity,
            credit_quality_score=cq_score,
            primary_leverage_metric=primary_lev,
            primary_coverage_metric=primary_cov,
            trend_assessment=trend,
            key_risks=risks,
            key_strengths=strengths,
            data_quality_issues=data_issues,
            formula_version=CreditRiskEngine.CREDIT_RISK_FORMULA_VERSION,
            calculated_at=datetime.now().isoformat(),
        )
