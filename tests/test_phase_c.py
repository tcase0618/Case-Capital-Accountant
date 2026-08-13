"""Phase C comprehensive tests: Peer analysis, anomaly detection, twin engine, feature store."""

import pytest

from accountant.analysis.accounting_twin_engine import (
    AccountingAggressiveness,
    AccountingTwinEngine,
    AccountingTwinReport,
)
from accountant.analysis.peer_anomaly_engine import (
    AnomalyReport,
    AnomalyType,
    PeerAnomalyEngine,
    SeverityLevel,
)
from accountant.analysis.peer_statistics_engine import (
    PeerMetric,
    PeerStatistics,
    PeerStatisticsEngine,
    PercentileRank,
)
from accountant.export.accounting_dna_feature_store import (
    AccountingDNAFeatureStore,
    CompanyFeature,
    EconomicMetricFeature,
    ForensicFlagFeature,
    PeriodFeature,
)


class TestPeerStatisticsEngine:
    """Peer statistics and ranking tests."""

    def test_calculate_statistics_basic(self):
        """Calculate mean, median, quartiles from peer metrics."""
        metrics = [
            PeerMetric(
                company_id="COMP001",
                fiscal_year=2024,
                metric_name="Debt/EBITDA",
                metric_value=2.5,
                source="REPORTED",
                confidence="HIGH",
            ),
            PeerMetric(
                company_id="COMP002",
                fiscal_year=2024,
                metric_name="Debt/EBITDA",
                metric_value=3.0,
                source="REPORTED",
                confidence="HIGH",
            ),
            PeerMetric(
                company_id="COMP003",
                fiscal_year=2024,
                metric_name="Debt/EBITDA",
                metric_value=3.5,
                source="REPORTED",
                confidence="HIGH",
            ),
        ]

        stats = PeerStatisticsEngine.calculate_statistics(metrics)

        assert stats.peer_count == 3
        assert stats.mean_value == 3.0
        assert stats.median_value == 3.0
        assert stats.min_value == 2.5
        assert stats.max_value == 3.5
        assert stats.valid_count == 3
        assert stats.data_quality == 100.0

    def test_calculate_statistics_with_nulls(self):
        """Handle missing data in peer metrics."""
        metrics = [
            PeerMetric(
                company_id="COMP001",
                fiscal_year=2024,
                metric_name="Metric",
                metric_value=1.0,
                source="REPORTED",
                confidence="HIGH",
            ),
            PeerMetric(
                company_id="COMP002",
                fiscal_year=2024,
                metric_name="Metric",
                metric_value=None,
                source="REPORTED",
                confidence="HIGH",
            ),
            PeerMetric(
                company_id="COMP003",
                fiscal_year=2024,
                metric_name="Metric",
                metric_value=3.0,
                source="REPORTED",
                confidence="HIGH",
            ),
        ]

        stats = PeerStatisticsEngine.calculate_statistics(metrics)

        assert stats.peer_count == 3
        assert stats.valid_count == 2
        assert stats.null_count == 1
        assert stats.data_quality == pytest.approx(66.67, rel=0.01)

    def test_rank_company_percentile(self):
        """Classify company percentile within peer group."""
        metrics = [
            PeerMetric(
                company_id=f"COMP{i:03d}",
                fiscal_year=2024,
                metric_name="ROE",
                metric_value=5.0 + i,
                source="REPORTED",
                confidence="HIGH",
            )
            for i in range(20)
        ]

        stats = PeerStatisticsEngine.calculate_statistics(metrics)
        company_metric = PeerMetric(
            company_id="TARGET",
            fiscal_year=2024,
            metric_name="ROE",
            metric_value=24.0,  # Should be top decile
            source="REPORTED",
            confidence="HIGH",
        )

        ranking = PeerStatisticsEngine.rank_company(company_metric, stats)

        assert ranking.percentile_classification == PercentileRank.TOP_DECILE

    def test_rank_company_insufficient_data(self):
        """Handle insufficient peer data."""
        stats = PeerStatistics(
            metric_name="ROE",
            fiscal_year=2024,
            peer_count=2,
            mean_value=10.0,
            median_value=10.0,
            min_value=5.0,
            max_value=15.0,
            stdev=5.0,
            q1_value=7.5,
            q3_value=12.5,
            p10_value=None,
            p90_value=None,
            valid_count=2,
            null_count=0,
            data_quality=100.0,
            analysis_date="2026-08-12",
        )

        company_metric = PeerMetric(
            company_id="TARGET",
            fiscal_year=2024,
            metric_name="ROE",
            metric_value=10.0,
            source="REPORTED",
            confidence="HIGH",
        )

        ranking = PeerStatisticsEngine.rank_company(company_metric, stats)

        assert (
            ranking.percentile_classification
            == PercentileRank.INSUFFICIENT_DATA
        )

    def test_rank_peer_group_complete(self):
        """Complete analysis: statistics + rankings for all peers."""
        metrics = [
            PeerMetric(
                company_id=f"COMP{i:03d}",
                fiscal_year=2024,
                metric_name="ROIC",
                metric_value=8.0 + i,
                source="ECONOMIC",
                confidence="HIGH",
            )
            for i in range(10)
        ]

        stats, rankings = PeerStatisticsEngine.rank_peer_group(metrics)

        assert stats.peer_count == 10
        assert len(rankings) == 10
        assert all(r.peer_count == 10 for r in rankings)


