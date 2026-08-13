"""Peer statistics engine for calculating percentiles, quartiles, and peer rankings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from statistics import mean, median, quantiles
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class PercentileRank(StrEnum):
    """Classification of percentile position within peer group."""

    TOP_DECILE = "TOP_DECILE"  # 90-100th percentile
    TOP_QUARTILE = "TOP_QUARTILE"  # 75-90th percentile
    ABOVE_MEDIAN = "ABOVE_MEDIAN"  # 50-75th percentile
    BELOW_MEDIAN = "BELOW_MEDIAN"  # 25-50th percentile
    BOTTOM_QUARTILE = "BOTTOM_QUARTILE"  # 10-25th percentile
    BOTTOM_DECILE = "BOTTOM_DECILE"  # 0-10th percentile
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Fewer than 3 peers


@dataclass(frozen=True)
class PeerMetric:
    """Single peer company's metric value."""

    company_id: str
    fiscal_year: int
    metric_name: str  # e.g., "Debt/EBITDA"
    metric_value: float | None  # None if data unavailable
    source: str  # "REPORTED", "ECONOMIC"
    confidence: str  # HIGH, MEDIUM, LOW


@dataclass(frozen=True)
class PeerStatistics:
    """Aggregated statistics for metric across peer group."""

    metric_name: str
    fiscal_year: int
    peer_count: int

    # Metrics
    mean_value: float | None  # Arithmetic mean
    median_value: float | None  # 50th percentile
    min_value: float | None
    max_value: float | None
    stdev: float | None  # Standard deviation

    # Percentiles
    q1_value: float | None  # 25th percentile
    q3_value: float | None  # 75th percentile
    p10_value: float | None  # 10th percentile
    p90_value: float | None  # 90th percentile

    # Distribution
    valid_count: int  # Number of non-None values
    null_count: int  # Number of None values
    data_quality: float  # % of peers with valid data (0-100)

    # Analysis
    analysis_date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class PeerRanking:
    """Company's ranking within peer group for specific metric."""

    company_id: str
    fiscal_year: int
    metric_name: str

    # Ranking
    metric_value: float | None
    percentile_rank: float | None  # 0-100 scale
    percentile_classification: PercentileRank

    # Relative position
    std_deviations_from_mean: float | None  # Z-score
    distance_from_median: float | None  # Absolute difference
    peer_rank: int | None  # Ordinal rank within group (1 = best/worst depending on metric)
    peer_count: int  # Total peers in group

    # Context
    formula_version: str  # V1_PEER_STATISTICS


