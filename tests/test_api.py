from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

import accountant.api.app as api_app
from accountant.api.app import app, get_session
from accountant.db.models import Company, Filing, FilingDocument, RawFact, ReportCard, Security
from accountant.ingest.companies import BulkCompanyImportResult


def _session_override(test_session):
    def _override():
        yield test_session

    return _override


def _seed_company_with_filings_and_facts(test_session) -> Company:
    company = Company(
        id=uuid.uuid4(),
        cik="0000320193",
        name="Apple Inc.",
        entity_type="operating",
        sic="3571",
        sic_description="Electronic Computers",
        fiscal_year_end="0927",
        state_of_incorporation="CA",
    )
    security = Security(company_id=company.id, ticker="AAPL", exchange="NASDAQ")
    filing_old = Filing(
        id=uuid.uuid4(),
        company_id=company.id,
        accession_number="0000320193-24-000001",
        form_type="10-K",
        filing_date=date(2024, 11, 1),
        report_date=date(2024, 9, 28),
        accepted_at=datetime(2024, 11, 1, 16, 30, 0),
        primary_document="aapl-20240928.htm",
        source_url="https://www.sec.gov/Archives/aapl-2024",
    )
    filing_new = Filing(
        id=uuid.uuid4(),
        company_id=company.id,
        accession_number="0000320193-25-000001",
        form_type="10-K",
        filing_date=date(2025, 11, 1),
        report_date=date(2025, 9, 27),
        accepted_at=datetime(2025, 11, 1, 16, 30, 0),
        primary_document="aapl-20250927.htm",
        source_url="https://www.sec.gov/Archives/aapl-2025",
        is_xbrl=True,
        is_inline_xbrl=True,
    )
    document = FilingDocument(
        id=uuid.uuid4(),
        filing_id=filing_new.id,
        sequence=1,
        document_name="aapl-20250927x10k.htm",
        document_type="10-K",
        description="Annual report",
        size_bytes=123456,
        url="https://www.sec.gov/Archives/aapl-2025-doc",
    )
    fact_old = RawFact(
        id=uuid.uuid4(),
        filing_id=filing_old.id,
        company_id=company.id,
        concept="Assets",
        taxonomy="us-gaap",
        unit="USD",
        period_end=date(2024, 9, 28),
        value_numeric=Decimal("100.00"),
        fact_hash="hash-old",
        accession_number=filing_old.accession_number,
        form="10-K",
        filed_date=date(2024, 11, 1),
        fiscal_year=2024,
        fiscal_period="FY",
        source_type="companyfacts",
    )
    fact_new = RawFact(
        id=uuid.uuid4(),
        filing_id=filing_new.id,
        company_id=company.id,
        concept="Assets",
        taxonomy="us-gaap",
        unit="USD",
        period_end=date(2025, 9, 27),
        value_numeric=Decimal("120.00"),
        fact_hash="hash-new",
        accession_number=filing_new.accession_number,
        form="10-K",
        filed_date=date(2025, 11, 1),
        fiscal_year=2025,
        fiscal_period="FY",
        source_type="companyfacts",
    )
    fact_other = RawFact(
        id=uuid.uuid4(),
        filing_id=filing_new.id,
        company_id=company.id,
        concept="Liabilities",
        taxonomy="us-gaap",
        unit="USD",
        period_end=date(2025, 9, 27),
        value_numeric=Decimal("70.00"),
        fact_hash="hash-other",
        accession_number=filing_new.accession_number,
        form="10-K",
        filed_date=date(2025, 11, 1),
        fiscal_year=2025,
        fiscal_period="FY",
        source_type="companyfacts",
    )
    test_session.add_all([
        company,
        security,
        filing_old,
        filing_new,
        document,
        fact_old,
        fact_new,
        fact_other,
    ])
    test_session.commit()
    return company


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_company_by_ticker(test_session) -> None:
    company = _seed_company_with_filings_and_facts(test_session)

    app.dependency_overrides[get_session] = _session_override(test_session)
    client = TestClient(app)

    response = client.get("/companies/aapl")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": str(company.id),
        "cik": "0000320193",
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "entity_type": "operating",
        "sic": "3571",
        "sic_description": "Electronic Computers",
        "fiscal_year_end": "0927",
        "state_of_incorporation": "CA",
        "filings_count": 2,
        "raw_facts_count": 3,
        "canonical_facts_count": 0,
        "statement_snapshots_count": 0,
        "research_records_count": 0,
        "latest_filing_date": "2025-11-01",
    }


