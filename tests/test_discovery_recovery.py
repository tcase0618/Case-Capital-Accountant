from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from argparse import Namespace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from accountant.db import create_session_factory
from accountant.db.models import Company, Filing
from accountant.sec import discovery_state as ds

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_stale_sec_filings.py"
SPEC = importlib.util.spec_from_file_location("discovery_import_test", SCRIPT)
importer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = importer
SPEC.loader.exec_module(importer)

DAY = date(2026, 10, 20)
CIK = "0000000001"
A = "0000000001-26-000001"
B = "0000000001-26-000002"


def test_discovery_does_not_invent_failed_indexes_on_edgar_holidays(tmp_path):
    state = ds.DiscoveryState(tmp_path / "checkpoint.json")
    days = state.dates(date(2026, 10, 20), date(2026, 10, 9), date(2026, 10, 13))
    assert days == [date(2026, 10, 9), date(2026, 10, 13)]


def test_each_company_admission_honors_storage_reserve(tmp_path, monkeypatch):
    monkeypatch.setattr(importer, "get_settings", lambda: SimpleNamespace(
        storage_max_database_gb=14, storage_min_free_disk_gb=25,
        storage_worker_reserve_mb=128, data_dir=tmp_path,
    ))
    monkeypatch.setattr(importer.shutil, "disk_usage", lambda _: SimpleNamespace(free=30 * 1024**3))
    session = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        execute=lambda _: SimpleNamespace(scalar_one=lambda: 14 * 1024**3 - 64 * 1024**2),
    )
    with pytest.raises(importer.StoragePaused, match="database_cap_reached"):
        importer._require_storage_headroom(session)


@pytest.mark.parametrize("filename_header", ["File Name", "Filename"])
@pytest.mark.parametrize("filed", [DAY, date(2025, 2, 28)])
def test_real_edgar_header_and_compact_date_are_accepted(monkeypatch, filename_header, filed):
    # Shape observed in the official October 21 daily dissemination feed.
    body = (
        "Description: Daily Index of EDGAR Dissemination Feed\n"
        f"CIK|Company Name|Form Type|Date Filed|{filename_header}\n"
        "----------------------------------------------------------------\n"
        f"1|One|10-K|{filed:%Y%m%d}|edgar/data/1/{A}.txt\n"
    )
    monkeypatch.setattr(importer, "get_settings", lambda: SimpleNamespace(
        sec_user_agent="Case Capital offline test test@example.com", sec_timeout_seconds=5,
    ))
    monkeypatch.setattr(httpx.Client, "get", lambda *a, **k: httpx.Response(
        200, text=body, request=httpx.Request("GET", "https://www.sec.gov/test.idx"),
    ))
    rows = importer._load_matching_daily_index_filings(
        DAY, DAY, {CIK: {"ticker": "ONE"}}, forms={"10-K"},
    )
    assert len(rows) == 1
    assert rows[0].filing_date == filed
    assert rows[0].cik == CIK


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("HTTP forbidden")

    monkeypatch.setattr(httpx.Client, "send", forbidden)


@pytest.fixture
def harness(tmp_path, monkeypatch, test_engine):
    factory = create_session_factory(test_engine)
    monkeypatch.setattr(
        importer, "get_settings", lambda: SimpleNamespace(sec_min_interval_seconds=0)
    )
    universe = {CIK: {"ticker": "ONE", "name": "One"}}
    monkeypatch.setattr(importer, "_load_universe", lambda _: universe)
    payload = {
        "cik": CIK,
        "name": "One",
        "tickers": ["ONE"],
        "exchanges": ["NYSE"],
        "filings": {
            "recent": {"accessionNumber": [A], "form": ["10-K"], "filingDate": [DAY.isoformat()]},
            "files": [],
        },
    }
    calls = []
    shards = {}

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_submissions(self, cik):
            calls.append(cik)
            if isinstance(payload.get("error"), Exception):
                raise payload["error"]
            return payload

        def get_submissions_file(self, name):
            calls.append(name)
            return shards[name]

    monkeypatch.setattr(importer, "SecClient", Client)
    rows = [importer.IndexFiling(CIK, "One", "10-K", DAY, f"edgar/data/1/{A}.txt")]
    monkeypatch.setattr(importer, "_load_matching_daily_index_filings", lambda *a, **k: rows)
    args = Namespace(
        from_date=DAY.isoformat(), to_date=DAY.isoformat(), forms="useful", workers=1, limit=None
    )
    path = tmp_path / "checkpoint.json"

    def run():
        return importer._run_discovery(factory, ds.DiscoveryState(path), args, DAY)

    return SimpleNamespace(**locals())


