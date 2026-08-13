"""Tests for research data quality engine."""

import pytest

from accountant.research.data_quality_engine import (
    CoverageScore,
    DataQualityReport,
    DataQualityTier,
    ResearchDataQualityEngine,
)


class TestCoverageScore:
    def test_coverage_score_creation(self):
        score = CoverageScore(
            metric_name="FILING_COVERAGE",
            coverage_pct=95.0,
            expected_count=5,
            actual_count=5,
            missing_items=[],
            last_update_date="2024-01-15",
            notes="Complete coverage",
        )
        assert score.metric_name == "FILING_COVERAGE"
        assert score.coverage_pct == 95.0
        assert len(score.missing_items) == 0

    def test_coverage_score_immutable(self):
        score = CoverageScore(
            metric_name="TEST",
            coverage_pct=50.0,
            expected_count=10,
            actual_count=5,
            missing_items=["A", "B"],
            last_update_date="2024-01-15",
            notes="",
        )
        with pytest.raises(AttributeError):
            score.coverage_pct = 60.0  # type: ignore


class TestDataQualityReport:
    def test_data_quality_report_creation(self):
        report = DataQualityReport(
            company_id="AAPL",
            as_of_date="2024-01-15",
            overall_tier=DataQualityTier.COMPREHENSIVE,
            overall_coverage_pct=90.0,
            coverage_scores={},
            missing_filing_periods=[],
            incomplete_statements=[],
            data_quality_issues=[],
            restatement_indicators=[],
            research_usable=True,
            research_confidence_pct=90.0,
            follow_up_actions=[],
            assessment_version="V1",
            created_at="2024-01-15T10:00:00",
        )
        assert report.company_id == "AAPL"
        assert report.overall_tier == DataQualityTier.COMPREHENSIVE
        assert report.research_usable is True

    def test_data_quality_report_immutable(self):
        report = DataQualityReport(
            company_id="TEST",
            as_of_date="2024-01-15",
            overall_tier=DataQualityTier.ADEQUATE,
            overall_coverage_pct=60.0,
            coverage_scores={},
            missing_filing_periods=[],
            incomplete_statements=[],
            data_quality_issues=[],
            restatement_indicators=[],
            research_usable=False,
            research_confidence_pct=60.0,
            follow_up_actions=[],
            assessment_version="V1",
            created_at="2024-01-15T10:00:00",
        )
        with pytest.raises(AttributeError):
            report.research_usable = True  # type: ignore


class TestDataQualityTier:
    def test_all_tiers_exist(self):
        tiers = [
            DataQualityTier.COMPLETE,
            DataQualityTier.COMPREHENSIVE,
            DataQualityTier.SUBSTANTIAL,
            DataQualityTier.ADEQUATE,
            DataQualityTier.INSUFFICIENT,
        ]
        assert len(tiers) == 5


