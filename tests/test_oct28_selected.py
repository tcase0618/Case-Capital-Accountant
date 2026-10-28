"""Independently selected audit regressions adapted to current main."""

from unittest.mock import Mock

import pytest

from accountant.db.models import Company


def test_deployment_gates_reject_live_thread_with_storage_pause(test_session, monkeypatch):
    import accountant.api.app as module

    monkeypatch.setattr(
        module.MACHINE,
        "snapshot",
        lambda: {
            "running": True,
            "storage_blocked": True,
            "storage_block_reason": "database_cap_reached",
            "blocked_companies": 0,
        },
    )
    monkeypatch.setattr(
        module, "build_source_integrity_snapshot", lambda _: {"source_grade": "STRONG"}
    )
    response = module.deployment_readiness(test_session)
    gates = {gate["name"]: gate for gate in response.gates}
    assert not gates["machine_running"]["passed"]
    assert not gates["blocked_companies"]["passed"]


@pytest.mark.parametrize(
    "candidates,successes,expected_error",
    [(3, 0, True), (3, 2, True), (3, 3, False), (0, 0, False)],
)
def test_buy_board_refresh_exposes_total_or_partial_quote_failure(
    monkeypatch, candidates, successes, expected_error
):
    from accountant.research import buy_board as module

    engine = Mock()
    session = Mock()
    monkeypatch.setattr(module, "create_db_engine", lambda: engine)
    monkeypatch.setattr(module, "create_session_factory", lambda _: lambda: session)
    monkeypatch.setattr(
        module,
        "refresh_buy_board_prices",
        lambda *_, **__: {
            "candidate_count": candidates,
            "updated": successes,
            "successes": successes,
            "session_label": "TEST",
        },
    )
    board = module.BuyBoardScheduler()
    board._refresh("test")
    status = board.snapshot()
    assert bool(status["last_error"]) is expected_error
    assert status["last_success_count"] == successes


def test_actual_all_failure_quote_refresh_is_visible(test_session, monkeypatch):
    from accountant.db.models import BuyBoardCandidate
    from accountant.research import buy_board as module

    for index, ticker in enumerate(("AAA", "BBB"), 1):
        company = Company(cik=f"{index:010d}", name=ticker)
        test_session.add(company)
        test_session.flush()
        test_session.add(
            BuyBoardCandidate(
                company_id=company.id, ticker=ticker, company_name=ticker, status="ACTIVE"
            )
        )
    test_session.commit()
    monkeypatch.setattr(module, "create_db_engine", Mock())
    monkeypatch.setattr(module, "create_session_factory", lambda _: lambda: test_session)
    quote = Mock(return_value={"ok": False, "reason": "fixture market data unavailable"})
    monkeypatch.setattr(module, "alpaca_quote", quote)
    board = module.BuyBoardScheduler()
    result = board._refresh("fixture")
    assert result["candidate_count"] == quote.call_count == 2
    assert result["successes"] == 0
    assert board.snapshot()["last_error"]
