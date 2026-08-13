"""Tests for fundamental research classification engine."""

import pytest

from accountant.research.classification_engine import (
    ClassificationRule,
    FundamentalResearchClassificationEngine,
    FundamentalResearchRecord,
    ResearchClassification,
)


class TestClassificationRule:
    def test_classification_rule_creation(self):
        rule = ClassificationRule(
            rule_id="TEST_RULE",
            rule_name="Test Rule",
            metric_name="Test Metric",
            operator="gt",
            threshold=100,
            actual_value=150,
            triggered=True,
            severity="HIGH",
        )
        assert rule.rule_id == "TEST_RULE"
        assert rule.triggered is True
        assert rule.severity == "HIGH"

    def test_classification_rule_immutable(self):
        rule = ClassificationRule(
            rule_id="TEST",
            rule_name="Test",
            metric_name="Test",
            operator="gt",
            threshold=0,
            actual_value=0,
            triggered=False,
            severity="LOW",
        )
        with pytest.raises(AttributeError):
            rule.triggered = True  # type: ignore


class TestFundamentalResearchRecord:
    def test_record_creation(self):
        record = FundamentalResearchRecord(
            company_id="AAPL",
            as_of_date="2024-01-15",
            classification=ResearchClassification.HIGH_QUALITY,
            rules_triggered=[],
            rules_failed=[],
            accounting_quality_score=75.0,
            owner_earnings_yield_pct=5.5,
            owner_earnings_growth_pct=10.0,
            roic_pct=15.0,
            incremental_roic_pct=12.0,
            capital_allocation_score=70.0,
            credit_quality_score=80.0,
            bear_case_risk_score=20.0,
            forensic_risk_score=15.0,
            valuation_range_low=100.0,
            valuation_range_high=150.0,
            current_price=120.0,
            margin_of_safety_pct=25.0,
            peer_rank_quality=75,
            peer_rank_growth=80,
            peer_rank_valuation=70,
            peer_rank_safety=85,
            warnings=[],
            classification_notes="High quality company",
            rule_version="FUNDAMENTAL_RESEARCH_CLASSIFICATION_V1",
            feature_versions={},
            created_at="2024-01-15T10:00:00",
        )
        assert record.company_id == "AAPL"
        assert record.classification == ResearchClassification.HIGH_QUALITY
        assert record.accounting_quality_score == 75.0

    def test_record_immutable(self):
        record = FundamentalResearchRecord(
            company_id="AAPL",
            as_of_date="2024-01-15",
            classification=ResearchClassification.WATCHLIST,
            rules_triggered=[],
            rules_failed=[],
            accounting_quality_score=None,
            owner_earnings_yield_pct=None,
            owner_earnings_growth_pct=None,
            roic_pct=None,
            incremental_roic_pct=None,
            capital_allocation_score=None,
            credit_quality_score=None,
            bear_case_risk_score=None,
            forensic_risk_score=None,
            valuation_range_low=None,
            valuation_range_high=None,
            current_price=None,
            margin_of_safety_pct=None,
            peer_rank_quality=None,
            peer_rank_growth=None,
            peer_rank_valuation=None,
            peer_rank_safety=None,
            warnings=[],
            classification_notes="",
            rule_version="FUNDAMENTAL_RESEARCH_CLASSIFICATION_V1",
            feature_versions={},
            created_at="2024-01-15T10:00:00",
        )
        with pytest.raises(AttributeError):
            record.classification = ResearchClassification.HIGH_QUALITY  # type: ignore


class TestResearchClassificationEngine:
    def test_classify_high_quality(self):
        record = FundamentalResearchClassificationEngine.classify(
            company_id="AAPL",
            as_of_date="2024-01-15",
            accounting_quality_score=75.0,
            forensic_risk_score=20.0,
        )
        assert record.company_id == "AAPL"
        assert record.classification == ResearchClassification.HIGH_QUALITY

    def test_classify_rejected_negative_fcf(self):
        record = FundamentalResearchClassificationEngine.classify(
            company_id="TEST",
            as_of_date="2024-01-15",
            negative_fcf=True,
        )
        assert record.classification == ResearchClassification.REJECTED_BY_RULES
        assert len(record.rules_triggered) > 0

    def test_classify_rejected_declining_revenue(self):
        record = FundamentalResearchClassificationEngine.classify(
            company_id="TEST",
            as_of_date="2024-01-15",
            declining_revenue=True,
        )
        assert record.classification == ResearchClassification.REJECTED_BY_RULES
        assert len(record.rules_triggered) > 0

    def test_classify_rejected_low_quality(self):
        record = FundamentalResearchClassificationEngine.classify(
            company_id="TEST",
            as_of_date="2024-01-15",
            accounting_quality_score=30.0,
        )
        assert record.classification == ResearchClassification.REJECTED_BY_RULES

    def test_classify_expensive(self):
        record = FundamentalResearchClassificationEngine.classify(
            company_id="TEST",
            as_of_date="2024-01-15",
            valuation_range_high=100.0,
            current_price=120.0,
            accounting_quality_score=50.0,
            owner_earnings_yield_pct=3.0,
        )
        assert record.classification == ResearchClassification.EXPENSIVE

    def test_classify_attractive_valuation(self):
        record = FundamentalResearchClassificationEngine.classify(
            company_id="TEST",
            as_of_date="2024-01-15",
            valuation_range_low=50.0,
            valuation_range_high=100.0,
            current_price=60.0,
            accounting_quality_score=50.0,
            owner_earnings_yield_pct=3.0,
        )
        assert record.classification == ResearchClassification.ATTRACTIVE_VALUATION

    def test_classify_insufficient_data(self):
        record = FundamentalResearchClassificationEngine.classify(
            company_id="TEST",
            as_of_date="2024-01-15",
        )
        assert record.classification == ResearchClassification.INSUFFICIENT_DATA

    def test_margin_of_safety_calculation(self):
        record = FundamentalResearchClassificationEngine.classify(
            company_id="TEST",
            as_of_date="2024-01-15",
            valuation_range_high=100.0,
            current_price=80.0,
        )
        assert record.margin_of_safety_pct is not None
        assert record.margin_of_safety_pct > 0

    def test_version_tracking(self):
        record = FundamentalResearchClassificationEngine.classify(
            company_id="TEST",
            as_of_date="2024-01-15",
        )
        assert (
            record.rule_version
            == FundamentalResearchClassificationEngine.FUNDAMENTAL_RESEARCH_CLASSIFICATION_VERSION
        )

    def test_constant_thresholds_exist(self):
        assert (
            FundamentalResearchClassificationEngine.HIGH_QUALITY_ACCOUNTING_QUALITY_MIN
            == 70
        )
        assert (
            FundamentalResearchClassificationEngine.ATTRACTIVE_VALUATION_MARGIN_OF_SAFETY_MIN_PCT
            == 30
        )
