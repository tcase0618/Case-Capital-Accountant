"""Daily index retries do not depend on unrelated company filing dates."""

import importlib.util
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from accountant.db import create_session_factory
from accountant.db.models import SecIndexCheckpoint
from accountant.sec.exceptions import SecHttpError

spec = importlib.util.spec_from_file_location(
    "audit_index_import", Path(__file__).resolve().parents[1] / "scripts/import_stale_sec_filings.py",
)
index = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = index
spec.loader.exec_module(index)


def test_index_replays_three_business_days_and_pending_gap(test_engine):
    factory = create_session_factory(test_engine)
    with factory() as session:
        session.add(SecIndexCheckpoint(index_date=date(2026, 10, 7), status="completed"))
        session.commit()
    assert index._next_index_date(factory, date(2026, 10, 8)) == date(2026, 10, 2)
    with factory() as session:
        session.add(SecIndexCheckpoint(index_date=date(2026, 9, 25), status="pending"))
        session.commit()
    assert index._next_index_date(factory, date(2026, 10, 8)) == date(2026, 9, 25)


def test_throttled_date_remains_pending_then_retries(monkeypatch, test_engine):
    factory = create_session_factory(test_engine)
    client = MagicMock()
    client.__enter__.return_value = client
    client.get_text.side_effect = [
        SecHttpError(403, "test", "throttled"),
        "CIK|Company Name|Form Type|Date Filed|Filename\n123|Test|10-Q|2026-10-07|test.txt",
    ]
    monkeypatch.setattr(index, "SecClient", lambda **kwargs: client)
    day = date(2026, 10, 7)
    universe = {"0000000123": {"ticker": "TEST", "name": "Test"}}
    fetched = []
    assert index._load_matching_daily_index_filings(day, day, universe, forms=None, factory=factory, fetched_days=fetched) == []
    with factory() as session:
        checkpoint = session.get(SecIndexCheckpoint, day)
        assert checkpoint.status == "pending"
        assert checkpoint.fetched_at is None
    rows = index._load_matching_daily_index_filings(day, day, universe, forms=None, factory=factory, fetched_days=fetched)
    assert len(rows) == 1
    assert fetched == [day]
    assert client.get_text.call_count == 2