class TestPeerAnomalyEngine:
    """Peer anomaly detection tests."""

    def test_detect_statistical_outlier_extreme(self):
        """Detect extreme outlier (|Z| > 3.0)."""
        finding = PeerAnomalyEngine.detect_statistical_outlier(
            company_id="COMP001",
            fiscal_year=2024,
            metric_name="Debt/EBITDA",
            current_value=10.0,
            peer_median=3.0,
            z_score=3.5,
            peer_count=10,
        )

        assert finding is not None
        assert finding.anomaly_type == AnomalyType.OUTLIER_EXTREME
        assert finding.severity == SeverityLevel.CRITICAL

    def test_detect_statistical_outlier_moderate(self):
        """Detect moderate outlier (2.0 < |Z| <= 3.0)."""
        finding = PeerAnomalyEngine.detect_statistical_outlier(
            company_id="COMP001",
            fiscal_year=2024,
            metric_name="ROE",
            current_value=25.0,
            peer_median=10.0,
            z_score=2.5,
            peer_count=10,
        )

        assert finding is not None
        assert finding.anomaly_type == AnomalyType.OUTLIER_MODERATE
        assert finding.severity == SeverityLevel.HIGH

    def test_detect_statistical_outlier_mild(self):
        """Detect mild outlier (1.5 < |Z| <= 2.0)."""
        finding = PeerAnomalyEngine.detect_statistical_outlier(
            company_id="COMP001",
            fiscal_year=2024,
            metric_name="Revenue Growth",
            current_value=20.0,
            peer_median=10.0,
            z_score=1.8,
            peer_count=10,
        )

        assert finding is not None
        assert finding.anomaly_type == AnomalyType.OUTLIER_MILD
        assert finding.severity == SeverityLevel.MEDIUM

    def test_detect_statistical_outlier_normal(self):
        """No anomaly within normal range."""
        finding = PeerAnomalyEngine.detect_statistical_outlier(
            company_id="COMP001",
            fiscal_year=2024,
            metric_name="Metric",
            current_value=10.0,
            peer_median=10.0,
            z_score=0.5,
            peer_count=10,
        )

        assert finding is None

    def test_detect_trend_anomaly_deteriorating(self):
        """Detect deteriorating trend."""
        finding = PeerAnomalyEngine.detect_trend_anomaly(
            company_id="COMP001",
            fiscal_year=2024,
            metric_name="Operating Margin",
            current_value=12.0,
            prior_year_value=15.0,
            two_year_prior=18.0,
        )

        assert finding is not None
        assert finding.anomaly_type == AnomalyType.TREND_DETERIORATING
        assert finding.severity == SeverityLevel.MEDIUM

    def test_detect_trend_anomaly_sign_reversal(self):
        """Detect sign reversal (profit to loss)."""
        finding = PeerAnomalyEngine.detect_trend_anomaly(
            company_id="COMP001",
            fiscal_year=2024,
            metric_name="Net Income",
            current_value=-50.0,
            prior_year_value=100.0,
            two_year_prior=110.0,
        )

        assert finding is not None
        assert finding.anomaly_type == AnomalyType.TREND_INFLECTION
        assert finding.severity == SeverityLevel.HIGH

    def test_run_anomaly_scan_complete(self):
        """Complete anomaly scan with multiple findings."""
        metrics = {
            "Debt/EBITDA": 8.0,
            "ROE": 25.0,
            "Revenue Growth": 5.0,
        }
        peer_medians = {
            "Debt/EBITDA": 3.0,
            "ROE": 10.0,
            "Revenue Growth": 8.0,
        }
        z_scores = {
            "Debt/EBITDA": 3.2,
            "ROE": 2.1,
            "Revenue Growth": -0.5,
        }
        prior_metrics = {
            "Debt/EBITDA": 7.0,
            "ROE": 22.0,
            "Revenue Growth": 4.0,
        }

        report = PeerAnomalyEngine.run_anomaly_scan(
            company_id="COMP001",
            fiscal_year=2024,
            metrics=metrics,
            peer_medians=peer_medians,
            z_scores=z_scores,
            prior_metrics=prior_metrics,
            peer_count=20,
        )

        assert isinstance(report, AnomalyReport)
        assert report.company_id == "COMP001"
        assert report.total_findings > 0
        assert report.anomaly_risk_score > 0


