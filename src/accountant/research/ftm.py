"""Follow-the-money market-cap maps built from stored report-card evidence."""

from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from accountant.db.models import Company, CompanyReport, ReportCard

FTM_VERSION = "FTM_MARKET_CAP_MAP_V1"


def ftm_overview(session: Session) -> dict[str, object]:
    rows = _company_rows(session)
    sectors = _aggregate(rows, "sector")
    total_market_cap = sum(float(item["market_cap"] or 0) for item in sectors)
    for item in sectors:
        item["weight_pct"] = _round(_weight(item["market_cap"], total_market_cap))
    return {
        "version": FTM_VERSION,
        "generated_at": _now_iso(),
        "market_cap_basis": "latest stored SEC-linked market-cap snapshot",
        "total_market_cap": _round(total_market_cap),
        "covered_company_count": len(rows),
        "weighted_company_count": sum(1 for row in rows if row["market_cap"] is not None),
        "sectors": sorted(sectors, key=lambda item: item["weight_pct"], reverse=True),
        "capital_context": _capital_context(),
        "coverage_notes": _coverage_notes(rows),
    }


def ftm_sector(session: Session, sector_slug: str) -> dict[str, object] | None:
    rows = _company_rows(session)
    matching = [row for row in rows if _slug(str(row["sector"])) == sector_slug]
    if not matching:
        return None
    sector = str(matching[0]["sector"])
    total_market_cap = sum(float(row["market_cap"] or 0) for row in matching)
    subsectors = _aggregate(matching, "subsector")
    for item in subsectors:
        item["weight_pct"] = _round(_weight(item["market_cap"], total_market_cap))
    companies = []
    for row in sorted(matching, key=lambda item: float(item["market_cap"] or 0), reverse=True):
        payload = dict(row)
        payload["weight_pct"] = _round(_weight(row["market_cap"], total_market_cap))
        companies.append(payload)
    return {
        "version": FTM_VERSION,
        "generated_at": _now_iso(),
        "sector": sector,
        "sector_slug": sector_slug,
        "description": _sector_description(sector),
        "market_cap": _round(total_market_cap),
        "weight_pct": _round(_weight(total_market_cap, sum(float(row["market_cap"] or 0) for row in rows))),
        "company_count": len(matching),
        "subsectors": sorted(subsectors, key=lambda item: item["weight_pct"], reverse=True),
        "companies": companies[:250],
        "capital_context": _capital_context(),
        "coverage_notes": _coverage_notes(matching),
    }


def _company_rows(session: Session) -> list[dict[str, object]]:
    latest_cards = session.execute(
        select(ReportCard).order_by(
            ReportCard.cik.asc(),
            ReportCard.accepted_at.desc().nullslast(),
            ReportCard.filed_date.desc(),
            ReportCard.created_at.desc(),
        )
    ).scalars().all()
    cards_by_cik: dict[str, ReportCard] = {}
    for card in latest_cards:
        cards_by_cik.setdefault(card.cik, card)
    companies = session.execute(
        select(Company, CompanyReport).join(CompanyReport, CompanyReport.company_id == Company.id)
    ).all()
    rows: list[dict[str, object]] = []
    for company, report in companies:
        card = cards_by_cik.get(company.cik)
        if card is None:
            continue
        market = dict(card.market_data_linkage or {})
        verdict = dict(card.final_verdict or {})
        stats = dict(report.key_stats or {})
        sector = str(card.gics_sector or stats.get("gics_sector") or _infer_sector(company.sic_description))
        subsector = str(card.gics_industry or stats.get("gics_industry") or company.sic_description or "Unclassified")
        rows.append(
            {
                "ticker": report.ticker,
                "company_name": report.company_name,
                "sector": sector,
                "subsector": subsector,
                "market_cap": _number(market.get("market_cap")),
                "score": _number(verdict.get("grade_score")) or _number(report.composite_score),
                "action": verdict.get("current_action") or report.stance,
                "grade": verdict.get("grade"),
                "data_quality": report.data_quality_tier,
                "government_money": {"value": None, "status": "not_ingested", "source": "SEC filing ledger pending DEF 14A/SBA/award mapping"},
                "ceo_money": {"value": None, "status": "not_ingested", "source": "SEC executive-compensation extraction pending DEF 14A"},
            }
        )
    return rows