class PeerStatisticsEngine:
    """
    Calculate peer statistics and rankings for metrics.

    Core principle: Deterministic percentile/quartile calculations
    across peer group to contextualize company metrics.
    """

    @staticmethod
    def calculate_statistics(
        metrics: list[PeerMetric],
    ) -> PeerStatistics:
        """
        Calculate aggregated statistics for metric across peers.

        Input: List of peer metrics
        Output: PeerStatistics with mean, median, quartiles, std dev
        """
        if not metrics:
            return PeerStatistics(
                metric_name="",
                fiscal_year=0,
                peer_count=0,
                mean_value=None,
                median_value=None,
                min_value=None,
                max_value=None,
                stdev=None,
                q1_value=None,
                q3_value=None,
                p10_value=None,
                p90_value=None,
                valid_count=0,
                null_count=0,
                data_quality=0.0,
                analysis_date="2026-08-12",
            )

        metric_name = metrics[0].metric_name if metrics else ""
        fiscal_year = metrics[0].fiscal_year if metrics else 0

        # Extract valid values (non-None)
        valid_values = [m.metric_value for m in metrics if m.metric_value is not None]
        valid_count = len(valid_values)
        null_count = len(metrics) - valid_count
        data_quality = (valid_count / len(metrics) * 100) if metrics else 0

        if not valid_values:
            return PeerStatistics(
                metric_name=metric_name,
                fiscal_year=fiscal_year,
                peer_count=len(metrics),
                mean_value=None,
                median_value=None,
                min_value=None,
                max_value=None,
                stdev=None,
                q1_value=None,
                q3_value=None,
                p10_value=None,
                p90_value=None,
                valid_count=0,
                null_count=null_count,
                data_quality=0.0,
                analysis_date="2026-08-12",
            )

        # Calculate mean
        mean_val = mean(valid_values)

        # Calculate median
        median_val = median(valid_values)

        # Calculate min/max
        min_val = min(valid_values)
        max_val = max(valid_values)

        # Calculate standard deviation
        if valid_count >= 2:
            sum_sq_diff = sum((x - mean_val) ** 2 for x in valid_values)
            stdev = (sum_sq_diff / (valid_count - 1)) ** 0.5
        else:
            stdev = None

        # Calculate percentiles
        q1_val = None
        q3_val = None
        p10_val = None
        p90_val = None

        if valid_count >= 3:
            try:
                quartiles_result = quantiles(valid_values, n=4)
                q1_val = quartiles_result[0]
                q3_val = quartiles_result[2]
            except Exception:
                pass

        if valid_count >= 10:
            try:
                deciles = quantiles(valid_values, n=10)
                p10_val = deciles[0]
                p90_val = deciles[8]
            except Exception:
                pass

        return PeerStatistics(
            metric_name=metric_name,
            fiscal_year=fiscal_year,
            peer_count=len(metrics),
            mean_value=mean_val,
            median_value=median_val,
            min_value=min_val,
            max_value=max_val,
            stdev=stdev,
            q1_value=q1_val,
            q3_value=q3_val,
            p10_value=p10_val,
            p90_value=p90_val,
            valid_count=valid_count,
            null_count=null_count,
            data_quality=data_quality,
            analysis_date="2026-08-12",
        )

    @staticmethod
    def rank_company(
        company_metric: PeerMetric,
        peer_statistics: PeerStatistics,
    ) -> PeerRanking:
        """
        Rank single company within peer group for metric.

        Input: Company metric and peer statistics
        Output: PeerRanking with percentile, Z-score, ordinal rank
        """
        if company_metric.metric_value is None:
            return PeerRanking(
                company_id=company_metric.company_id,
                fiscal_year=company_metric.fiscal_year,
                metric_name=company_metric.metric_name,
                metric_value=None,
                percentile_rank=None,
                percentile_classification=PercentileRank.INSUFFICIENT_DATA,
                std_deviations_from_mean=None,
                distance_from_median=None,
                peer_rank=None,
                peer_count=peer_statistics.peer_count,
                formula_version="V1_PEER_STATISTICS",
            )

        if (
            peer_statistics.peer_count < 3
            or peer_statistics.median_value is None
        ):
            return PeerRanking(
                company_id=company_metric.company_id,
                fiscal_year=company_metric.fiscal_year,
                metric_name=company_metric.metric_name,
                metric_value=company_metric.metric_value,
                percentile_rank=None,
                percentile_classification=PercentileRank.INSUFFICIENT_DATA,
                std_deviations_from_mean=None,
                distance_from_median=None,
                peer_rank=None,
                peer_count=peer_statistics.peer_count,
                formula_version="V1_PEER_STATISTICS",
            )

        # Calculate Z-score
        z_score = None
        if peer_statistics.stdev and peer_statistics.stdev > 0:
            z_score = (
                company_metric.metric_value - peer_statistics.mean_value
            ) / peer_statistics.stdev

        # Distance from median
        distance = company_metric.metric_value - peer_statistics.median_value

        # Percentile rank (approximate using quartiles)
        percentile_rank = None
        if company_metric.metric_value >= peer_statistics.p90_value:  # type: ignore
            percentile_rank = 95.0
        elif company_metric.metric_value >= peer_statistics.q3_value:  # type: ignore
            percentile_rank = 82.5
        elif company_metric.metric_value >= peer_statistics.median_value:
            percentile_rank = 62.5
        elif company_metric.metric_value >= peer_statistics.q1_value:  # type: ignore
            percentile_rank = 37.5
        elif company_metric.metric_value >= peer_statistics.p10_value:  # type: ignore
            percentile_rank = 15.0
        else:
            percentile_rank = 5.0

        # Percentile classification
        if percentile_rank is None:
            classification = PercentileRank.INSUFFICIENT_DATA
        elif percentile_rank >= 90:
            classification = PercentileRank.TOP_DECILE
        elif percentile_rank >= 75:
            classification = PercentileRank.TOP_QUARTILE
        elif percentile_rank >= 50:
            classification = PercentileRank.ABOVE_MEDIAN
        elif percentile_rank >= 25:
            classification = PercentileRank.BELOW_MEDIAN
        elif percentile_rank >= 10:
            classification = PercentileRank.BOTTOM_QUARTILE
        else:
            classification = PercentileRank.BOTTOM_DECILE

        return PeerRanking(
            company_id=company_metric.company_id,
            fiscal_year=company_metric.fiscal_year,
            metric_name=company_metric.metric_name,
            metric_value=company_metric.metric_value,
            percentile_rank=percentile_rank,
            percentile_classification=classification,
            std_deviations_from_mean=z_score,
            distance_from_median=distance,
            peer_rank=None,  # Would need full peer list to calculate
            peer_count=peer_statistics.peer_count,
            formula_version="V1_PEER_STATISTICS",
        )

    @staticmethod
    def rank_peer_group(
        metrics: list[PeerMetric],
    ) -> tuple[PeerStatistics, list[PeerRanking]]:
        """
        Complete peer group analysis: statistics + individual rankings.

        Input: List of peer metrics
        Output: (PeerStatistics, list of PeerRanking for each company)
        """
        stats = PeerStatisticsEngine.calculate_statistics(metrics)
        rankings = []

        for metric in metrics:
            ranking = PeerStatisticsEngine.rank_company(metric, stats)
            rankings.append(ranking)

        return stats, rankings