def test_get_company_facts_filters_and_orders_results(test_session) -> None:
    _seed_company_with_filings_and_facts(test_session)

    app.dependency_overrides[get_session] = _session_override(test_session)
    client = TestClient(app)

    response = client.get("/companies/AAPL/facts", params={"concept": "Assets", "limit": 10})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert [item["accession_number"] for item in payload] == [
        "0000320193-25-000001",
        "0000320193-24-000001",
    ]
    assert all(item["concept"] == "Assets" for item in payload)
    assert payload[0]["value_numeric"] == "120.0000000000"
    assert payload[1]["value_numeric"] == "100.0000000000"


def test_dashboard_returns_aggregate_counts(test_session) -> None:
    _seed_company_with_filings_and_facts(test_session)

    app.dependency_overrides[get_session] = _session_override(test_session)
    client = TestClient(app)

    response = client.get("/api/dashboard")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"] == {
        "total_companies": 1,
        "total_filings": 2,
        "total_raw_facts": 3,
        "total_canonical_facts": 0,
        "total_statement_snapshots": 0,
        "total_research_records": 0,
        "companies_with_raw_facts": 1,
        "companies_with_canonical_facts": 0,
        "companies_with_statement_snapshots": 0,
        "companies_with_research_records": 0,
        "companies_with_reports": 0,
    }
    assert payload["coverage"][0]["ticker"] == "AAPL"
    assert payload["coverage"][0]["coverage_status"] == "facts-ingested"
    assert payload["recent_filings"][0]["accession_number"] == "0000320193-25-000001"
    assert payload["ticker_tape"]


