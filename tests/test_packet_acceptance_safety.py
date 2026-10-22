from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from accountant.research.packet_acceptance import REQUIRED_QA_CHECKS, evaluate_packet_acceptance


@pytest.fixture
def valid_inputs():
    now = datetime(2026, 10, 21, 12, tzinfo=UTC)
    report = SimpleNamespace(
        ticker="AAPL", company_id="c", pipeline_stage="reports-ready",
        data_quality_tier="ADEQUATE", updated_at=now,
        as_of_date="2026-10-21", composite_score=80,
    )
    card = SimpleNamespace(
        ticker="AAPL", company_id="c", accepted_at=now - timedelta(days=30),
        final_verdict={
            "grade_score": 80, "last_scored_ts": now.isoformat(),
            "calculation_validation": {
                "version": "FINANCIAL_QA_V1", "status": "PASS", "input_fingerprint": "fixture",
                "checks": dict.fromkeys(REQUIRED_QA_CHECKS, True),
            },
        },
    )
    return dict(
        ticker="AAPL", report=report, card=card, now=now,
        mode={"terminal_handoff_allowed": True, "execution_allowed": False, "research_only": True},
        source={"source_grade": "STRONG", "sec": {"latest_filing_date": "2026-10-20"}},
        storage_blocked=False,
    )


def test_only_verified_current_research_is_accepted(valid_inputs):
    assert evaluate_packet_acceptance(**valid_inputs)["accepted"] is True


@pytest.mark.parametrize("key,value,reason", [
    ("storage_blocked", True, "pipeline_storage_blocked"),
    ("report", None, "report_or_card_missing"),
    ("card", None, "report_or_card_missing"),
])
def test_explicit_incomplete_inputs_fail_closed(valid_inputs, key, value, reason):
    valid_inputs[key] = value
    acceptance = evaluate_packet_acceptance(**valid_inputs)
    assert acceptance["accepted"] is False
    assert reason in acceptance["reasons"]


def test_ready_stage_does_not_override_legacy_or_missing_qa(valid_inputs):
    valid_inputs["card"].final_verdict.pop("calculation_validation")
    assert "financial_qa_unverified" in evaluate_packet_acceptance(**valid_inputs)["reasons"]


def test_handoff_policy_cannot_be_overridden_by_successful_transport(valid_inputs):
    valid_inputs["mode"]["terminal_handoff_allowed"] = False
    assert "terminal_handoff_disallowed" in evaluate_packet_acceptance(**valid_inputs)["reasons"]


@pytest.mark.parametrize("filing", [None, "bad", "2026-10-22", "2026-10-06"])
def test_source_dates_are_not_packet_generation_dates(valid_inputs, filing):
    valid_inputs["source"]["sec"]["latest_filing_date"] = filing
    assert evaluate_packet_acceptance(**valid_inputs)["accepted"] is False


def test_contradictory_score_or_identity_is_rejected(valid_inputs):
    valid_inputs["report"].composite_score = 90
    valid_inputs["card"].ticker = "MSFT"
    reasons = evaluate_packet_acceptance(**valid_inputs)["reasons"]
    assert "score_disagreement" in reasons
    assert "report_identity_mismatch" in reasons


def test_aware_stale_and_future_timestamps_are_rejected(valid_inputs):
    valid_inputs["report"].updated_at = valid_inputs["now"] + timedelta(days=1)
    valid_inputs["card"].final_verdict["last_scored_ts"] = "2026-09-20T00:00:00+00:00"
    reasons = evaluate_packet_acceptance(**valid_inputs)["reasons"]
    assert "report_timestamp_invalid_or_stale" in reasons
    assert "calculation_timestamp_invalid_or_stale" in reasons


def test_failed_quality_and_source_are_not_clean(valid_inputs):
    valid_inputs["source"]["source_grade"] = "FAILED"
    valid_inputs["report"].data_quality_tier = "INSUFFICIENT"
    result = evaluate_packet_acceptance(**valid_inputs)
    assert result["accepted"] is False
    assert "data_quality_insufficient" in result["reasons"]


def test_missing_one_required_qa_check_cannot_be_averaged_away(valid_inputs):
    valid_inputs["card"].final_verdict["calculation_validation"]["checks"].pop("archive_rebuildability")
    assert evaluate_packet_acceptance(**valid_inputs)["accepted"] is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 101])
def test_nonfinite_and_out_of_range_report_scores_fail_closed(valid_inputs, value):
    valid_inputs["report"].composite_score = value
    assert evaluate_packet_acceptance(**valid_inputs)["accepted"] is False


@pytest.mark.parametrize("key", ["sec", "verdict", "validation", "checks"])
def test_malformed_nested_evidence_fails_closed(valid_inputs, key):
    if key == "sec":
        valid_inputs["source"]["sec"] = ["invalid"]
    elif key == "verdict":
        valid_inputs["card"].final_verdict = ["invalid"]
    elif key == "validation":
        valid_inputs["card"].final_verdict["calculation_validation"] = ["invalid"]
    else:
        valid_inputs["card"].final_verdict["calculation_validation"]["checks"] = ["invalid"]
    assert evaluate_packet_acceptance(**valid_inputs)["accepted"] is False


@pytest.mark.parametrize("value", [None, datetime(2026, 10, 20)])
def test_missing_or_naive_filing_acceptance_is_not_assumed_utc(valid_inputs, value):
    valid_inputs["card"].accepted_at = value
    assert "filing_acceptance_unverified" in evaluate_packet_acceptance(**valid_inputs)["reasons"]