def test_failed_index_survives_restart(harness, monkeypatch):
    h = harness

    def fail(*a, **k):
        raise RuntimeError("unavailable")

    monkeypatch.setattr(importer, "_load_matching_daily_index_filings", fail)
    assert h.run() == 1
    assert not ds.DiscoveryState(h.path).entry(DAY)["ok"]
    monkeypatch.setattr(importer, "_load_matching_daily_index_filings", lambda *a, **k: h.rows)
    assert h.run() == 0
    assert ds.DiscoveryState(h.path).entry(DAY)["done"][CIK] == [A]


def test_same_day_repeat_discovers_late_filing(harness):
    h = harness
    assert h.run() == 0
    assert h.run() == 0
    assert h.calls == [CIK]
    h.rows.append(importer.IndexFiling(CIK, "One", "10-Q", DAY, f"edgar/data/1/{B}.txt"))
    for key, value in (("accessionNumber", B), ("form", "10-Q"), ("filingDate", DAY.isoformat())):
        h.payload["filings"]["recent"][key].append(value)
    assert h.run() == 0
    assert h.calls == [CIK, CIK]
    assert ds.DiscoveryState(h.path).entry(DAY)["done"][CIK] == [A, B]


def test_company_error_replayed_after_restart(harness):
    h = harness
    h.payload["error"] = RuntimeError("company failure")
    assert h.run() == 1
    assert ds.DiscoveryState(h.path).entry(DAY)["pending"][CIK] == [A]
    del h.payload["error"]
    # Retry does not depend on the company appearing in the next index response.
    h.rows.clear()
    assert h.run() == 0
    assert h.calls == [CIK, CIK]


def test_no_success_on_commit_failure(harness, monkeypatch):
    h = harness
    from sqlalchemy.orm import Session

    original = Session.commit

    def fail(self):
        raise RuntimeError("commit failed")

    monkeypatch.setattr(Session, "commit", fail)
    assert h.run() == 1
    assert not ds.DiscoveryState(h.path).entry(DAY)["done"]
    monkeypatch.setattr(Session, "commit", original)
    assert h.run() == 0


def test_missing_recent_requires_historical_shard(harness):
    h = harness
    with h.factory() as session:
        session.add(Company(cik=CIK, name="Already known"))
        session.commit()
    h.payload["filings"]["recent"] = {}
    assert h.run() == 1
    h.payload["filings"]["files"] = [{"name": "old.json"}]
    h.shards["old.json"] = {
        "accessionNumber": [A],
        "form": ["10-K"],
        "filingDate": [DAY.isoformat()],
    }
    assert h.run() == 0
    assert "old.json" in h.calls


def test_wrong_company_payload_is_not_committed(harness):
    h = harness
    h.payload["cik"] = "0000000002"
    assert h.run() == 1
    with h.factory() as session:
        assert session.execute(select(Company)).first() is None


def test_crash_after_commit_recovery_needs_no_fetch(harness, monkeypatch):
    h = harness
    original = ds.DiscoveryState.save

    def fail_after_done(self, today):
        if any(e["done"] for e in self.days.values()):
            raise OSError("checkpoint disk failure after commit")
        return original(self, today)

    monkeypatch.setattr(ds.DiscoveryState, "save", fail_after_done)
    assert h.run() == 1
    assert ds.DiscoveryState(h.path).entry(DAY)["pending"][CIK] == [A]
    monkeypatch.setattr(ds.DiscoveryState, "save", original)
    assert h.run() == 0
    assert h.calls == [CIK]


