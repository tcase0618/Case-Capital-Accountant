from __future__ import annotations

import uuid
from datetime import date, datetime

from accountant.db.models import Company, PaperBookPosition, ReportCard, Security
from accountant.research.company_router import route_company
from accountant.research.paper_book import launch_lane1_paper_book


def test_company_router_assigns_general_when_no_strategy_lane_fits() -> None:
    financial = route_company(
        gics_sector="Financials",
        sic_description="State commercial bank",
        revenue=100.0,
        owner_earnings=10.0,
        net_income=9.0,
    )
    prerevenue = route_company(
        gics_sector="Healthcare",
        sic_description="Biological products",
        revenue=0.0,
        owner_earnings=-5.0,
        net_income=-7.0,
    )
    operating = route_company(
        gics_sector="Technology",
        sic_description="Electronic Computers",
        revenue=1000.0,
        owner_earnings=150.0,
        net_income=120.0,
    )
    general = route_company(
        gics_sector=None,
        sic_description=None,
        revenue=100.0,
        owner_earnings=15.0,
        net_income=10.0,
    )

    assert financial.family == "financials"
    assert financial.lane1_supported is False
    assert prerevenue.family == "pre_revenue"
    assert prerevenue.lane1_supported is False
    assert general.family == "general"
    assert general.lane1_supported is False
    assert operating.family == "ai_compute"
    assert operating.lane1_supported is True


def test_launch_lane1_paper_book_freezes_latest_operating_company_snapshot(test_session) -> None:
    company = Company(
        id=uuid.uuid4(),
        cik="0000320193",
        name="Apple Inc.",
        sic="3571",
        sic_description="Electronic Computers",
        entity_type="operating",
    )
    security = Security(company_id=company.id, ticker="AAPL", exchange="NASDAQ")
    test_session.add_all([company, security])
    test_session.flush()

    report_card = ReportCard(
        id=uuid.uuid4(),
        company_id=company.id,
        report_card_id="0000320193_10-K_2025-09-27_2025-11-01",
        cik="0000320193",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        period_of_report=date(2025, 9, 27),
        filed_date=date(2025, 11, 1),
        accepted_at=datetime.fromisoformat("2025-11-01T16:30:00"),
        accession_number="0000320193-25-000001",
        standardized_financials={"revenue": 100.0},
        growth_trend_deltas={},
        accrual_cash_quality={},
        forensic_scores={},
        positive_quality={"positive_quality_score": 92.4},
        event_red_flags={},
        textual_signals={},
        non_gaap_forensics={},
        governance_ownership={},
        market_data_linkage={"price_asof": 210.5, "market_cap": 5000000000},
        universe_tradability={
            "passes_liquidity_filter": True,
            "excluded_financial_reit": False,
            "excluded_biotech_prerevenue": False,
            "excluded_recent_ipo": False,
        },
        final_verdict={
            "route_family": "operating_company",
            "route_reason": "operating issuer supports Lane 1 forensic quality model",
            "lane1_supported": True,
            "current_action": "BUY",
            "veto_triggered": False,
            "grade_score": 92.4,
            "grade": "A",
            "confidence": 0.88,
            "data_completeness_pct": 84.1,
        },
    )
    test_session.add(report_card)
    test_session.commit()

    result = launch_lane1_paper_book(test_session, launch_date=date(2026, 8, 31), size=20)
    test_session.commit()

    assert result.selected == 1
    position = test_session.query(PaperBookPosition).one()
    assert position.book_name == "lane1-paper-book-2026-08-31"
    assert position.entry_price == 210.5
    assert position.target_weight == 1.0
    assert position.thesis_snapshot["report_card_id"] == report_card.report_card_id


def test_lane1_paper_book_tracks_research_candidate_before_execution_readiness(test_session) -> None:
    company = Company(
        id=uuid.uuid4(),
        cik="0000789019",
        name="Microsoft Corporation",
        sic="7372",
        sic_description="Services-Prepackaged Software",
        entity_type="operating",
    )
    security = Security(company_id=company.id, ticker="MSFT", exchange="NASDAQ")
    test_session.add_all([company, security])
    test_session.flush()

    report_card = ReportCard(
        id=uuid.uuid4(),
        company_id=company.id,
        report_card_id="0000789019_10-Q_2026-03-31_2026-04-24",
        cik="0000789019",
        ticker="MSFT",
        company_name="Microsoft Corporation",
        filing_type="10-Q",
        period_of_report=date(2026, 3, 31),
        filed_date=date(2026, 4, 24),
        accepted_at=datetime.fromisoformat("2026-04-24T16:02:00"),
        accession_number="0000789019-26-000001",
        standardized_financials={"revenue": 100.0},
        growth_trend_deltas={},
        accrual_cash_quality={},
        forensic_scores={},
        positive_quality={"positive_quality_score": 81.0},
        event_red_flags={"going_concern_flag": False, "restatement_severity": "none"},
        textual_signals={},
        non_gaap_forensics={},
        governance_ownership={},
        market_data_linkage={"price_asof": None, "market_cap": None},
        universe_tradability={
            "passes_liquidity_filter": None,
            "excluded_financial_reit": False,
            "excluded_biotech_prerevenue": False,
            "excluded_recent_ipo": False,
        },
        final_verdict={
            "route_family": "ai_compute",
            "route_reason": "AI/compute issuer supports Lane 1 forensic quality model",
            "lane1_supported": True,
            "current_action": "WATCH",
            "veto_triggered": True,
            "veto_reason": "classification rejected by rules",
            "grade_score": 81.0,
            "grade": "B",
            "confidence": 0.62,
            "data_completeness_pct": 61.0,
        },
    )
    test_session.add(report_card)
    test_session.commit()

    result = launch_lane1_paper_book(test_session, launch_date=date(2026, 9, 17), size=20)
    test_session.commit()

    assert result.selected == 1
    position = test_session.query(PaperBookPosition).one()
    assert position.entry_price is None
    assert position.lane == "RESEARCH_WATCH"
    assert position.thesis_snapshot["current_action"] == "WATCH"
    assert position.thesis_snapshot["research_score"] == 81.0
    assert "research evidence only" in position.thesis_snapshot["selection_policy"]