def _aggregate(rows: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    result = []
    for name, items in grouped.items():
        market_cap = sum(float(item["market_cap"] or 0) for item in items)
        result.append(
            {
                "name": name,
                "slug": _slug(name),
                "market_cap": _round(market_cap),
                "company_count": len(items),
                "weighted_company_count": sum(1 for item in items if item["market_cap"] is not None),
                "avg_score": _round(_mean(item["score"] for item in items)),
                "capital_context": _capital_context(),
            }
        )
    return result


def _capital_context() -> dict[str, object]:
    return {
        "government_money": {"value": None, "status": "not_ingested", "source": "Requires agency-award, procurement, grant, and subsidy datasets."},
        "executive_money": {"value": None, "status": "not_ingested", "source": "Requires DEF 14A compensation and Form 4 ownership normalization."},
        "market_cap_weighting": {"status": "active", "source": "latest stored report-card market_cap"},
    }


def _coverage_notes(rows: list[dict[str, object]]) -> list[str]:
    missing_market_cap = sum(1 for row in rows if row["market_cap"] is None)
    return [
        f"{missing_market_cap} of {len(rows)} covered companies have no stored market-cap snapshot and are excluded from weight denominators.",
        "Government and executive-money fields are explicitly unavailable until their source feeds are ingested.",
        "Sector and subsector labels are based on stored GICS fields when present, otherwise deterministic SIC fallback labels.",
    ]


def _sector_description(sector: str) -> str:
    descriptions = {
        "Technology": "Software, computing, semiconductors, data infrastructure, and digital systems.",
        "Energy": "Oil, gas, power, utilities, grid, fuels, and energy infrastructure.",
        "Healthcare": "Biotech, pharmaceuticals, medical devices, diagnostics, and healthcare services.",
        "Financials": "Banks, insurers, asset managers, brokers, exchanges, and payment platforms.",
        "Industrials": "Machinery, defense, aerospace, transportation, construction, and industrial services.",
        "Consumer": "Retail, food, apparel, restaurants, travel, and consumer products.",
        "Materials": "Mining, chemicals, metals, packaging, and construction inputs.",
        "Real Estate": "Property owners, REITs, data centers, logistics, housing, and infrastructure assets.",
        "Utilities": "Regulated power, gas, water, grid, renewable, and baseload infrastructure.",
        "Communication Services": "Telecom, media, advertising, platforms, streaming, and entertainment.",
    }
    return descriptions.get(sector, "Companies not yet assigned to a dedicated sector profile.")


def _infer_sector(description: str | None) -> str:
    text = (description or "").lower()
    mapping = {
        "Technology": ("software", "computer", "semiconductor", "data processing", "electronic"),
        "Energy": ("oil", "gas", "petroleum", "energy", "pipeline", "drilling"),
        "Materials": ("mining", "metal", "chemical", "steel", "paper"),
        "Industrials": ("machinery", "transportation", "aerospace", "defense", "construction", "industrial"),
        "Consumer": ("retail", "restaurant", "apparel", "food", "beverage", "hotel"),
        "Healthcare": ("medical", "pharmaceutical", "biotech", "health", "diagnostic"),
        "Financials": ("bank", "insurance", "finance", "broker", "asset management"),
        "Real Estate": ("real estate", "reit", "property", "realty"),
        "Utilities": ("utility", "electric", "water"),
        "Communication Services": ("media", "telecommunications", "broadcast", "entertainment"),
    }
    for sector, terms in mapping.items():
        if any(term in text for term in terms):
            return sector
    return "General"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _number(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _mean(values) -> float | None:
    numbers = [value for value in (_number(item) for item in values) if value is not None]
    return sum(numbers) / len(numbers) if numbers else None


def _weight(value: object, total: float) -> float:
    number = _number(value) or 0.0
    return number / total * 100 if total > 0 else 0.0


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