def test_old_company_failure_replays_outside_poll_window(harness):
    h = harness
    old = DAY - timedelta(days=100)
    state = ds.DiscoveryState(h.path)
    entry = state.entry(old)
    entry["ok"] = True
    entry["pending"][CIK] = [A]
    state.save(DAY)
    h.rows.clear()
    h.args.from_date = None
    assert h.run() == 0
    assert h.calls == [CIK]


def test_pruning_never_discards_failures(tmp_path):
    state = ds.DiscoveryState(tmp_path / "s.json")
    old = DAY - timedelta(days=100)
    state.entry(old)["ok"] = True
    state.entry(old + timedelta(days=1))
    entry = state.entry(old + timedelta(days=2))
    entry["ok"] = True
    entry["pending"][CIK] = [A]
    state.save(DAY)
    saved = ds.DiscoveryState(state.path)
    assert old.isoformat() not in saved.days
    assert (old + timedelta(days=1)).isoformat() in saved.days
    assert (old + timedelta(days=2)).isoformat() in saved.days


def test_default_poll_ignores_future_global_filing(harness, monkeypatch):
    h = harness
    with h.factory() as session:
        company = Company(cik=CIK, name="One")
        session.add(company)
        session.flush()
        session.add(
            Filing(
                company_id=company.id,
                accession_number=B,
                form_type="10-K",
                filing_date=date(2099, 1, 1),
            )
        )
        session.commit()
    h.args.from_date = None
    seen = []

    def indexes(day, end, *a, **k):
        seen.append(day)
        return h.rows if day == DAY else []

    monkeypatch.setattr(importer, "_load_matching_daily_index_filings", indexes)
    assert h.run() == 0
    assert DAY in seen and len(seen) <= 23
    assert h.calls == [CIK]


def test_existing_accession_avoids_submissions_and_shard(harness):
    h = harness
    with h.factory() as session:
        company = Company(cik=CIK, name="One")
        session.add(company)
        session.flush()
        session.add(
            Filing(company_id=company.id, accession_number=A, form_type="10-K", filing_date=DAY)
        )
        session.commit()
    h.payload["error"] = RuntimeError("must not fetch")
    assert h.run() == 0
    assert not h.calls


def test_verification_rejects_noop_ingestion(harness, monkeypatch):
    monkeypatch.setattr(
        importer,
        "ingest_company_filings_payload",
        lambda *a: SimpleNamespace(inserted=0, skipped=1),
    )
    assert harness.run() == 1
    assert ds.DiscoveryState(harness.path).entry(DAY)["pending"][CIK] == [A]
    with harness.factory() as session:
        assert session.execute(select(Filing)).first() is None


def test_index_retry_fairness_overlap_and_history_cap(tmp_path):
    state = ds.DiscoveryState(tmp_path / "s.json")
    old = DAY - timedelta(days=300)
    for i in range(40):
        state.entry(old + timedelta(days=i))
    seen = set()
    for _ in range(4):
        dates = state.dates(DAY, None, DAY)
        assert len(dates) <= 33
        assert {DAY, DAY - timedelta(days=1), DAY - timedelta(days=4)} <= set(dates)
        for d in dates:
            state.entry(d)["attempts"] += 1
            seen.add(d)
    assert all(old + timedelta(days=i) in seen for i in range(40))


def test_limit_does_not_starve_later_company(harness):
    h = harness
    other = "0000000002"
    h.universe[other] = {"ticker": "TWO", "name": "Two"}
    h.rows.append(
        importer.IndexFiling(other, "Two", "10-K", DAY, "edgar/data/2/0000000002-26-000001.txt")
    )
    h.payload["error"] = RuntimeError("permanent failure")
    h.args.limit = 1
    assert h.run() == 1
    assert h.run() == 1
    assert h.calls == [CIK, other]


