from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest

from accountant.db.models import Filing
from accountant.research.buy_board import _estimate_cc_valuation
from accountant.research.grading_engine import GradingInputs, ReportCardGradingEngine
from accountant.research.grading_evidence import (
    build_disclosure_evidence,
    sustained_beneish_evidence,
)


def inputs():
    return GradingInputs(90, 90, 90, 90, 90, 0, 0, 0, 0, data_completeness_pct=100)


def test_unknown_forensics_reduce_confidence_not_invent_a_veto():
    complete = ReportCardGradingEngine.grade(inputs())
    missing = ReportCardGradingEngine.grade(replace(inputs(), dechow_severity=None))
    assert missing.confidence == complete.confidence * 0.75
    assert not missing.veto_triggered


def test_legacy_quarterly_report_cannot_generate_annual_target():
    report = SimpleNamespace(
        key_stats={"net_income": 100, "shares_outstanding": 10},
        composite_score=90,
        stance="BULLISH",
    )
    assert _estimate_cc_valuation(None, report) is None


def test_duration_ratios_require_identical_windows():
    from accountant.research.annual_flows import AnnualFlow, aligned_value

    anchor = AnnualFlow(100, date(2025, 1, 1), date(2025, 12, 31), ())
    old = AnnualFlow(50, date(2024, 1, 1), date(2024, 12, 31), ())
    assert aligned_value(old, anchor) is None
    assert aligned_value(None, anchor) is None
    assert aligned_value(anchor, anchor) == 100


def test_app_uses_lifespan_not_deprecated_event_registration():
    from accountant.api.app import app

    assert not app.router.on_startup
    assert not app.router.on_shutdown


def disclosure(text, *, amended=False):
    filing = Filing(
        form_type="10-K/A" if amended else "8-K",
        is_amendment=amended,
        filing_date=date(2026, 10, 8),
        accession_number="test-accession",
        source_url="https://www.sec.gov/Archives/test.htm",
    )
    return build_disclosure_evidence(
        [filing], filing, sec_user_agent="unit test test@example.com", fetch_text=lambda *_: text
    )


def test_part_iii_amendment_has_no_amendment_only_penalty():
    evidence = disclosure(
        "This amendment is filed solely to supply the information in Part III.", amended=True
    )
    assert evidence.amendment_kind == "administrative_part_iii"
    assert evidence.event_severity == 0
    result = ReportCardGradingEngine.grade(
        replace(inputs(), event_flag_severity=evidence.event_severity)
    )
    assert result.grade == ReportCardGradingEngine.grade(inputs()).grade
    assert evidence.sources[0]["text_sha256"]


def test_affirmative_non_reliance_triggers_big_r_veto():
    evidence = disclosure(
        "Item 4.02. The previously issued financial statements should no longer be relied upon."
    )
    assert evidence.big_r_restatement is True
    result = ReportCardGradingEngine.grade(
        replace(inputs(), big_r_restatement_flag=evidence.big_r_restatement)
    )
    assert result.grade == "F"
    assert result.veto_reason == "Big-R restatement"


@pytest.mark.parametrize(
    "text",
    [
        "Item 4.02 Non-Reliance on Previously Issued Financial Statements",
        "There is no substantial doubt about our ability to continue as a going concern.",
        "Liquidity risks may raise substantial doubt about our ability to continue as a going concern.",
    ],
)
def test_heading_negative_or_conditional_text_does_not_trigger_veto(text):
    evidence = disclosure(text)
    assert evidence.big_r_restatement is False
    assert evidence.going_concern is False


def test_affirmative_going_concern_and_missing_text_are_distinct():
    evidence = disclosure(
        "There is substantial doubt about our ability to continue as a going concern."
    )
    assert evidence.going_concern is True
    unavailable = disclosure("")
    assert unavailable.going_concern is None
    assert unavailable.big_r_restatement is None
    assert unavailable.event_severity is None


def test_sustained_beneish_needs_two_consecutive_measured_periods(monkeypatch):
    import accountant.research.grading_evidence as module

    periods = [
        SimpleNamespace(fiscal_year=year, period_end=date(year, 12, 31))
        for year in (2025, 2024, 2023)
    ]
    monkeypatch.setattr(module, "_annual_periods", lambda _: periods)
    monkeypatch.setattr(module, "_beneish_m_score", lambda *_: -1.5)
    assert sustained_beneish_evidence([])["sustained"] is True
    periods.pop()
    assert sustained_beneish_evidence([])["sustained"] is False
    periods[1].fiscal_year = 2022
    assert sustained_beneish_evidence([])["sustained"] is False


