"""Research data quality tracking and reporting engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class DataQualityTier(StrEnum):
    """Data quality tier classification."""

    COMPLETE = "COMPLETE"  # 100% of expected data available
    COMPREHENSIVE = "COMPREHENSIVE"  # 85-99% available
    SUBSTANTIAL = "SUBSTANTIAL"  # 70-84% available
    ADEQUATE = "ADEQUATE"  # 50-69% available
    INSUFFICIENT = "INSUFFICIENT"  # <50% available


class CoverageMetric(StrEnum):
    """Types of data coverage metrics."""

    FILING_COVERAGE = "FILING_COVERAGE"  # % of expected filings present
    STATEMENT_COMPLETENESS = "STATEMENT_COMPLETENESS"  # % of statements reconstructible
    FACT_COVERAGE = "FACT_COVERAGE"  # % of XBRL facts populated
    CANONICAL_MAPPING_COVERAGE = "CANONICAL_MAPPING_COVERAGE"  # % mapped to canonical
    METRIC_AVAILABILITY = "METRIC_AVAILABILITY"  # % of research metrics calculable
    HISTORICAL_DEPTH = "HISTORICAL_DEPTH"  # Years of historical data available
    PEER_COVERAGE = "PEER_COVERAGE"  # % of peer companies available


@dataclass(frozen=True)
class CoverageScore:
    """A single data coverage metric."""

    metric_name: str
    coverage_pct: float  # 0-100
    expected_count: int  # How many items expected
    actual_count: int  # How many items available
    missing_items: list[str]  # Which items missing (if small set)
    last_update_date: str  # ISO date
    notes: str


@dataclass(frozen=True)
class DataQualityReport:
    """Complete data quality assessment."""

    company_id: str
    as_of_date: str  # Date quality assessment was made

    # Tier assessment
    overall_tier: DataQualityTier
    overall_coverage_pct: float  # Weighted average of all metrics

    # Individual metrics
    coverage_scores: dict[str, CoverageScore]  # metric_name -> score

    # Gaps and issues
    missing_filing_periods: list[str]  # Fiscal periods with no filing
    incomplete_statements: list[str]  # Statements missing line items
    data_quality_issues: list[str]  # Specific problems detected
    restatement_indicators: list[str]  # Hints of future restatements

    # Recommendations
    research_usable: bool  # Can this be used for research?
    research_confidence_pct: float  # 0-100 confidence in research
    follow_up_actions: list[str]  # What to check/fix

    # Versioning
    assessment_version: str  # V1_DATA_QUALITY
    created_at: str  # ISO timestamp


class ResearchDataQualityEngine:
    """
    Track and report data quality for fundamental research.

    Quality drives research confidence: poor quality data
    should flag research records as lower-confidence.
    """

    DATA_QUALITY_VERSION = "V1_DATA_QUALITY"

    # Quality thresholds
    MIN_COVERAGE_COMPLETE = 100.0
    MIN_COVERAGE_COMPREHENSIVE = 85.0
    MIN_COVERAGE_SUBSTANTIAL = 70.0
    MIN_COVERAGE_ADEQUATE = 50.0

    MIN_YEARS_HISTORY = 3  # Minimum years of data for research
    MIN_FILINGS_ANNUAL = 1  # At least annual report
    MIN_FILINGS_QUARTERLY = 4  # Quarterly coverage desired

    @staticmethod
    def calculate_filing_coverage(
        company_id: str,
        fiscal_year: int,
        filings_present: dict[str, int],
    ) -> CoverageScore:
        """
        Calculate coverage of SEC filings.

        Args:
            company_id: Company identifier
            fiscal_year: Fiscal year
            filings_present: Dict mapping filing_type to count (e.g., {"10-K": 1, "10-Q": 4})

        Returns:
            CoverageScore with filing coverage percentage
        """
        expected = 5  # 1x 10-K + 4x 10-Q
        actual = filings_present.get("10-K", 0) + filings_present.get("10-Q", 0)
        coverage_pct = (actual / expected) * 100 if expected > 0 else 0.0

        missing = []
        if filings_present.get("10-K", 0) == 0:
            missing.append("10-K")
        if filings_present.get("10-Q", 0) < 4:
            missing.append(f"10-Q (only {filings_present.get('10-Q', 0)} of 4)")

        return CoverageScore(
            metric_name="FILING_COVERAGE",
            coverage_pct=coverage_pct,
            expected_count=expected,
            actual_count=actual,
            missing_items=missing,
            last_update_date="2026-08-12",
            notes=f"Fiscal year {fiscal_year}",
        )

    @staticmethod
    def calculate_statement_completeness(
        company_id: str,
        fiscal_year: int,
        balance_sheet_populated_pct: float = 0.0,
        income_statement_populated_pct: float = 0.0,
        cash_flow_populated_pct: float = 0.0,
    ) -> CoverageScore:
        """
        Calculate how complete financial statements are.

        Measures % of expected line items that are populated.

        Args:
            company_id: Company identifier
            fiscal_year: Fiscal year
            balance_sheet_populated_pct: 0-100
            income_statement_populated_pct: 0-100
            cash_flow_populated_pct: 0-100

        Returns:
            CoverageScore for statement completeness
        """
        avg_populated = (
            balance_sheet_populated_pct
            + income_statement_populated_pct
            + cash_flow_populated_pct
        ) / 3

        missing = []
        if balance_sheet_populated_pct < 80:
            missing.append(
                f"Balance Sheet ({balance_sheet_populated_pct:.0f}%)"
            )
        if income_statement_populated_pct < 80:
            missing.append(
                f"Income Statement ({income_statement_populated_pct:.0f}%)"
            )
        if cash_flow_populated_pct < 80:
            missing.append(
                f"Cash Flow ({cash_flow_populated_pct:.0f}%)"
            )

        return CoverageScore(
            metric_name="STATEMENT_COMPLETENESS",
            coverage_pct=avg_populated,
            expected_count=3,
            actual_count=3,  # All three statement types
            missing_items=missing,
            last_update_date="2026-08-12",
            notes=f"Fiscal year {fiscal_year}",
        )

    @staticmethod
    def calculate_metric_availability(
        company_id: str,
        metrics_calculable: list[str],
        all_metrics: list[str],
    ) -> CoverageScore:
        """
        Calculate which research metrics can be calculated.

        Args:
            company_id: Company identifier
            metrics_calculable: List of metrics that can be calculated
            all_metrics: List of all expected metrics

        Returns:
            CoverageScore for metric availability
        """
        coverage_pct = (
            (len(metrics_calculable) / len(all_metrics)) * 100
            if all_metrics
            else 0.0
        )
        missing = sorted(set(all_metrics) - set(metrics_calculable))

        return CoverageScore(
            metric_name="METRIC_AVAILABILITY",
            coverage_pct=coverage_pct,
            expected_count=len(all_metrics),
            actual_count=len(metrics_calculable),
            missing_items=missing[:5],  # Show first 5
            last_update_date="2026-08-12",
            notes=f"{len(all_metrics) - len(metrics_calculable)} metrics unavailable",
        )

    @staticmethod
    def assess_data_quality(
        company_id: str,
        as_of_date: str,
        filing_coverage_pct: float = 0.0,
        statement_completeness_pct: float = 0.0,
        metric_availability_pct: float = 0.0,
        canonical_mapping_coverage_pct: float = 0.0,
        years_of_history: int = 0,
        has_restatement_history: bool = False,
    ) -> DataQualityReport:
        """
        Assess overall data quality for a company.

        Args:
            company_id: Company identifier
            as_of_date: Assessment date
            filing_coverage_pct: % of expected filings present
            statement_completeness_pct: % of statement line items present
            metric_availability_pct: % of research metrics calculable
            canonical_mapping_coverage_pct: % of XBRL facts mapped
            years_of_history: Years of historical data available
            has_restatement_history: Whether company has history of restatements

        Returns:
            DataQualityReport with full assessment
        """
        # Calculate overall coverage
        coverage_scores = {
            "filing_coverage": CoverageScore(
                metric_name="FILING_COVERAGE",
                coverage_pct=filing_coverage_pct,
                expected_count=5,
                actual_count=int(filing_coverage_pct / 20),
                missing_items=[],
                last_update_date=as_of_date,
                notes="",
            ),
            "statement_completeness": CoverageScore(
                metric_name="STATEMENT_COMPLETENESS",
                coverage_pct=statement_completeness_pct,
                expected_count=3,
                actual_count=int(statement_completeness_pct / 33),
                missing_items=[],
                last_update_date=as_of_date,
                notes="",
            ),
            "metric_availability": CoverageScore(
                metric_name="METRIC_AVAILABILITY",
                coverage_pct=metric_availability_pct,
                expected_count=15,
                actual_count=int(metric_availability_pct / 6.67),
                missing_items=[],
                last_update_date=as_of_date,
                notes="",
            ),
        }

        avg_coverage = (
            filing_coverage_pct
            + statement_completeness_pct
            + metric_availability_pct
            + canonical_mapping_coverage_pct
        ) / 4

        # Classify tier
        if avg_coverage >= ResearchDataQualityEngine.MIN_COVERAGE_COMPLETE:
            tier = DataQualityTier.COMPLETE
        elif avg_coverage >= ResearchDataQualityEngine.MIN_COVERAGE_COMPREHENSIVE:
            tier = DataQualityTier.COMPREHENSIVE
        elif avg_coverage >= ResearchDataQualityEngine.MIN_COVERAGE_SUBSTANTIAL:
            tier = DataQualityTier.SUBSTANTIAL
        elif avg_coverage >= ResearchDataQualityEngine.MIN_COVERAGE_ADEQUATE:
            tier = DataQualityTier.ADEQUATE
        else:
            tier = DataQualityTier.INSUFFICIENT

        # Issues and recommendations
        issues = []
        follow_ups = []

        if years_of_history < ResearchDataQualityEngine.MIN_YEARS_HISTORY:
            issues.append(
                f"Insufficient historical depth: {years_of_history} years "
                f"(minimum {ResearchDataQualityEngine.MIN_YEARS_HISTORY})"
            )
            follow_ups.append("Wait for more history to accumulate")

        if has_restatement_history:
            issues.append("Company has history of restatements")
            follow_ups.append("Review all prior filings for amendments")

        if filing_coverage_pct < 80:
            issues.append("Missing historical filings")
            follow_ups.append("Manually locate missing SEC filings")

        if metric_availability_pct < 70:
            issues.append("Cannot calculate all key research metrics")
            follow_ups.append("Identify which metrics are missing")

        research_usable = tier != DataQualityTier.INSUFFICIENT
        research_confidence_pct = min(100, avg_coverage)

        return DataQualityReport(
            company_id=company_id,
            as_of_date=as_of_date,
            overall_tier=tier,
            overall_coverage_pct=avg_coverage,
            coverage_scores=coverage_scores,
            missing_filing_periods=[],
            incomplete_statements=[],
            data_quality_issues=issues,
            restatement_indicators=(
                ["History of restatements detected"]
                if has_restatement_history
                else []
            ),
            research_usable=research_usable,
            research_confidence_pct=research_confidence_pct,
            follow_up_actions=follow_ups,
            assessment_version=ResearchDataQualityEngine.DATA_QUALITY_VERSION,
            created_at="2026-08-12",
        )
