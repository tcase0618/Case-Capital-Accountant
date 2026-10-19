import importlib.util
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from accountant.db.models import Filing
from accountant.research.filing_signal_engine import build_event_red_flags, build_governance_signals
from accountant.research.grading_evidence import build_disclosure_evidence


@pytest.mark.parametrize(
    "reason",
    [
        "because they do not comply with GAAP",
        "as they may contain material errors",
        "although no cash balances were affected",
    ],
)
def test_non_reliance_determination_is_not_negated_by_its_reason(reason):
    filing = Filing(
        form_type="8-K",
        filing_date=date(2026, 10, 19),
        source_url="fixture",
        accession_number="fixture",
    )
    evidence = build_disclosure_evidence(
        [filing],
        filing,
        sec_user_agent="Test test@example.com",
        fetch_text=lambda *_: (
            "The Audit Committee determined that the financial statements "
            f"should no longer be relied upon {reason}."
        ),
    )
    assert evidence.big_r_restatement is True
    assert evidence.event_severity == 95


@pytest.mark.parametrize("wall_clock", [date(2026, 10, 19), date(2027, 6, 1)])
def test_signal_windows_do_not_depend_on_wall_clock(monkeypatch, wall_clock):
    import accountant.research.filing_signal_engine as module

    class Clock(date):
        @classmethod
        def today(cls):
            return wall_clock

    monkeypatch.setattr(module, "date", Clock)
    filings = [
        Filing(form_type="4", filing_date=date(2026, 7, 20), accession_number="sell-1"),
        Filing(form_type="4", filing_date=date(2026, 8, 1), accession_number="sell-2"),
        Filing(form_type="4", filing_date=date(2026, 8, 2), accession_number="future"),
    ]
    result = build_governance_signals(filings, as_of=date(2026, 8, 1), sec_user_agent="test")
    assert result.form4_filing_count_90d == 2
    assert result.insider_net_shares_bought_90d is None
    assert result.insider_buy_cluster_flag is None
    assert result.source_accessions == ("sell-1", "sell-2")
    assert result.as_of_date == "2026-08-01"


def test_event_windows_exclude_future_and_use_most_recent_disclosure():
    filings = [
        Filing(form_type="8-K", filing_date=date(2026, 5, 1), source_url="old"),
        Filing(form_type="CORRESP", filing_date=date(2027, 1, 1)),
        Filing(form_type="8-K", filing_date=date(2026, 8, 1), source_url="new"),
    ]
    result = build_event_red_flags(
        filings,
        as_of=date(2026, 8, 1),
        sec_user_agent="test",
        fetch_text=lambda *_: "The auditor dismissed Deloitte as its accounting firm.",
    )
    assert result.sec_comment_letter_flag is False
    assert result.auditor_change_date == "2026-08-01"
    assert result.auditor_tenure_years == 0


def test_governance_count_includes_cutoff_but_not_older_or_future_filings():
    filings = [
        Filing(form_type="4", filing_date=date(2026, 5, day), accession_number=str(day))
        for day in (2, 3)
    ]
    result = build_governance_signals(filings, as_of=date(2026, 8, 1), sec_user_agent="test")
    assert result.form4_filing_count_90d == 1
    assert result.source_accessions == ("3",)


def test_readiness_reads_scheduler_status_and_rejects_missing_failed_stale(tmp_path):
    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location(
        "readiness", root / "scripts/vps_readiness_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "status.json"
    assert not module.scheduler_status(path)["ok"]
    status = {"last_cycle_at": datetime.now(UTC).isoformat(), "status": "complete", "exit_code": 0}
    path.write_text(json.dumps(status))
    assert module.scheduler_status(path)["ok"]
    status.update(status="failed", exit_code=7)
    path.write_text(json.dumps(status))
    assert not module.scheduler_status(path)["ok"]
    status.update(status="complete", exit_code=0, last_cycle_at="2020-01-01T00:00:00Z")
    path.write_text(json.dumps(status))
    assert not module.scheduler_status(path)["ok"]


def test_every_mutation_route_requires_operator_auth():
    from fastapi.routing import APIRoute

    from accountant.api.app import app
    from accountant.api.auth import require_api_token

    def dependencies(dependant):
        yield dependant.call
        for child in dependant.dependencies:
            yield from dependencies(child)

    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.methods - {"GET", "HEAD", "OPTIONS"}
    ]
    assert routes
    for route in routes:
        assert require_api_token in set(dependencies(route.dependant)), route.path
