from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from accountant.db.models import Company, CompanyReport, Filing, RawFact, ReportCard
from accountant.research import report_machine as machine
from accountant.research.buy_board import (
    _estimate_share_count,
    _qualifies_for_buy_board,
    _validated_report,
)
from accountant.research.factor_engine import (
    FactorPeriod,
    _annual_periods,
    _external_financing_ratio,
)
from accountant.research.financial_input_safety import (
    RULE_VERSION,
    annual_report_inputs,
    expected_unit,
    provenance,
)


def fact(concept="Revenues", value=100, start=date(2025, 1, 1), end=date(2025, 12, 31), **kwargs):
    fields = dict(
        id=uuid.uuid4(), company_id=uuid.uuid4(), filing_id=uuid.uuid4(),
        concept=concept, taxonomy="us-gaap", unit=expected_unit(concept),
        value_numeric=Decimal(str(value)), period_start=start, period_end=end,
        fact_hash=uuid.uuid4().hex, fiscal_year=end.year, fiscal_period="FY",
        filed_date=date(2026, 2, 1), accession_number="0000000001-26-000001",
    )
    fields.update(kwargs)
    return RawFact(**fields)


@pytest.mark.parametrize("overrides", [
    {"unit": "EUR"}, {"unit": None}, {"taxonomy": "custom"},
    {"dimensions": {"GeographyAxis": "EuropeMember"}}, {"value_numeric": Decimal("NaN")},
])
def test_series_rejects_incompatible_context_even_if_newer(overrides):
    good = fact(value=0)
    bad = fact(value=900, filed_date=date(2026, 3, 1), **overrides)
    assert machine._series([bad, good], ["Revenues"], period="annual") == [(date(2025, 12, 31), 0)]


def test_series_has_deterministic_alias_priority_and_revision_provenance():
    old = fact(value=100)
    revised = fact(value=110, filed_date=date(2026, 3, 1))
    alias = fact(concept="SalesRevenueNet", value=999, filed_date=date(2026, 4, 1))
    for rows in ([old, alias, revised], [revised, alias, old]):
        result = machine._series(rows, ["Revenues", "SalesRevenueNet"], period="annual")
        assert result[0][1] == 110
        source = provenance(result.source_facts[0])
        assert source["fact_hash"] == revised.fact_hash
        assert source["rule_version"] == RULE_VERSION
        assert source["value"] == "110"


def test_conflicting_values_or_durations_are_unavailable_not_row_order_dependent():
    a = fact(value=100)
    for b in (fact(value=200), fact(start=date(2024, 12, 20))):
        assert machine._series([a, b], ["Revenues"], period="annual") == []
        assert machine._series([b, a], ["Revenues"], period="annual") == []


def test_july_june_ttm_is_not_compared_with_calendar_year():
    series = machine._series([
        fact(value=150, start=date(2025, 7, 1), end=date(2026, 6, 30)),
        fact(value=100, start=date(2025, 1, 1), end=date(2025, 12, 31)),
    ], ["Revenues"], period="annual")
    assert machine._comparable_prior_value(series) is None


def test_valid_year_over_year_retains_zero_prior_without_fallback():
    series = machine._series([
        fact(value=100), fact(value=0, start=date(2024, 1, 1), end=date(2024, 12, 31)),
    ], ["Revenues"], period="annual")
    assert machine._comparable_prior_value(series) == 0
    assert machine._pct_change(series[0][1], machine._comparable_prior_value(series)) is None


def test_quarterly_cfo_does_not_mix_with_annual_capex():
    revenue, inputs = annual_report_inputs([
        fact(), fact("NetCashProvidedByUsedInOperatingActivities", 50, start=date(2025, 10, 1)),
        fact("PaymentsToAcquirePropertyPlantAndEquipment", 100),
    ])
    assert revenue
    assert machine._latest_fact_from_concepts(inputs, ["NetCashProvidedByUsedInOperatingActivities"], "annual") is None
    assert machine._latest_fact_from_concepts(inputs, ["PaymentsToAcquirePropertyPlantAndEquipment"], "annual") == 100


@pytest.mark.parametrize("shares", [None, 0, -1])
def test_missing_shares_never_become_divisor_one(shares):
    result = machine._scenario_valuations(earnings_power=1000, quality_score=90, growth_pct=10, share_count=shares)
    assert result == {"bear": None, "base": None, "bull": None}


def test_instant_and_weighted_average_shares_are_not_interchangeable():
    facts = [fact("CommonStockSharesOutstanding", 20, start=None),
             fact("WeightedAverageNumberOfDilutedSharesOutstanding", 10)]
    assert machine._latest_fact_from_concepts(facts, ["WeightedAverageNumberOfDilutedSharesOutstanding"], "instant") is None
    assert machine._latest_fact_from_concepts(facts, ["CommonStockSharesOutstanding"], "annual") is None
    report = CompanyReport(key_stats={"weighted_avg_diluted_shares": 10})
    class NoInstantFactSession:
        def get_bind(self):
            raise AssertionError("database fallback must be explicitly stubbed")
    # An existing instant-share input wins, never a weighted-average substitute.
    report.key_stats["shares_outstanding"] = 20
    assert _estimate_share_count(NoInstantFactSession(), report) == 20