class TestResearchDataQualityEngine:
    def test_calculate_filing_coverage_complete(self):
        score = ResearchDataQualityEngine.calculate_filing_coverage(
            company_id="AAPL",
            fiscal_year=2024,
            filings_present={"10-K": 1, "10-Q": 4},
        )
        assert score.metric_name == "FILING_COVERAGE"
        assert score.coverage_pct == 100.0
        assert len(score.missing_items) == 0

    def test_calculate_filing_coverage_partial(self):
        score = ResearchDataQualityEngine.calculate_filing_coverage(
            company_id="TEST",
            fiscal_year=2024,
            filings_present={"10-K": 1, "10-Q": 2},
        )
        assert score.coverage_pct < 100.0
        assert "10-Q" in str(score.missing_items)

    def test_calculate_filing_coverage_missing(self):
        score = ResearchDataQualityEngine.calculate_filing_coverage(
            company_id="TEST",
            fiscal_year=2024,
            filings_present={"10-K": 0, "10-Q": 0},
        )
        assert score.coverage_pct == 0.0
        assert len(score.missing_items) > 0

    def test_calculate_statement_completeness(self):
        score = ResearchDataQualityEngine.calculate_statement_completeness(
            company_id="AAPL",
            fiscal_year=2024,
            balance_sheet_populated_pct=100.0,
            income_statement_populated_pct=100.0,
            cash_flow_populated_pct=100.0,
        )
        assert score.metric_name == "STATEMENT_COMPLETENESS"
        assert score.coverage_pct == 100.0

    def test_calculate_statement_completeness_partial(self):
        score = ResearchDataQualityEngine.calculate_statement_completeness(
            company_id="TEST",
            fiscal_year=2024,
            balance_sheet_populated_pct=80.0,
            income_statement_populated_pct=90.0,
            cash_flow_populated_pct=70.0,
        )
        assert 70 < score.coverage_pct < 90

    def test_calculate_metric_availability(self):
        all_metrics = [
            "net_income",
            "revenue",
            "assets",
            "owner_earnings",
            "roic",
        ]
        calculable = ["net_income", "revenue", "assets"]

        score = ResearchDataQualityEngine.calculate_metric_availability(
            company_id="AAPL",
            metrics_calculable=calculable,
            all_metrics=all_metrics,
        )
        assert score.metric_name == "METRIC_AVAILABILITY"
        assert score.coverage_pct == 60.0
        assert score.actual_count == 3
        assert score.expected_count == 5

    def test_assess_data_quality_complete(self):
        report = ResearchDataQualityEngine.assess_data_quality(
            company_id="AAPL",
            as_of_date="2024-01-15",
            filing_coverage_pct=100.0,
            statement_completeness_pct=100.0,
            metric_availability_pct=100.0,
            canonical_mapping_coverage_pct=100.0,
            years_of_history=10,
            has_restatement_history=False,
        )
        assert report.overall_tier == DataQualityTier.COMPLETE
        assert report.research_usable is True
        assert len(report.data_quality_issues) == 0

    def test_assess_data_quality_comprehensive(self):
        report = ResearchDataQualityEngine.assess_data_quality(
            company_id="TEST",
            as_of_date="2024-01-15",
            filing_coverage_pct=90.0,
            statement_completeness_pct=90.0,
            metric_availability_pct=90.0,
            canonical_mapping_coverage_pct=85.0,
            years_of_history=5,
            has_restatement_history=False,
        )
        assert report.overall_tier == DataQualityTier.COMPREHENSIVE
        assert report.research_usable is True

    def test_assess_data_quality_insufficient(self):
        report = ResearchDataQualityEngine.assess_data_quality(
            company_id="TEST",
            as_of_date="2024-01-15",
            filing_coverage_pct=40.0,
            statement_completeness_pct=40.0,
            metric_availability_pct=40.0,
            canonical_mapping_coverage_pct=30.0,
            years_of_history=1,
            has_restatement_history=True,
        )
        assert report.overall_tier == DataQualityTier.INSUFFICIENT
        assert report.research_usable is False
        assert len(report.data_quality_issues) > 0
        assert len(report.follow_up_actions) > 0

    def test_assess_data_quality_with_restatement_history(self):
        report = ResearchDataQualityEngine.assess_data_quality(
            company_id="TEST",
            as_of_date="2024-01-15",
            filing_coverage_pct=100.0,
            statement_completeness_pct=100.0,
            metric_availability_pct=100.0,
            canonical_mapping_coverage_pct=100.0,
            years_of_history=5,
            has_restatement_history=True,
        )
        assert any("restatement" in issue.lower() for issue in report.data_quality_issues)

    def test_version_tracking(self):
        report = ResearchDataQualityEngine.assess_data_quality(
            company_id="AAPL",
            as_of_date="2024-01-15",
        )
        assert (
            report.assessment_version
            == ResearchDataQualityEngine.DATA_QUALITY_VERSION
        )

    def test_constant_thresholds_exist(self):
        assert ResearchDataQualityEngine.MIN_COVERAGE_COMPLETE == 100.0
        assert ResearchDataQualityEngine.MIN_COVERAGE_COMPREHENSIVE == 85.0
        assert ResearchDataQualityEngine.MIN_YEARS_HISTORY == 3
