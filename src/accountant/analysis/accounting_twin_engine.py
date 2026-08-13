"""Accounting twin engine comparing reported vs. economic books."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class ReportedVsEconomicMetric(StrEnum):
    """Key metrics compared between reported and economic books."""

    REVENUE = "REVENUE"
    OPERATING_INCOME = "OPERATING_INCOME"
    NET_INCOME = "NET_INCOME"
    OPERATING_CASH_FLOW = "OPERATING_CASH_FLOW"
    TOTAL_DEBT = "TOTAL_DEBT"
    EQUITY = "EQUITY"
    ROE = "ROE"
    ROIC = "ROIC"
    EBITDA = "EBITDA"
    FREE_CASH_FLOW = "FREE_CASH_FLOW"


class AccountingAggressiveness(StrEnum):
    """Classification of reported vs. economic divergence."""

    CONSERVATIVE = "CONSERVATIVE"  # Reported < Economic (under-reporting)
    NEUTRAL = "NEUTRAL"  # Reported ≈ Economic (within tolerance)
    MODERATE = "MODERATE"  # Reported > Economic (modest gap)
    AGGRESSIVE = "AGGRESSIVE"  # Reported > Economic (significant gap)
    HIGHLY_AGGRESSIVE = "HIGHLY_AGGRESSIVE"  # Reported > Economic (extreme gap)


@dataclass(frozen=True)
class ReportedEconomicDifference:
    """Reconciliation between reported and economic metric."""

    company_id: str
    fiscal_year: int
    metric_name: str

    # Values
    reported_value: float | None
    economic_value: float | None

    # Difference
    absolute_difference: float | None
    percentage_difference: float | None  # (Reported - Economic) / Economic
    aggressiveness: AccountingAggressiveness

    # Driver analysis
    drivers: list[str]  # Policy differences, estimates, one-time items
    policy_adjustments: dict[str, float]  # e.g., {"inventory_lifo_to_fifo": 50}

    # Assessment
    reason: str  # Plain English explanation
    formula_version: str  # V1_ACCOUNTING_TWIN


@dataclass(frozen=True)
class AccountingTwinReport:
    """Complete reported vs. economic comparison."""

    company_id: str
    fiscal_year: int
    analysis_date: str

    # Metrics compared
    metric_reconciliations: list[ReportedEconomicDifference]
    total_metrics: int

    # Divergence summary
    average_divergence: float  # Average % difference across metrics
    max_divergence: float  # Largest % difference
    aggressiveness_score: float  # 0-100 (higher = more aggressive)

    # Overall assessment
    overall_aggressiveness: AccountingAggressiveness
    key_drivers: list[str]  # Top divergence causes
    recommendation: str  # Follow-up actions


class AccountingTwinEngine:
    """
    Compare reported accounting book vs. economic book.

    Core principle: Identify policy choices and estimate differences
    that create divergence between reported and economic earnings.
    """

    TOLERANCE_PCT = 5.0  # Percent difference considered "neutral"
    AGGRESSIVE_THRESHOLD = 15.0  # Percent difference = aggressive

    @staticmethod
    def reconcile_metric(
        company_id: str,
        fiscal_year: int,
        metric_name: str,
        reported_value: float | None,
        economic_value: float | None,
    ) -> ReportedEconomicDifference:
        """
        Reconcile reported vs. economic value for single metric.

        Input: Reported and economic metric values
        Output: Difference with aggressiveness classification
        """
        if reported_value is None or economic_value is None:
            return ReportedEconomicDifference(
                company_id=company_id,
                fiscal_year=fiscal_year,
                metric_name=metric_name,
                reported_value=reported_value,
                economic_value=economic_value,
                absolute_difference=None,
                percentage_difference=None,
                aggressiveness=AccountingAggressiveness.NEUTRAL,
                drivers=[],
                policy_adjustments={},
                reason="Insufficient data for comparison",
                formula_version="V1_ACCOUNTING_TWIN",
            )

        # Calculate differences
        abs_diff = reported_value - economic_value
        pct_diff = (abs_diff / abs(economic_value)) * 100 if economic_value != 0 else 0.0

        # Classify aggressiveness
        if pct_diff < 0:
            aggressiveness = AccountingAggressiveness.CONSERVATIVE
            reason = f"Reported {pct_diff:.1f}% below economic ({abs_diff:.0f})"
        elif abs(pct_diff) <= AccountingTwinEngine.TOLERANCE_PCT:
            aggressiveness = AccountingAggressiveness.NEUTRAL
            reason = f"Reported within {AccountingTwinEngine.TOLERANCE_PCT}% of economic"
        elif pct_diff <= AccountingTwinEngine.AGGRESSIVE_THRESHOLD:
            aggressiveness = AccountingAggressiveness.MODERATE
            reason = f"Reported {pct_diff:.1f}% above economic (policy gap)"
        elif pct_diff <= 30.0:
            aggressiveness = AccountingAggressiveness.AGGRESSIVE
            reason = f"Reported {pct_diff:.1f}% above economic (significant gap)"
        else:
            aggressiveness = AccountingAggressiveness.HIGHLY_AGGRESSIVE
            reason = f"Reported {pct_diff:.1f}% above economic (extreme gap)"

        return ReportedEconomicDifference(
            company_id=company_id,
            fiscal_year=fiscal_year,
            metric_name=metric_name,
            reported_value=reported_value,
            economic_value=economic_value,
            absolute_difference=abs_diff,
            percentage_difference=pct_diff,
            aggressiveness=aggressiveness,
            drivers=[reason],
            policy_adjustments={},
            reason=reason,
            formula_version="V1_ACCOUNTING_TWIN",
        )

    @staticmethod
    def run_twin_analysis(
        company_id: str,
        fiscal_year: int,
        reported_metrics: dict[str, float | None],
        economic_metrics: dict[str, float | None],
    ) -> AccountingTwinReport:
        """
        Complete twin analysis comparing reported vs. economic books.

        Input: Company, year, reported metrics, economic metrics
        Output: AccountingTwinReport with reconciliations and aggressiveness
        """
        reconciliations = []

        # Reconcile each metric
        for metric_name in reported_metrics:
            reported_val = reported_metrics.get(metric_name)
            economic_val = economic_metrics.get(metric_name)

            recon = AccountingTwinEngine.reconcile_metric(
                company_id=company_id,
                fiscal_year=fiscal_year,
                metric_name=metric_name,
                reported_value=reported_val,
                economic_value=economic_val,
            )
            reconciliations.append(recon)

        # Calculate aggregate statistics
        valid_reconciliations = [
            r
            for r in reconciliations
            if r.percentage_difference is not None
        ]
        if valid_reconciliations:
            avg_divergence = sum(
                r.percentage_difference for r in valid_reconciliations
            ) / len(valid_reconciliations)
            max_divergence = max(
                abs(r.percentage_difference) for r in valid_reconciliations
            )
        else:
            avg_divergence = 0.0
            max_divergence = 0.0

        # Aggressiveness score
        aggressive_count = sum(
            1
            for r in reconciliations
            if r.aggressiveness
            in (
                AccountingAggressiveness.AGGRESSIVE,
                AccountingAggressiveness.HIGHLY_AGGRESSIVE,
            )
        )
        aggressiveness_score = min(100, aggressive_count * 20 + max_divergence)

        # Overall classification
        if aggressive_count > 0:
            overall = AccountingAggressiveness.AGGRESSIVE
        elif any(
            r.aggressiveness == AccountingAggressiveness.MODERATE
            for r in reconciliations
        ):
            overall = AccountingAggressiveness.MODERATE
        elif any(
            r.aggressiveness == AccountingAggressiveness.CONSERVATIVE
            for r in reconciliations
        ):
            overall = AccountingAggressiveness.CONSERVATIVE
        else:
            overall = AccountingAggressiveness.NEUTRAL

        # Key drivers
        key_drivers = []
        for recon in sorted(
            reconciliations,
            key=lambda r: abs(r.percentage_difference) if r.percentage_difference else 0,
            reverse=True,
        )[:3]:
            if recon.percentage_difference:
                key_drivers.append(
                    f"{recon.metric_name}: {recon.percentage_difference:.1f}%"
                )

        # Recommendation
        if aggressiveness_score > 50:
            recommendation = (
                "HIGH PRIORITY: Significant divergence detected. "
                "Review accounting policies and estimates. "
                "Reported earnings may exceed sustainable economic earnings."
            )
        elif aggressiveness_score > 25:
            recommendation = (
                "MEDIUM PRIORITY: Moderate divergence between reported and economic. "
                "Review policy choices (LIFO/FIFO, depreciation, etc.)."
            )
        else:
            recommendation = (
                "Reported and economic books closely aligned. Accounting quality is high."
            )

        return AccountingTwinReport(
            company_id=company_id,
            fiscal_year=fiscal_year,
            analysis_date="2026-08-12",
            metric_reconciliations=reconciliations,
            total_metrics=len(reconciliations),
            average_divergence=avg_divergence,
            max_divergence=max_divergence,
            aggressiveness_score=aggressiveness_score,
            overall_aggressiveness=overall,
            key_drivers=key_drivers,
            recommendation=recommendation,
        )