def test_external_financing_does_not_add_dollars_to_share_counts():
    current = FactorPeriod(2025, "FY", date(2025, 12, 31), {"Assets": 1000, "CommonStockSharesOutstanding": 10})
    prior = FactorPeriod(2024, "FY", date(2024, 12, 31), {"Assets": 1000, "CommonStockSharesOutstanding": 5})
    assert _external_financing_ratio(current, prior) is None


def test_fy_metadata_does_not_turn_missing_duration_into_annual_flow():
    assert _annual_periods([fact(start=None)]) == []
    assert _annual_periods([fact(start=date(2025, 10, 1))]) == []


def test_factor_inputs_reject_segment_and_preserve_revision_identity():
    original = fact()
    revision = fact(value=120, filed_date=date(2026, 3, 1))
    segment = fact(value=999, dimensions={"Segment": "A"})
    period = _annual_periods([segment, original, revision])[0]
    assert period.facts["Revenues"] == 120
    assert period.source_facts["Revenues"].fact_hash == revision.fact_hash


def test_archived_raw_zero_is_incomplete_even_with_canonical_facts():
    assert machine._pipeline_stage(0, 100) == "archive-dependent-incomplete"


@pytest.mark.parametrize("status,raw,score", [("UNVALIDATED", 10, 90), ("VALIDATED", 0, 90), ("VALIDATED", 10, 50)])
def test_actionable_outputs_require_canonical_grade_score_and_raw_inputs(status, raw, score):
    report = CompanyReport(stance="MOST_BULLISH", composite_score=90, data_quality_tier="ADEQUATE", key_stats={
        "validation_status": status, "raw_facts_count": raw,
        "financial_input_rule_version": RULE_VERSION,
        "canonical_grade": "A", "canonical_score": score,
        "canonical_facts_count": 100, "accounting_quality_score": 90,
        "owner_earnings": 100, "revenue_growth_pct": 10,
    })
    assert not _validated_report(report)
    assert not _qualifies_for_buy_board(report)


def test_report_build_unknown_events_and_immutable_card(test_session, monkeypatch):
    # Every external boundary is disabled; filings have no source URLs.
    monkeypatch.setattr(machine, "_resolved_current_price", lambda *a, **k: None)
    monkeypatch.setattr(machine, "sync_buy_board_candidate", lambda *a, **k: None)
    monkeypatch.setattr(machine, "upsert_company_bottleneck_snapshot", lambda *a, **k: None)
    company = Company(cik="0000000001", name="Safety Fixture")
    test_session.add(company)
    test_session.flush()
    filing = Filing(company_id=company.id, accession_number="0000000001-26-000001",
                    form_type="10-K/A", filing_date=date(2026, 2, 1), is_amendment=True)
    test_session.add(filing)
    test_session.flush()
    for row in [fact(value=0), fact("NetIncomeLoss", value=0),
                fact("NetCashProvidedByUsedInOperatingActivities", 50, start=date(2025, 10, 1)),
                fact("PaymentsToAcquirePropertyPlantAndEquipment", 100),
                fact("CommonStockSharesOutstanding", 20, start=None)]:
        row.company_id, row.filing_id = company.id, filing.id
        test_session.add(row)
    test_session.flush()
    machine.ContinuousResearchMachine()._build_report(test_session, company, "SAFE")
    report = test_session.execute(select(CompanyReport)).scalar_one()
    card = test_session.execute(select(ReportCard)).scalar_one()
    assert report.key_stats["revenue"] == 0
    assert report.key_stats["owner_earnings"] is None
    assert report.key_stats["eps"] is None
    assert card.event_red_flags["restatement_severity"] == "unknown"
    assert card.event_red_flags["going_concern_flag"] is None
    assert card.final_verdict["grade"] == "UNVALIDATED"
    assert card.final_verdict["position_size"] == 0
    assert card.final_verdict["composite_score"] == report.composite_score
    assert card.final_verdict["score_lineage"]["red_flag_penalty_source"]["event_flag_severity"] is None
    original = dict(card.final_verdict)
    machine.ContinuousResearchMachine()._build_report(test_session, company, "SAFE")
    test_session.refresh(card)
    assert card.final_verdict == original


def test_storage_paused_restart_reports_persisted_counts(test_session, test_engine, monkeypatch):
    company = Company(cik="0000000001", name="Stored")
    test_session.add(company)
    test_session.flush()
    test_session.add(CompanyReport(
        company_id=company.id, ticker="SAFE", company_name="Stored",
        as_of_date="2026-10-22", stance="NEUTRAL", pipeline_stage="unvalidated",
    ))
    test_session.commit()
    worker = machine.ContinuousResearchMachine()
    monkeypatch.setattr(machine, "create_db_engine", lambda: test_engine)
    monkeypatch.setattr(test_engine, "dispose", lambda: None)
    monkeypatch.setattr(worker, "_storage_preflight", lambda _: SimpleNamespace(
        allowed=False, reason="database_cap_reached",
    ))
    monkeypatch.setattr(worker, "_sync_universes_if_needed", lambda _: pytest.fail("write path must not run"))
    assert worker._run_cycle() is False
    snapshot = worker.snapshot()
    assert snapshot["reports_cached"] == 1
    assert snapshot["total_companies"] == 1
    assert snapshot["storage_blocked"] is True
