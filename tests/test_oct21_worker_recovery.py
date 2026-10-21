"""ACC-HIGH-003/004/005 and MED-013: exercise admission and persisted rotation."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

from accountant.config import Settings
from accountant.db.models import Company, Filing, Security
from accountant.research import report_machine as module
from accountant.research.report_machine import ContinuousResearchMachine


@pytest.mark.parametrize("restart_after", [None, 1])
def test_filings_workers_rotate_all_companies_using_persisted_checks(
    test_session, monkeypatch, restart_after
):
    monkeypatch.setattr(module, "get_settings", lambda: Settings(machine_workers=2))
    monkeypatch.setattr(module, "SecClient", MagicMock())
    fetch = Mock(return_value={})
    monkeypatch.setattr(module, "fetch_company_filings_payload", fetch)
    monkeypatch.setattr(module, "ingest_company_filings_payload", lambda *_: None)
    for index, ticker in enumerate(("AAA", "BBB", "CCC", "DDD", "EEE", "FFF"), 1):
        company = Company(cik=f"{index:010d}", name=f"Fixture {ticker}", entity_type="operating")
        test_session.add(company)
        test_session.flush()
        test_session.add(
            Security(company_id=company.id, ticker=ticker, security_type="common_stock")
        )
        test_session.add(
            Filing(
                company_id=company.id,
                accession_number=f"fixture-{index}",
                form_type="10-K",
                filing_date=date(2026, 10, 8),
            )
        )
    test_session.commit()
    machine = ContinuousResearchMachine()
    seen = []
    for cycle in range(3):
        if cycle == restart_after:
            test_session.expire_all()
            machine = ContinuousResearchMachine()
        assignments = machine._load_role_assignments(test_session)
        assert len(assignments) == 2
        for assignment in assignments:
            assert assignment["lane"] == "filings"
            company = test_session.get(Company, assignment["company_id"])
            assert machine._refresh_company_filings(
                test_session,
                company,
                assignment["ticker"],
                int(assignment["worker_id"]) - 1,
                role=assignment["role"],
            )
            seen.append(assignment["ticker"])
    assert seen == ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    assert all(not call.kwargs["include_historical_files"] for call in fetch.call_args_list)
    assert all(company.filings_checked_at is not None for company in test_session.query(Company))


def test_worker_retries_rolls_back_and_releases_admission_after_failure(monkeypatch):
    machine = ContinuousResearchMachine()
    gate = Mock()
    gate.claim.return_value = True
    machine._storage_gate = gate
    session = Mock()
    session.get.return_value = SimpleNamespace(id="fixture")
    lane = Mock(side_effect=RuntimeError("[SQL: private details]"))
    monkeypatch.setattr(machine, "_process_company_lane", lane)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    assignments = [
        {
            "worker_id": 1,
            "role": "STATEMENTS",
            "lane": "statements",
            "company_id": "fixture",
            "ticker": "SYN",
        }
    ]
    assert machine._process_role_assignments(lambda: session, assignments) == []
    assert lane.call_count == session.rollback.call_count == 2
    gate.release.assert_called_once()
    session.close.assert_called_once()
    snapshot = machine.snapshot()
    assert snapshot["worker_states"][0]["status"] == "error"
    assert snapshot["last_error"] == "research_worker_error"
    assert len(snapshot["recent_errors"]) == 2
    assert "private details" not in str(snapshot)


def test_storage_denial_does_not_start_a_worker_lane():
    machine = ContinuousResearchMachine()
    gate = Mock(stop_reason="database_cap_reached")
    gate.claim.return_value = False
    machine._storage_gate = gate
    session = Mock()
    lane = Mock()
    machine._process_company_lane = lane
    assignments = [
        {
            "worker_id": 1,
            "role": "STATEMENTS",
            "lane": "statements",
            "company_id": "fixture",
            "ticker": "SYN",
        }
    ]
    assert machine._process_role_assignments(lambda: session, assignments) == []
    lane.assert_not_called()
    session.get.assert_not_called()
    gate.release.assert_not_called()  # A denied claim has already released its lock.
    session.close.assert_called_once()
    assert machine.snapshot()["storage_blocked"]


def test_loop_exception_is_reported_and_next_cycle_runs(monkeypatch):
    machine = ContinuousResearchMachine()
    calls = []

    def cycle():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("injected loop failure")
        machine._stop.set()
        return False

    monkeypatch.setattr(machine, "_run_cycle", cycle)
    monkeypatch.setattr(machine._wake, "wait", lambda **_: None)
    machine._run()
    assert len(calls) == 2
    assert machine.snapshot()["last_error"] == "research_worker_error"


def test_error_is_retained_until_three_successful_cycles(monkeypatch):
    machine = ContinuousResearchMachine()
    engine = Mock()
    monkeypatch.setattr(module, "create_db_engine", lambda: engine)
    monkeypatch.setattr(module, "create_session_factory", lambda _: Mock(return_value=Mock()))
    monkeypatch.setattr(module.StorageGate, "from_settings", lambda _: Mock())
    monkeypatch.setattr(machine, "_storage_preflight", lambda _: SimpleNamespace(allowed=True))
    monkeypatch.setattr(machine, "_sync_universes_if_needed", lambda _: None)
    monkeypatch.setattr(machine, "_load_role_assignments", lambda _: [])
    monkeypatch.setattr(
        machine,
        "_refresh_progress_snapshot",
        lambda _: {
            "pending_companies": 0,
            "runnable_companies": 0,
            "blocked_companies": 0,
            "blocked_examples": [],
        },
    )
    machine._record_error("injected error")
    for _ in range(2):
        machine._run_cycle()
        assert machine.snapshot()["last_error"]
    machine._run_cycle()
    assert machine.snapshot()["last_error"] is None
    assert len(machine.snapshot()["recent_errors"]) == 1


@pytest.mark.parametrize("postgres", [True, False])
def test_storage_preflight_uses_real_size_disk_and_original_cycle_baseline(
    tmp_path, monkeypatch, postgres
):
    machine = ContinuousResearchMachine()
    machine._storage_gate = SimpleNamespace(_start_database_bytes=0)
    settings = Settings(
        data_dir=tmp_path, storage_max_cycle_growth_gb=0.25, storage_worker_reserve_mb=128
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module.shutil, "disk_usage", lambda _: SimpleNamespace(free=1024**3))
    engine = MagicMock()
    engine.dialect.name = "postgresql" if postgres else "sqlite"
    engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = (
        200 * 1024**2
    )
    decision = machine._storage_preflight(engine)
    assert decision.allowed is (not postgres)
    if postgres:
        assert decision.reason == "cycle_growth_cap_reached"
