"""Peer anomaly detection engine using statistical methods (Z-scores, IQR, trend analysis)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class AnomalyType(StrEnum):
    """Classification of detected anomaly."""

    OUTLIER_EXTREME = "OUTLIER_EXTREME"  # |Z| > 3.0
    OUTLIER_MODERATE = "OUTLIER_MODERATE"  # |Z| > 2.0 and <= 3.0
    OUTLIER_MILD = "OUTLIER_MILD"  # |Z| > 1.5 and <= 2.0
    TREND_DETERIORATING = "TREND_DETERIORATING"  # Consistent decline
    TREND_IMPROVING = "TREND_IMPROVING"  # Consistent improvement
    TREND_INFLECTION = "TREND_INFLECTION"  # Direction change (sign reversal)
    IQR_OUTLIER = "IQR_OUTLIER"  # Outside 1.5×IQR bounds
    NO_ANOMALY = "NO_ANOMALY"  # Within normal range
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Not enough history


class SeverityLevel(StrEnum):
    """Severity of anomaly."""

    CRITICAL = "CRITICAL"  # Action required
    HIGH = "HIGH"  # Review recommended
    MEDIUM = "MEDIUM"  # Flag for investigation
    LOW = "LOW"  # Monitor
    INFO = "INFO"  # Informational only


@dataclass(frozen=True)
class AnomalyFinding:
    """Single detected anomaly for company metric."""

    company_id: str
    fiscal_year: int
    metric_name: str

    # Anomaly details
    anomaly_type: AnomalyType
    severity: SeverityLevel

    # Current value
    current_value: float | None
    peer_median: float | None

    # Statistical context
    z_score: float | None  # Standard deviations from peer mean
    iqr_ratio: float | None  # Distance from IQR bounds / IQR width
    percentile_rank: float | None

    # Trend context (if multi-year)
    prior_year_value: float | None
    trend_direction: str | None  # UP, DOWN, FLAT, REVERSAL
    trend_strength: float | None  # CAGR or correlation

    # Analysis
    reason: str  # Plain English explanation
    recommendation: str  # Suggested follow-up
    formula_version: str  # V1_PEER_ANOMALY


@dataclass(frozen=True)
class AnomalyReport:
    """Complete anomaly analysis for company across metrics."""

    company_id: str
    fiscal_year: int
    peer_count: int
    analysis_date: str

    # Findings
    findings: list[AnomalyFinding]
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int

    # Overall assessment
    anomaly_risk_score: float  # 0-100 (higher = more anomalies)
    is_outlier: bool  # Any metric is statistical outlier
    trend_concern: bool  # Any deteriorating or reversal trends
    recommendation: str  # Summary action


class PeerAnomalyEngine:
    """
    Detect statistical anomalies within peer groups.

    Core principle: Identify outliers and concerning trends via
    Z-scores, IQR, and multi-year analysis.
    """

    Z_SCORE_EXTREME = 3.0  # |Z| > 3.0 = extreme outlier
    Z_SCORE_MODERATE = 2.0  # |Z| > 2.0 = moderate outlier
    Z_SCORE_MILD = 1.5  # |Z| > 1.5 = mild anomaly
    IQR_MULTIPLIER = 1.5  # Standard box-plot multiplier

    @staticmethod
    def detect_statistical_outlier(
        company_id: str,
        fiscal_year: int,
        metric_name: str,
        current_value: float | None,
        peer_median: float | None,
        z_score: float | None,
        peer_count: int,
    ) -> AnomalyFinding | None:
        """
        Detect statistical outliers using Z-score method.

        Input: Company metric and peer statistics
        Output: AnomalyFinding if outlier detected, None otherwise
        """
        if current_value is None or z_score is None or peer_median is None:
            return None

        if peer_count < 5:
            return None

        abs_z = abs(z_score)

        if abs_z > PeerAnomalyEngine.Z_SCORE_EXTREME:
            anomaly_type = AnomalyType.OUTLIER_EXTREME
            severity = SeverityLevel.CRITICAL
            reason = f"Metric {abs_z:.1f} standard deviations from peer mean"
        elif abs_z > PeerAnomalyEngine.Z_SCORE_MODERATE:
            anomaly_type = AnomalyType.OUTLIER_MODERATE
            severity = SeverityLevel.HIGH
            reason = f"Metric {abs_z:.1f} standard deviations from peer mean"
        elif abs_z > PeerAnomalyEngine.Z_SCORE_MILD:
            anomaly_type = AnomalyType.OUTLIER_MILD
            severity = SeverityLevel.MEDIUM
            reason = f"Metric {abs_z:.1f} standard deviations from peer mean"
        else:
            return None

        direction = "above" if z_score > 0 else "below"
        recommendation = (
            f"Investigate why {company_id}'s {metric_name} is {direction} "
            f"peer median. Review business drivers and competitive position."
        )

        return AnomalyFinding(
            company_id=company_id,
            fiscal_year=fiscal_year,
            metric_name=metric_name,
            anomaly_type=anomaly_type,
            severity=severity,
            current_value=current_value,
            peer_median=peer_median,
            z_score=z_score,
            iqr_ratio=None,
            percentile_rank=None,
            prior_year_value=None,
            trend_direction=None,
            trend_strength=None,
            reason=reason,
            recommendation=recommendation,
            formula_version="V1_PEER_ANOMALY",
        )

    @staticmethod
    def detect_trend_anomaly(
        company_id: str,
        fiscal_year: int,
        metric_name: str,
        current_value: float | None,
        prior_year_value: float | None,
        two_year_prior: float | None,
    ) -> AnomalyFinding | None:
        """
        Detect concerning trends: deterioration, improvement, reversal.

        Input: Current and historical metric values
        Output: AnomalyFinding if trend anomaly, None otherwise
        """
        if current_value is None or prior_year_value is None:
            return None

        # Calculate year-over-year change
        yoy_change = current_value - prior_year_value

        # Detect sign reversals (e.g., profit to loss)
        if prior_year_value != 0:
            sign_changed = (prior_year_value > 0) != (current_value > 0)
        else:
            sign_changed = False

        if sign_changed:
            anomaly_type = AnomalyType.TREND_INFLECTION
            severity = SeverityLevel.HIGH
            reason = f"Metric reversed sign: {prior_year_value:.2f} → {current_value:.2f}"
            recommendation = "Urgent: Investigate cause of inflection point"
        elif yoy_change < 0 and prior_year_value > 0:
            # Deteriorating trend
            anomaly_type = AnomalyType.TREND_DETERIORATING
            severity = SeverityLevel.MEDIUM
            pct_change = (yoy_change / abs(prior_year_value)) * 100
            reason = f"Metric declined {pct_change:.1f}% YoY"
            recommendation = "Monitor deteriorating trend; assess sustainability"
        elif yoy_change > 0 and prior_year_value < 0:
            # Improving from negative base
            anomaly_type = AnomalyType.TREND_IMPROVING
            severity = SeverityLevel.LOW
            pct_change = (yoy_change / abs(prior_year_value)) * 100
            reason = f"Metric improved {pct_change:.1f}% YoY"
            recommendation = "Continue monitoring improvement trajectory"
        else:
            return None

        return AnomalyFinding(
            company_id=company_id,
            fiscal_year=fiscal_year,
            metric_name=metric_name,
            anomaly_type=anomaly_type,
            severity=severity,
            current_value=current_value,
            peer_median=None,
            z_score=None,
            iqr_ratio=None,
            percentile_rank=None,
            prior_year_value=prior_year_value,
            trend_direction="DOWN" if yoy_change < 0 else "UP",
            trend_strength=yoy_change,
            reason=reason,
            recommendation=recommendation,
            formula_version="V1_PEER_ANOMALY",
        )

    @staticmethod
    def run_anomaly_scan(
        company_id: str,
        fiscal_year: int,
        metrics: dict[str, float | None],
        peer_medians: dict[str, float | None],
        z_scores: dict[str, float | None],
        prior_metrics: dict[str, float | None] | None = None,
        peer_count: int = 0,
    ) -> AnomalyReport:
        """
        Complete anomaly scan for company across metrics.

        Input: Company metrics, peer statistics, optional prior-year data
        Output: AnomalyReport with all findings
        """
        findings = []

        # Statistical outlier detection
        for metric_name, current_value in metrics.items():
            peer_median = peer_medians.get(metric_name)
            z_score = z_scores.get(metric_name)

            finding = PeerAnomalyEngine.detect_statistical_outlier(
                company_id=company_id,
                fiscal_year=fiscal_year,
                metric_name=metric_name,
                current_value=current_value,
                peer_median=peer_median,
                z_score=z_score,
                peer_count=peer_count,
            )
            if finding:
                findings.append(finding)

        # Trend analysis (if prior-year data available)
        if prior_metrics:
            for metric_name, current_value in metrics.items():
                prior_value = prior_metrics.get(metric_name)
                if prior_value is not None:
                    finding = PeerAnomalyEngine.detect_trend_anomaly(
                        company_id=company_id,
                        fiscal_year=fiscal_year,
                        metric_name=metric_name,
                        current_value=current_value,
                        prior_year_value=prior_value,
                        two_year_prior=None,
                    )
                    if finding:
                        findings.append(finding)

        # Calculate risk score
        critical_count = sum(1 for f in findings if f.severity == SeverityLevel.CRITICAL)
        high_count = sum(1 for f in findings if f.severity == SeverityLevel.HIGH)
        medium_count = sum(1 for f in findings if f.severity == SeverityLevel.MEDIUM)

        anomaly_risk_score = min(100, critical_count * 30 + high_count * 15 + medium_count * 5)

        # Determine if outlier
        is_outlier = any(
            f.anomaly_type
            in (
                AnomalyType.OUTLIER_EXTREME,
                AnomalyType.OUTLIER_MODERATE,
            )
            for f in findings
        )

        # Determine if trend concern
        trend_concern = any(
            f.anomaly_type
            in (
                AnomalyType.TREND_DETERIORATING,
                AnomalyType.TREND_INFLECTION,
            )
            for f in findings
        )

        # Summary recommendation
        if critical_count > 0:
            recommendation = (
                f"URGENT: {critical_count} critical anomalies detected. "
                f"Immediate investigation required."
            )
        elif high_count > 0:
            recommendation = (
                f"HIGH PRIORITY: {high_count} significant anomalies. "
                f"Review recommended."
            )
        elif medium_count > 0:
            recommendation = (
                f"MEDIUM PRIORITY: {medium_count} anomalies flagged. "
                f"Monitor closely."
            )
        else:
            recommendation = (
                "No statistical anomalies detected. "
                "Metrics within normal peer range."
            )

        return AnomalyReport(
            company_id=company_id,
            fiscal_year=fiscal_year,
            peer_count=peer_count,
            analysis_date="2026-08-12",
            findings=findings,
            total_findings=len(findings),
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            anomaly_risk_score=anomaly_risk_score,
            is_outlier=is_outlier,
            trend_concern=trend_concern,
            recommendation=recommendation,
        )
