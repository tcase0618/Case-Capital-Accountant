"""Historical snapshot engine: orchestrates point-in-time data collection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from accountant.analysis.point_in_time_engine import (
    HistoricalSnapshot,
    PointInTimeResolver,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class HistoricalSnapshotEngine:
    """
    Orchestrate construction of complete point-in-time snapshots.

    Combines:
    - Available filings (PointInTimeResolver.resolve_available_statements)
    - Raw facts (PointInTimeResolver.resolve_raw_facts)
    - Calculated metrics (PointInTimeResolver.resolve_metric)
    - Data quality assessment (ResearchDataQualityEngine)
    - Research classification (FundamentalResearchClassificationEngine)

    Result: Single HistoricalSnapshot object with complete context for
    research and backtesting at a specific historical date.
    """

    @staticmethod
    def build_snapshot(
        session: Session,
        company_id: str,
        as_of_date: str,  # YYYY-MM-DD
        include_peer_comparison: bool = False,
        include_research_classification: bool = False,
    ) -> HistoricalSnapshot:
        """
        Build complete snapshot of what was knowable at a point in time.

        This is the main entry point for point-in-time research.

        Args:
            session: Database session
            company_id: Company identifier
            as_of_date: Query date (YYYY-MM-DD)
            include_peer_comparison: Also get peer metrics for decile analysis
            include_research_classification: Also classify company at this date

        Returns:
            HistoricalSnapshot with complete availability picture
        """
        # Core snapshot from PointInTimeResolver
        snapshot = PointInTimeResolver.get_historical_snapshot(
            session=session,
            company_id=company_id,
            as_of_date=as_of_date,
        )

        # Could add additional enrichment here:
        # - Load peer data (if include_peer_comparison=True)
        # - Calculate research classification (if include_research_classification=True)
        # - Assess data quality
        # - Generate warnings for known issues

        return snapshot

    @staticmethod
    def build_snapshots_for_dates(
        session: Session,
        company_id: str,
        dates: list[str],  # Multiple YYYY-MM-DD dates
    ) -> list[HistoricalSnapshot]:
        """
        Build snapshots for multiple historical dates efficiently.

        Useful for backtesting (build monthly snapshots from 2020-2024).

        Args:
            session: Database session
            company_id: Company identifier
            dates: List of query dates (YYYY-MM-DD), sorted ascending

        Returns:
            List of HistoricalSnapshot objects, one per date
        """
        snapshots = []
        for date in sorted(dates):
            snapshot = HistoricalSnapshotEngine.build_snapshot(
                session=session,
                company_id=company_id,
                as_of_date=date,
            )
            snapshots.append(snapshot)
        return snapshots

    @staticmethod
    def compare_snapshots(
        snapshot1: HistoricalSnapshot,
        snapshot2: HistoricalSnapshot,
    ) -> dict[str, list[str]]:
        """
        Compare two snapshots to identify what changed over time.

        Returns dict mapping change type to list of items:
        - "new_filings": Filings added between dates
        - "amended": Statements amended between dates
        - "availability_improved": New metrics became available
        - "data_quality_changed": Coverage changed

        Args:
            snapshot1: Earlier snapshot
            snapshot2: Later snapshot

        Returns:
            Dict with lists of changes
        """
        changes = {
            "new_filings": [],
            "amended": [],
            "availability_improved": [],
            "data_quality_changed": [],
        }

        # Stub: Would compare statement IDs, coverage metrics, etc.

        return changes