def test_list_companies_filters_by_query(test_session) -> None:
    _seed_company_with_filings_and_facts(test_session)

    app.dependency_overrides[get_session] = _session_override(test_session)
    client = TestClient(app)

    response = client.get("/api/companies", params={"q": "Apple"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["ticker"] == "AAPL"
    assert payload[0]["filings_count"] == 2
    assert payload[0]["raw_facts_count"] == 3


def test_company_filings_include_documents(test_session) -> None:
    _seed_company_with_filings_and_facts(test_session)

    app.dependency_overrides[get_session] = _session_override(test_session)
    client = TestClient(app)

    response = client.get("/api/companies/AAPL/filings")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["accession_number"] == "0000320193-25-000001"
    assert payload[0]["documents"][0]["document_name"] == "aapl-20250927x10k.htm"
    assert payload[0]["accepted_at"] == "2025-11-01T16:30:00"


def test_import_coverage_universe_endpoint(test_session, monkeypatch) -> None:
    class DummySecClient:
        def close(self) -> None:
            return None

    def fake_import_companies_from_tickers(session, tickers, sec_client):
        assert tickers == ["AAPL", "MSFT", "GOOGL"]
        return BulkCompanyImportResult(
            requested=3,
            imported=2,
            existing=1,
            unresolved=[],
            invalid=[],
            imported_tickers=["AAPL", "MSFT", "GOOGL"],
            mode="sec_registry",
        )

    monkeypatch.setattr(api_app, "SecClient", DummySecClient)
    monkeypatch.setattr(api_app, "import_companies_from_tickers", fake_import_companies_from_tickers)

    app.dependency_overrides[get_session] = _session_override(test_session)
    client = TestClient(app)

    response = client.post(
        "/api/coverage/import",
        json={
            "universe_name": "mega cap test",
            "ticker_blob": "AAPL, MSFT\nGOOGL",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "mega cap test completed",
        "mode": "sec_registry",
        "requested": 3,
        "imported": 2,
        "existing": 1,
        "unresolved": [],
        "invalid": [],
        "imported_tickers": ["AAPL", "MSFT", "GOOGL"],
    }


def test_get_company_returns_404_for_unknown_ticker(test_session) -> None:
    app.dependency_overrides[get_session] = _session_override(test_session)
    client = TestClient(app)

    response = client.get("/companies/MSFT")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Company not found for ticker MSFT"}


def test_market_quote_endpoint_returns_research_only_failure_shape(monkeypatch) -> None:
    def fake_ibkr_quote(ticker: str):
        assert ticker == "AAPL"
        return {
            "ok": False,
            "symbol": "AAPL",
            "checked_at": "2026-08-13T03:49:30.387657+00:00",
            "reason": "IBKR connection timed out before nextValidId",
            "config": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 7496,
                "client_id": 1,
                "read_only": True,
                "mode": "research_only",
                "order_mutation_policy": "blocked_before_gateway",
            },
            "errors": [
                {
                    "req_id": -1,
                    "code": 502,
                    "message": "Couldn't connect to TWS.",
                    "details": "",
                }
            ],
        }

    monkeypatch.setattr(api_app, "ibkr_quote", fake_ibkr_quote)
    client = TestClient(app)

    response = client.get("/api/companies/AAPL/market-quote")

    assert response.status_code == 200
    assert response.json()["symbol"] == "AAPL"
    assert response.json()["ok"] is False
    assert response.json()["reason"] == "IBKR connection timed out before nextValidId"


def test_get_latest_report_card_exposes_lineage_and_identity_metadata(test_session) -> None:
    company = _seed_company_with_filings_and_facts(test_session)
    report_card = ReportCard(
        id=uuid.uuid4(),
        company_id=company.id,
        report_card_id="0000320193_10-K_2025-09-27_2025-11-01",
        cik="0000320193",
        ticker="AAPL",
        company_name="Apple Inc.",
        sic_code="3571",
        gics_sector="Technology",
        gics_industry="Electronic Computers",
        exchange="NASDAQ",
        filing_type="10-K",
        period_of_report=date(2025, 9, 27),
        filed_date=date(2025, 11, 1),
        accepted_at=datetime(2025, 11, 1, 16, 30, 0),
        accession_number="0000320193-25-000001",
        source_url="https://www.sec.gov/Archives/aapl-2025",
        raw_filing_sha256="abc",
        is_restatement=False,
        standardized_financials={"revenue": 100.0},
        growth_trend_deltas={"revenue_yoy_growth": 12.5},
        accrual_cash_quality={"cash_conversion_ratio": 1.1},
        forensic_scores={"beneish_m_score": -2.4},
        positive_quality={"positive_quality_score": 82.7},
        event_red_flags={"going_concern_flag": False},
        textual_signals={},
        non_gaap_forensics={"gaap_eps": 5.0},
        governance_ownership={},
        market_data_linkage={"market_cap": 123456789.0},
        universe_tradability={"excluded_recent_ipo": False},
        final_verdict={
            "grade": "B",
            "next_expected_filing_date": "2026-11-01",
            "score_lineage": {
                "canonical_score_name": "positive_quality_score",
                "canonical_score_value": 82.7,
            },
        },
    )
    test_session.add(report_card)
    test_session.commit()

    app.dependency_overrides[get_session] = _session_override(test_session)
    client = TestClient(app)

    response = client.get("/api/report-cards/AAPL")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["gics_sector"] == "Technology"
    assert payload["gics_industry"] == "Electronic Computers"
    assert payload["exchange"] == "NASDAQ"
    assert payload["market_data_linkage"]["market_cap"] == 123456789.0
    assert payload["final_verdict"]["next_expected_filing_date"] == "2026-11-01"
    assert payload["final_verdict"]["score_lineage"]["canonical_score_name"] == "positive_quality_score"