class TestAccountingTwinEngine:
    """Reported vs. economic book comparison tests."""

    def test_reconcile_metric_neutral(self):
        """Reconcile metrics within tolerance (neutral)."""
        recon = AccountingTwinEngine.reconcile_metric(
            company_id="COMP001",
            fiscal_year=2024,
            metric_name="Revenue",
            reported_value=1000.0,
            economic_value=1000.0,
        )

        assert recon.aggressiveness == AccountingAggressiveness.NEUTRAL
        assert recon.percentage_difference is not None

    def test_reconcile_metric_moderate_aggressive(self):
        """Reconcile metrics with moderate divergence."""
        recon = AccountingTwinEngine.reconcile_metric(
            company_id="COMP001",
            fiscal_year=2024,
            metric_name="Operating Income",
            reported_value=115.0,
            economic_value=100.0,
        )

        assert recon.aggressiveness == AccountingAggressiveness.MODERATE
        assert recon.percentage_difference is not None
        assert recon.percentage_difference > AccountingTwinEngine.TOLERANCE_PCT

    def test_reconcile_metric_highly_aggressive(self):
        """Reconcile metrics with extreme divergence."""
        recon = AccountingTwinEngine.reconcile_metric(
            company_id="COMP001",
            fiscal_year=2024,
            metric_name="Net Income",
            reported_value=500.0,
            economic_value=250.0,
        )

        assert recon.aggressiveness == AccountingAggressiveness.HIGHLY_AGGRESSIVE
        assert recon.percentage_difference is not None
        assert recon.percentage_difference > 30.0

    def test_run_twin_analysis_complete(self):
        """Complete twin analysis with multiple metrics."""
        reported = {
            "Revenue": 1000.0,
            "Operating Income": 200.0,
            "Net Income": 100.0,
            "ROIC": 12.0,
        }
        economic = {
            "Revenue": 1000.0,
            "Operating Income": 180.0,
            "Net Income": 80.0,
            "ROIC": 10.0,
        }

        report = AccountingTwinEngine.run_twin_analysis(
            company_id="COMP001",
            fiscal_year=2024,
            reported_metrics=reported,
            economic_metrics=economic,
        )

        assert isinstance(report, AccountingTwinReport)
        assert report.company_id == "COMP001"
        assert report.total_metrics == 4
        assert report.average_divergence > 0