@pytest.mark.asyncio
async def test_lifespan_cleans_up_even_when_startup_fails(monkeypatch):
    import accountant.api.app as module

    calls = []
    monkeypatch.setattr(module, "startup_machine", lambda: calls.append("start"))
    monkeypatch.setattr(module, "shutdown_machine", lambda: calls.append("stop"))
    async with module.lifespan(module.app):
        assert calls == ["start"]
    assert calls == ["start", "stop"]

    def fail():
        raise RuntimeError("injected startup failure")

    monkeypatch.setattr(module, "startup_machine", fail)
    with pytest.raises(RuntimeError, match="injected"):
        async with module.lifespan(module.app):
            pytest.fail("startup failure must not enter running state")
    assert calls[-1] == "stop"


def test_twelve_sec_clients_share_aggregate_request_budget(tmp_path):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    import httpx

    from accountant.config import Settings
    from accountant.sec import SecClient

    arrivals = []
    lock = threading.Lock()
    settings = Settings(
        data_dir=tmp_path, sec_user_agent="test test@example.com", sec_min_interval_seconds=0.1
    )

    def transport(_request):
        with lock:
            arrivals.append(time.monotonic())
        return httpx.Response(200, json={"cik": "0000000001"})

    def request(_index):
        with (
            httpx.Client(transport=httpx.MockTransport(transport)) as http,
            SecClient(settings=settings, http_client=http) as client,
        ):
            client.get_submissions("0000000001")

    with ThreadPoolExecutor(max_workers=12) as executor:
        list(executor.map(request, range(12)))
    assert len(arrivals) == 12
    for start in arrivals:
        assert sum(start <= instant < start + 1.0 for instant in arrivals) <= 10


def test_legacy_companyfacts_path_surfaces_payload_errors(monkeypatch):
    from unittest.mock import MagicMock, Mock

    import accountant.research.report_machine as module

    monkeypatch.setattr(module, "_latest_company_report", lambda *_: None)
    monkeypatch.setattr(
        module, "_count", lambda session, model, company_id: 1 if model is module.Filing else 0
    )
    monkeypatch.setattr(module, "SecClient", MagicMock())
    monkeypatch.setattr(module, "CompanyFactsClient", Mock())
    monkeypatch.setattr(
        module, "ingest_company_facts_payload", lambda *_: (1, 0, 0, ["missing provenance"])
    )
    session = Mock()
    company = SimpleNamespace(id="test-company", cik="0000000001")
    with pytest.raises(RuntimeError, match="provenance/payload errors"):
        module.ContinuousResearchMachine()._process_company(session, company, "SYN", 0)
    session.rollback.assert_called_once()


@pytest.mark.parametrize(
    "text,amended,expected_big_r",
    [
        ("This amendment is filed solely to provide Part III information.", True, False),
        ("Item 4.02. Our financial statements should no longer be relied upon.", False, True),
    ],
)
def test_report_build_persists_grading_evidence_without_external_calls(
    test_session, monkeypatch, text, amended, expected_big_r
):
    import accountant.research.filing_signal_engine as signals
    import accountant.research.grading_evidence as evidence
    import accountant.research.report_machine as machine
    from accountant.db.models import Company, ReportCard, Security

    company = Company(cik="0000000001", name="Synthetic operating issuer", entity_type="operating")
    test_session.add(company)
    test_session.flush()
    test_session.add(Security(company_id=company.id, ticker="SYN"))
    test_session.add(
        Filing(
            company_id=company.id,
            accession_number="0000000001-26-000001",
            form_type="10-K/A" if amended else "8-K",
            is_amendment=amended,
            filing_date=date(2026, 10, 8),
            report_date=date(2025, 12, 31),
            source_url="https://www.sec.gov/Archives/synthetic",
        )
    )
    test_session.commit()
    monkeypatch.setattr(signals, "fetch_filing_text", lambda *_: text)
    monkeypatch.setattr(evidence, "fetch_filing_text", lambda *_: text)
    monkeypatch.setattr(machine, "_resolved_current_price", lambda *_, **__: None)
    machine.ContinuousResearchMachine()._build_report(test_session, company, "SYN")
    test_session.commit()
    card = test_session.query(ReportCard).one()
    assert card.final_verdict["grading_rule_version"] == ReportCardGradingEngine.RULE_VERSION
    assert card.event_red_flags["disclosure_evidence"]["big_r_restatement"] is expected_big_r
    assert card.final_verdict["score_lineage"]["red_flag_penalty_source"][
        "event_flag_severity"
    ] == (95 if expected_big_r else 0)
    if expected_big_r:
        assert card.final_verdict["veto_reason"] == "Big-R restatement"
