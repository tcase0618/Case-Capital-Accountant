from __future__ import annotations

from accountant.db.models import Company, CompanyReport
from accountant.research.bottleneck_engine import (
    build_bottleneck_payload,
    extract_management_bottlenecks,
)


def test_extract_management_bottlenecks_tags_ai_and_energy_language() -> None:
    text = (
        "Management expects AI demand to remain supply constrained because GPU and data center capacity "
        "remain limited. Energy costs and electricity costs may pressure margins during expansion."
    )

    results = extract_management_bottlenecks(text)
    categories = {item["category"] for item in results}

    assert "AI compute capacity / GPU supply" in categories
    assert "Energy input cost / power availability" in categories


def test_build_bottleneck_payload_uses_model_family_and_metric_blockers() -> None:
    company = Company(
        cik="0000000001",
        name="Example AI Inc.",
        sic="7372",
        sic_description="Prepackaged Software",
    )
    report = CompanyReport(
        company_id=company.id,
        ticker="AIEX",
        company_name="Example AI Inc.",
        as_of_date="2026-09-16",
        stance="WATCH",
        composite_score=42.0,
        data_quality_tier="PARTIAL",
        latest_filing_date="2026-09-01",
        key_stats={
            "revenue": 100.0,
            "revenue_growth_pct": -6.0,
            "net_income": -25.0,
            "owner_earnings": -30.0,
            "owner_earnings_margin_pct": -30.0,
            "overall_coverage_pct": 40.0,
            "factor_warning_count": 3,
        },
        report_markdown="AI demand remains strong but customer demand and supply chain constraints continue.",
    )

    payload = build_bottleneck_payload(company=company, report=report)

    assert payload.focus_family == "AI / compute"
    assert payload.model_family == "ai_compute"
    assert payload.bottlenecks[0]["category"] == "Insufficient earnings-data coverage"
    assert any(item["category"] == "AI compute capacity / GPU supply" for item in payload.management_bottlenecks)