class TestAccountingDNAFeatureStore:
    """Feature store and export tests."""

    def test_company_to_feature(self):
        """Create company feature row."""
        feature = AccountingDNAFeatureStore.company_to_feature(
            company_id="ACME001",
            ticker="ACME",
            company_name="ACME Inc.",
            industry="Technology",
            sector="Software",
            market_cap_usd=50000.0,
            is_public=True,
        )

        assert isinstance(feature, CompanyFeature)
        assert feature.company_id == "ACME001"
        assert feature.ticker == "ACME"
        assert feature.is_public is True

    def test_period_to_feature(self):
        """Create period metadata feature row."""
        feature = AccountingDNAFeatureStore.period_to_feature(
            company_id="ACME001",
            fiscal_year=2024,
            fiscal_quarter=None,
            period_end="2024-12-31",
            filing_type="10-K",
        )

        assert isinstance(feature, PeriodFeature)
        assert feature.fiscal_year == 2024
        assert feature.filing_type == "10-K"

    def test_economic_metric_to_feature(self):
        """Create economic metric feature row."""
        feature = AccountingDNAFeatureStore.economic_metric_to_feature(
            company_id="ACME001",
            fiscal_year=2024,
            metric_name="Net_Debt",
            metric_value=500.0,
            metric_source="CALCULATED",
            formula_version="V1_ECONOMIC_DEBT",
        )

        assert isinstance(feature, EconomicMetricFeature)
        assert feature.metric_name == "Net_Debt"
        assert feature.metric_value == 500.0

    def test_forensic_flag_to_feature(self):
        """Create forensic flag feature row."""
        feature = AccountingDNAFeatureStore.forensic_flag_to_feature(
            company_id="ACME001",
            fiscal_year=2024,
            rule_id="REV_001",
            rule_name="Revenue Growth > Earnings Growth",
            category="REVENUE_QUALITY",
            severity="WARNING",
            metric_name="Revenue Growth",
            metric_value=2.0,
            threshold=1.5,
            reason="Revenue growing faster than earnings",
        )

        assert isinstance(feature, ForensicFlagFeature)
        assert feature.rule_id == "REV_001"
        assert feature.severity == "WARNING"

    def test_feature_to_parquet_dict(self):
        """Convert feature to Parquet dictionary."""
        feature = AccountingDNAFeatureStore.company_to_feature(
            company_id="ACME001",
        )

        parquet_dict = AccountingDNAFeatureStore.feature_to_parquet_dict(feature)

        assert isinstance(parquet_dict, dict)
        assert "company_id" in parquet_dict
        assert parquet_dict["company_id"] == "ACME001"

    def test_get_feature_catalog(self):
        """Retrieve complete feature catalog."""
        catalog = AccountingDNAFeatureStore.get_feature_catalog()

        assert len(catalog) > 0
        assert all(c.feature_name for c in catalog)
        assert all(c.table_name for c in catalog)

    def test_export_summary(self):
        """Get feature store export summary."""
        summary = AccountingDNAFeatureStore.export_summary()

        assert summary["feature_store_name"] == "Accounting DNA"
        assert len(summary["tables"]) > 0
        assert "Parquet" in summary["backends"]


class TestPhaseCAIntegration:
    """Integration tests for Phase C components."""

    def test_peer_analysis_to_feature_flow(self):
        """End-to-end: peer statistics → rankings → features."""
        metrics = [
            PeerMetric(
                company_id=f"COMP{i:03d}",
                fiscal_year=2024,
                metric_name="ROIC",
                metric_value=8.0 + i,
                source="ECONOMIC",
                confidence="HIGH",
            )
            for i in range(10)
        ]

        stats, rankings = PeerStatisticsEngine.rank_peer_group(metrics)

        # Convert to features
        features = [
            AccountingDNAFeatureStore.economic_metric_to_feature(
                company_id=r.company_id,
                fiscal_year=r.fiscal_year,
                metric_name=f"Percentile_{r.metric_name}",
                metric_value=r.percentile_rank,
                formula_version="V1_PEER_STATISTICS",
            )
            for r in rankings
        ]

        assert len(features) == 10
        assert all(f.metric_value is not None for f in features)

    def test_anomaly_to_feature_flow(self):
        """End-to-end: anomaly detection → features."""
        metrics = {"Debt/EBITDA": 8.0}
        peer_medians = {"Debt/EBITDA": 3.0}
        z_scores = {"Debt/EBITDA": 3.2}

        report = PeerAnomalyEngine.run_anomaly_scan(
            company_id="COMP001",
            fiscal_year=2024,
            metrics=metrics,
            peer_medians=peer_medians,
            z_scores=z_scores,
            peer_count=20,
        )

        # Convert to features
        features = []
        for finding in report.findings:
            feature = AccountingDNAFeatureStore.forensic_flag_to_feature(
                company_id=finding.company_id,
                fiscal_year=finding.fiscal_year,
                rule_id=f"ANOMALY_{finding.anomaly_type}",
                rule_name=finding.anomaly_type.value,
                category="PEER_ANOMALY",
                severity=finding.severity.value,
                metric_name=finding.metric_name,
                metric_value=finding.current_value,
                threshold=finding.peer_median,
                reason=finding.reason,
            )
            features.append(feature)

        assert len(features) > 0
