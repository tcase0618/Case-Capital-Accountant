"""Accounting DNA feature store: Parquet export and DuckDB analytics layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class FeatureTableType(StrEnum):
    """Types of feature tables in the feature store."""

    COMPANIES = "companies"  # Base company metadata
    PERIODS = "periods"  # Fiscal periods and dates
    ECONOMIC_METRICS = "economic_metrics"  # Economic debt, dilution, etc.
    FORENSIC_FLAGS = "forensic_flags"  # Forensic rules violations
    POLICY_CHANGES = "policy_changes"  # Accounting policy changes
    PEER_RANKINGS = "peer_rankings"  # Percentile ranks within peers
    PEER_ANOMALIES = "peer_anomalies"  # Statistical anomalies
    ACCOUNTING_TWINS = "accounting_twins"  # Reported vs economic
    FEATURE_CATALOG = "feature_catalog"  # Metadata about all features


@dataclass(frozen=True)
class CompanyFeature:
    """Company metadata row for feature store."""

    company_id: str
    ticker: str | None
    company_name: str | None
    industry: str | None
    sector: str | None
    market_cap_usd: float | None
    is_public: bool
    data_source: str  # "SEC", "PRIVATE", etc.
    last_updated: str  # YYYY-MM-DD


@dataclass(frozen=True)
class PeriodFeature:
    """Fiscal period metadata."""

    company_id: str
    fiscal_year: int
    fiscal_quarter: int | None
    period_start: str  # YYYY-MM-DD
    period_end: str  # YYYY-MM-DD
    filing_date: str  # YYYY-MM-DD
    filing_type: str  # 10-K, 10-Q, etc.
    accession_number: str | None


@dataclass(frozen=True)
class EconomicMetricFeature:
    """Economic metric row for feature store."""

    company_id: str
    fiscal_year: int
    metric_name: str  # e.g., "Reported_Debt", "Net_Debt", "SBC_Dilution"
    metric_value: float | None
    metric_source: str  # REPORTED, ECONOMIC, CALCULATED
    confidence: str  # HIGH, MEDIUM, LOW
    formula_version: str  # V1_ECONOMIC_DEBT, etc.
    calculation_date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class ForensicFlagFeature:
    """Forensic rule violation row."""

    company_id: str
    fiscal_year: int
    rule_id: str  # e.g., "REV_001"
    rule_name: str
    category: str  # REVENUE_QUALITY, etc.
    severity: str  # WARNING, ALERT, CRITICAL
    metric_name: str
    metric_value: float | None
    threshold: float | None
    reason: str
    detection_date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class PolicyChangeFeature:
    """Accounting policy change row."""

    company_id: str
    prior_year: int
    current_year: int
    policy_name: str  # Revenue Recognition, Depreciation, etc.
    change_type: str  # NO_CHANGE, SCOPE_CHANGE, METHOD_CHANGE, etc.
    is_material: bool
    token_similarity: float | None  # 0-1 scale
    edit_distance_ratio: float | None  # 0-1 scale
    summary: str
    detection_date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class PeerRankingFeature:
    """Peer ranking row."""

    company_id: str
    fiscal_year: int
    metric_name: str
    metric_value: float | None
    percentile_rank: float | None  # 0-100
    percentile_classification: str  # TOP_DECILE, etc.
    z_score: float | None
    peer_count: int
    ranking_date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class PeerAnomalyFeature:
    """Peer anomaly row."""

    company_id: str
    fiscal_year: int
    metric_name: str
    anomaly_type: str  # OUTLIER_EXTREME, TREND_DETERIORATING, etc.
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    current_value: float | None
    prior_year_value: float | None
    peer_median: float | None
    z_score: float | None
    reason: str
    detection_date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class AccountingTwinFeature:
    """Reported vs. economic comparison row."""

    company_id: str
    fiscal_year: int
    metric_name: str  # REVENUE, OPERATING_INCOME, etc.
    reported_value: float | None
    economic_value: float | None
    percentage_difference: float | None
    aggressiveness: str  # CONSERVATIVE, NEUTRAL, MODERATE, AGGRESSIVE
    reason: str
    comparison_date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class FeatureCatalogEntry:
    """Metadata about available features."""

    feature_name: str
    table_name: str
    data_type: str  # STRING, FLOAT, INT, BOOL
    description: str
    source_engine: str  # EconomicDebtEngine, PeerStatisticsEngine, etc.
    availability_start: str  # YYYY-MM-DD (when feature first available)
    update_frequency: str  # ANNUAL, QUARTERLY, AD_HOC


class AccountingDNAFeatureStore:
    """
    Accounting DNA feature store for Parquet/DuckDB analytics.

    Core principle: Export all Phase A-C analysis results into
    normalized feature tables for downstream analytics and research.
    """

    @staticmethod
    def company_to_feature(
        company_id: str,
        ticker: str | None = None,
        company_name: str | None = None,
        industry: str | None = None,
        sector: str | None = None,
        market_cap_usd: float | None = None,
        is_public: bool = False,
    ) -> CompanyFeature:
        """Create company metadata feature row."""
        return CompanyFeature(
            company_id=company_id,
            ticker=ticker,
            company_name=company_name,
            industry=industry,
            sector=sector,
            market_cap_usd=market_cap_usd,
            is_public=is_public,
            data_source="SEC",
            last_updated=datetime.now().strftime("%Y-%m-%d"),
        )

    @staticmethod
    def period_to_feature(
        company_id: str,
        fiscal_year: int,
        fiscal_quarter: int | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
        filing_date: str | None = None,
        filing_type: str = "10-K",
        accession_number: str | None = None,
    ) -> PeriodFeature:
        """Create period metadata feature row."""
        return PeriodFeature(
            company_id=company_id,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            period_start=period_start or "",
            period_end=period_end or "",
            filing_date=filing_date or datetime.now().strftime("%Y-%m-%d"),
            filing_type=filing_type,
            accession_number=accession_number,
        )

    @staticmethod
    def economic_metric_to_feature(
        company_id: str,
        fiscal_year: int,
        metric_name: str,
        metric_value: float | None,
        metric_source: str = "CALCULATED",
        confidence: str = "HIGH",
        formula_version: str = "V1",
    ) -> EconomicMetricFeature:
        """Create economic metric feature row."""
        return EconomicMetricFeature(
            company_id=company_id,
            fiscal_year=fiscal_year,
            metric_name=metric_name,
            metric_value=metric_value,
            metric_source=metric_source,
            confidence=confidence,
            formula_version=formula_version,
            calculation_date=datetime.now().strftime("%Y-%m-%d"),
        )

    @staticmethod
    def forensic_flag_to_feature(
        company_id: str,
        fiscal_year: int,
        rule_id: str,
        rule_name: str,
        category: str,
        severity: str,
        metric_name: str,
        metric_value: float | None,
        threshold: float | None,
        reason: str,
    ) -> ForensicFlagFeature:
        """Create forensic flag feature row."""
        return ForensicFlagFeature(
            company_id=company_id,
            fiscal_year=fiscal_year,
            rule_id=rule_id,
            rule_name=rule_name,
            category=category,
            severity=severity,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
            reason=reason,
            detection_date=datetime.now().strftime("%Y-%m-%d"),
        )

    @staticmethod
    def feature_to_parquet_dict(feature: object) -> dict:
        """Convert feature dataclass to Parquet-ready dictionary."""
        if hasattr(feature, "__dataclass_fields__"):
            return asdict(feature)
        return {}

    @staticmethod
    def get_feature_catalog() -> list[FeatureCatalogEntry]:
        """Return complete feature catalog metadata."""
        return [
            FeatureCatalogEntry(
                feature_name="Company_ID",
                table_name="companies",
                data_type="STRING",
                description="Unique company identifier",
                source_engine="Manual",
                availability_start="2026-01-01",
                update_frequency="AD_HOC",
            ),
            FeatureCatalogEntry(
                feature_name="Reported_Debt",
                table_name="economic_metrics",
                data_type="FLOAT",
                description="Balance sheet debt from reported financials",
                source_engine="EconomicDebtEngine",
                availability_start="2026-01-01",
                update_frequency="ANNUAL",
            ),
            FeatureCatalogEntry(
                feature_name="Economic_Debt",
                table_name="economic_metrics",
                data_type="FLOAT",
                description="Adjusted debt including pensions, convertibles, supplier financing",
                source_engine="EconomicDebtEngine",
                availability_start="2026-01-01",
                update_frequency="ANNUAL",
            ),
            FeatureCatalogEntry(
                feature_name="SBC_Dilution_Pct",
                table_name="economic_metrics",
                data_type="FLOAT",
                description="Stock-based compensation dilution as % of shares",
                source_engine="DilutionEngine",
                availability_start="2026-01-01",
                update_frequency="ANNUAL",
            ),
            FeatureCatalogEntry(
                feature_name="Buyback_Effectiveness",
                table_name="economic_metrics",
                data_type="STRING",
                description="Classification of buyback offset vs. dilution",
                source_engine="DilutionEngine",
                availability_start="2026-01-01",
                update_frequency="ANNUAL",
            ),
            FeatureCatalogEntry(
                feature_name="ROIC",
                table_name="economic_metrics",
                data_type="FLOAT",
                description="Return on invested capital",
                source_engine="CapitalAllocationLedger",
                availability_start="2026-01-01",
                update_frequency="ANNUAL",
            ),
            FeatureCatalogEntry(
                feature_name="Forensic_Rule_Violation",
                table_name="forensic_flags",
                data_type="STRING",
                description="Rule ID and severity of forensic rule violation",
                source_engine="ForensicRulesEngine",
                availability_start="2026-01-01",
                update_frequency="ANNUAL",
            ),
            FeatureCatalogEntry(
                feature_name="Policy_Change_Type",
                table_name="policy_changes",
                data_type="STRING",
                description="Classification of accounting policy change YoY",
                source_engine="AccountingPolicyExtractor",
                availability_start="2026-01-01",
                update_frequency="ANNUAL",
            ),
            FeatureCatalogEntry(
                feature_name="Percentile_Rank",
                table_name="peer_rankings",
                data_type="FLOAT",
                description="Percentile rank within peer group (0-100)",
                source_engine="PeerStatisticsEngine",
                availability_start="2026-01-01",
                update_frequency="ANNUAL",
            ),
            FeatureCatalogEntry(
                feature_name="Anomaly_Type",
                table_name="peer_anomalies",
                data_type="STRING",
                description="Statistical anomaly classification",
                source_engine="PeerAnomalyEngine",
                availability_start="2026-01-01",
                update_frequency="ANNUAL",
            ),
            FeatureCatalogEntry(
                feature_name="Reported_vs_Economic_Gap",
                table_name="accounting_twins",
                data_type="FLOAT",
                description="Percentage difference between reported and economic metrics",
                source_engine="AccountingTwinEngine",
                availability_start="2026-01-01",
                update_frequency="ANNUAL",
            ),
        ]

    @staticmethod
    def export_summary() -> dict:
        """Summary of feature store schema and contents."""
        return {
            "feature_store_name": "Accounting DNA",
            "version": "1.0",
            "backends": ["Parquet", "DuckDB"],
            "tables": [
                "companies",
                "periods",
                "economic_metrics",
                "forensic_flags",
                "policy_changes",
                "peer_rankings",
                "peer_anomalies",
                "accounting_twins",
                "feature_catalog",
            ],
            "total_features": len(AccountingDNAFeatureStore.get_feature_catalog()),
            "update_frequency": "ANNUAL",
            "timestamp": datetime.now().isoformat(),
        }