@pytest.mark.parametrize(
    "start,end", [(DAY + timedelta(days=1), DAY), (None, DAY + timedelta(days=1))]
)
def test_reject_invalid_or_future_range(tmp_path, start, end):
    with pytest.raises(ValueError):
        ds.DiscoveryState(tmp_path / "s.json").dates(DAY, start, end)


def test_explicit_backfill_not_capped(tmp_path):
    state = ds.DiscoveryState(tmp_path / "s.json")
    assert len(state.dates(DAY, DAY - timedelta(days=100), DAY)) > 60


def test_checkpoint_atomic_bounded_and_corruption_fail_closed(tmp_path, monkeypatch):
    path = tmp_path / "s.json"
    state = ds.DiscoveryState(path)
    state.entry(DAY)
    state.save(DAY)
    before = path.read_bytes()
    monkeypatch.setattr(ds, "MAX_BYTES", 20)
    with pytest.raises(ValueError):
        state.save(DAY)
    assert path.read_bytes() == before
    monkeypatch.setattr(ds, "MAX_BYTES", 10000)

    def fail(*a):
        raise OSError("replace failed")

    monkeypatch.setattr(ds.os, "replace", fail)
    with pytest.raises(OSError):
        state.save(DAY)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
    path.write_text('{"version":99,"days":{}}')
    with pytest.raises(ValueError):
        ds.DiscoveryState(path)


def test_lock_excludes_second_writer_and_releases(tmp_path):
    path = tmp_path / "s.json"
    with ds.checkpoint_lock(path), pytest.raises(OSError), ds.checkpoint_lock(path):
        pytest.fail("second writer entered")
    with ds.checkpoint_lock(path):
        pass


def test_lock_excludes_other_process(tmp_path):
    path = tmp_path / "s.json"
    code = (
        f"import sys; sys.path.insert(0, {str(SCRIPT.parents[1] / 'src')!r}); "
        "from pathlib import Path; from accountant.sec.discovery_state import checkpoint_lock; "
        f"lock = checkpoint_lock(Path({str(path)!r})); lock.__enter__()"
    )
    with ds.checkpoint_lock(path):
        blocked = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=10)
        assert blocked.returncode != 0
        assert b"ImportError" not in blocked.stderr
    released = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=10)
    assert released.returncode == 0, released.stderr


def test_future_checkpoint_fails_closed(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "days": {"2099-01-01": {"ok": True, "pending": {}, "done": {}, "attempts": 1}},
            }
        )
    )
    with pytest.raises(ValueError):
        ds.DiscoveryState(path)


@pytest.mark.parametrize("status", [403, 404, 500])
def test_http_failures_are_not_empty_success(monkeypatch, status):
    monkeypatch.setattr(
        importer,
        "get_settings",
        lambda: SimpleNamespace(sec_user_agent="Test x@example.com", sec_timeout_seconds=1),
    )

    def response(*a, **k):
        return httpx.Response(status, request=httpx.Request("GET", "https://example.test"))

    monkeypatch.setattr(httpx.Client, "get", response)
    with pytest.raises(RuntimeError):
        importer._load_matching_daily_index_filings(DAY, DAY, {}, forms=None)


@pytest.mark.parametrize(
    "text",
    [
        "<html>blocked</html>",
        "CIK|Company Name|Form Type|Date Filed|Filename\n1|One|10-K|bad|edgar/data/1/0000000001-26-000001.txt",
    ],
)
def test_malformed_index_not_empty_success(monkeypatch, text):
    monkeypatch.setattr(
        importer,
        "get_settings",
        lambda: SimpleNamespace(sec_user_agent="Test x@example.com", sec_timeout_seconds=1),
    )
    monkeypatch.setattr(
        httpx.Client,
        "get",
        lambda *a, **k: httpx.Response(
            200, text=text, request=httpx.Request("GET", "https://example.test")
        ),
    )
    with pytest.raises(ValueError):
        importer._load_matching_daily_index_filings(DAY, DAY, {}, forms=None)
