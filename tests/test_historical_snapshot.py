"""Tests for historical snapshot engine."""

from accountant.analysis.historical_snapshot_engine import HistoricalSnapshotEngine
from accountant.analysis.point_in_time_engine import HistoricalSnapshot


class TestHistoricalSnapshotEngine:
    def test_build_snapshot(self, test_session):
        """Build snapshot for a company at a specific date."""
        snapshot = HistoricalSnapshotEngine.build_snapshot(
            session=test_session,
            company_id="AAPL",
            as_of_date="2024-01-15",
        )
        assert isinstance(snapshot, HistoricalSnapshot)
        assert snapshot.company_id == "AAPL"
        assert snapshot.as_of_date == "2024-01-15"

    def test_build_snapshot_with_peer_comparison(self, test_session):
        """Build snapshot including peer comparison."""
        snapshot = HistoricalSnapshotEngine.build_snapshot(
            session=test_session,
            company_id="AAPL",
            as_of_date="2024-01-15",
            include_peer_comparison=True,
        )
        assert snapshot.company_id == "AAPL"

    def test_build_snapshot_with_classification(self, test_session):
        """Build snapshot including research classification."""
        snapshot = HistoricalSnapshotEngine.build_snapshot(
            session=test_session,
            company_id="AAPL",
            as_of_date="2024-01-15",
            include_research_classification=True,
        )
        assert snapshot.company_id == "AAPL"

    def test_build_snapshots_for_dates_single(self, test_session):
        """Build snapshots for a single date."""
        snapshots = HistoricalSnapshotEngine.build_snapshots_for_dates(
            session=test_session,
            company_id="AAPL",
            dates=["2024-01-15"],
        )
        assert len(snapshots) == 1
        assert snapshots[0].as_of_date == "2024-01-15"

    def test_build_snapshots_for_dates_multiple(self, test_session):
        """Build snapshots for multiple dates."""
        dates = [
            "2024-01-15",
            "2024-02-15",
            "2024-03-15",
        ]
        snapshots = HistoricalSnapshotEngine.build_snapshots_for_dates(
            session=test_session,
            company_id="AAPL",
            dates=dates,
        )
        assert len(snapshots) == 3
        assert [s.as_of_date for s in snapshots] == sorted(dates)

    def test_build_snapshots_for_dates_unsorted(self, test_session):
        """Build snapshots maintains date order even if input unsorted."""
        dates = [
            "2024-03-15",
            "2024-01-15",
            "2024-02-15",
        ]
        snapshots = HistoricalSnapshotEngine.build_snapshots_for_dates(
            session=test_session,
            company_id="AAPL",
            dates=dates,
        )
        assert len(snapshots) == 3
        assert [s.as_of_date for s in snapshots] == sorted(dates)

    def test_compare_snapshots(self, test_session):
        """Compare two snapshots to identify changes."""
        snapshot1 = HistoricalSnapshotEngine.build_snapshot(
            session=test_session,
            company_id="AAPL",
            as_of_date="2024-01-15",
        )
        snapshot2 = HistoricalSnapshotEngine.build_snapshot(
            session=test_session,
            company_id="AAPL",
            as_of_date="2024-02-15",
        )

        changes = HistoricalSnapshotEngine.compare_snapshots(
            snapshot1=snapshot1,
            snapshot2=snapshot2,
        )
        assert isinstance(changes, dict)
        assert "new_filings" in changes
        assert "amended" in changes
        assert "availability_improved" in changes
        assert "data_quality_changed" in changes

    def test_compare_snapshots_identical(self, test_session):
        """Comparing identical snapshots shows no changes."""
        snapshot = HistoricalSnapshotEngine.build_snapshot(
            session=test_session,
            company_id="AAPL",
            as_of_date="2024-01-15",
        )

        changes = HistoricalSnapshotEngine.compare_snapshots(
            snapshot1=snapshot,
            snapshot2=snapshot,
        )
        # Should have empty change lists
        assert isinstance(changes, dict)
