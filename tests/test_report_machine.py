from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from accountant.config import clear_settings_cache
from accountant.db.models import RawFact
from accountant.research import report_machine as report_machine_module
from accountant.research.report_machine import (
    ContinuousResearchMachine,
    _resolved_current_price,
    _series,
    _worker_role_specs,
)


def test_worker_role_specs_cover_eight_lane_swarm() -> None:
    specs = _worker_role_specs(8)

    assert [spec["role"] for spec in specs] == [
        "sec-filings-a",
        "sec-filings-b",
        "companyfacts",
        "canonical",
        "statements",
        "reports-a",
        "reports-b",
        "strategy",
    ]
    assert [spec["primary_lane"] for spec in specs] == [
        "filings",
        "filings",
        "companyfacts",
        "canonical",
        "statements",
        "report-build",
        "report-build",
        "strategy",
    ]


def test_blank_worker_states_include_role_labels(monkeypatch) -> None:
    monkeypatch.setenv("MACHINE_WORKERS", "8")
    clear_settings_cache()

    machine = ContinuousResearchMachine()
    states = machine._blank_worker_states()

    assert len(states) == 8
    assert states[0]["role"] == "SEC FILINGS A"
    assert states[2]["role"] == "COMPANYFACTS"
    assert states[7]["role"] == "STRATEGY"
    assert all(state["status"] == "standby" for state in states)

    clear_settings_cache()


def test_series_filters_out_annual_fact_from_quarterly_growth_path() -> None:
    company_id = uuid.uuid4()
    filing_id = uuid.uuid4()
    now = datetime(2026, 8, 30, tzinfo=UTC)
    facts = [
        RawFact(
            id=uuid.uuid4(),
            filing_id=filing_id,
            company_id=company_id,
            concept="RevenueFromContractWithCustomerExcludingAssessedTax",
            taxonomy="us-gaap",
            unit="USD",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            value_numeric=Decimal("1000"),
            fact_hash="annual-2025",
            filed_date=date(2026, 2, 1),
            created_at=now,
        ),
        RawFact(
            id=uuid.uuid4(),
            filing_id=filing_id,
            company_id=company_id,
            concept="RevenueFromContractWithCustomerExcludingAssessedTax",
            taxonomy="us-gaap",
            unit="USD",
            period_start=date(2025, 4, 1),
            period_end=date(2025, 6, 30),
            value_numeric=Decimal("250"),
            fact_hash="quarter-2025q2",
            filed_date=date(2025, 8, 1),
            created_at=now,
        ),
        RawFact(
            id=uuid.uuid4(),
            filing_id=filing_id,
            company_id=company_id,
            concept="RevenueFromContractWithCustomerExcludingAssessedTax",
            taxonomy="us-gaap",
            unit="USD",
            period_start=date(2024, 4, 1),
            period_end=date(2024, 6, 30),
            value_numeric=Decimal("200"),
            fact_hash="quarter-2024q2",
            filed_date=date(2024, 8, 1),
            created_at=now,
        ),
    ]

    quarterly = _series(
        facts,
        ["RevenueFromContractWithCustomerExcludingAssessedTax"],
        period="quarterly",
    )
    annual = _series(
        facts,
        ["RevenueFromContractWithCustomerExcludingAssessedTax"],
        period="annual",
    )

    assert quarterly == [
        (date(2025, 6, 30), 250.0),
        (date(2024, 6, 30), 200.0),
    ]
    assert annual == [(date(2025, 12, 31), 1000.0)]


def test_resolved_current_price_prefers_live_quote(monkeypatch) -> None:
    monkeypatch.setattr(
        report_machine_module,
        "alpaca_quote",
        lambda ticker: {"ok": True, "quote": {"last": 123.45, "close": 122.0}},
    )

    assert _resolved_current_price("AAPL", fallback=None) == 123.45


def test_resolved_current_price_falls_back_when_quote_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        report_machine_module,
        "alpaca_quote",
        lambda ticker: {"ok": False, "reason": "credentials missing"},
    )

    assert _resolved_current_price("AAPL", fallback=99.0) == 99.0
