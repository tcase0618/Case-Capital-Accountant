from __future__ import annotations

import re
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from accountant.db.models import Company, CompanyBottleneckSnapshot, CompanyReport


SECTOR_INTELLIGENCE_VERSION = "SECTOR_INTELLIGENCE_V1"

STRATEGIC_BOTTLENECKS: tuple[dict[str, Any], ...] = (
    {
        "category": "AI data-center power and grid capacity",
        "thesis": "AI compute demand is increasingly constrained by available power, grid interconnects, cooling, and data-center capacity.",
        "affected_terms": ("ai", "compute", "semiconductor", "software", "data processing", "electronic computers", "communications"),
        "enabler_terms": ("electric", "power", "utility", "natural gas", "pipeline", "nuclear", "uranium", "energy", "data center", "cooling"),
        "preferred_focus": ("Energy / resources",),
        "sector_bias": ("Technology", "Communication Services", "Utilities", "Energy"),
    },
    {
        "category": "Semiconductor, advanced packaging, and compute hardware supply",
        "thesis": "Compute growth depends on chip supply, memory bandwidth, networking, packaging, substrates, test equipment, and server integration.",
        "affected_terms": ("ai", "compute", "data center", "cloud", "software", "communications"),
        "enabler_terms": ("semiconductor", "chip", "memory", "electronic", "computer storage", "computer peripheral", "communications equipment", "printed circuit", "server"),
        "preferred_focus": ("AI / compute",),
        "sector_bias": ("Technology", "Industrials"),
    },
    {
        "category": "Critical minerals, copper, uranium, and industrial input supply",
        "thesis": "Electrification, AI infrastructure, defense, and energy expansion need copper, uranium, steel, specialty chemicals, and other constrained inputs.",
        "affected_terms": ("energy", "power", "electric", "industrial", "construction", "semiconductor", "battery", "renewable"),
        "enabler_terms": ("mining", "metal", "copper", "uranium", "lithium", "chemical", "steel", "aluminum", "materials", "coal", "gold", "silver"),
        "preferred_focus": ("Energy / resources",),
        "sector_bias": ("Materials", "Energy", "Industrials", "Utilities"),
    },
    {
        "category": "Industrial buildout, electrical equipment, and automation capacity",
        "thesis": "Factories, grid upgrades, data centers, and energy projects need equipment suppliers, automation, construction capacity, and specialized labor.",
        "affected_terms": ("construction", "industrial", "manufacturing", "data center", "electric", "power", "defense", "aerospace"),
        "enabler_terms": ("machinery", "electrical", "construction", "engineering", "automation", "aerospace", "defense", "industrial", "equipment"),
        "preferred_focus": (),
        "sector_bias": ("Industrials", "Utilities", "Technology", "Energy"),
    },
    {
        "category": "Logistics, freight, inventory, and working-capital throughput",
        "thesis": "Supply chains improve when transportation, warehousing, inventory visibility, and receivables/cash-conversion pressure improve.",
        "affected_terms": ("retail", "consumer", "manufacturing", "inventory", "freight", "logistics", "restaurant", "apparel"),
        "enabler_terms": ("transportation", "rail", "trucking", "shipping", "logistics", "warehouse", "supply chain", "freight", "data processing"),
        "preferred_focus": (),
        "sector_bias": ("Industrials", "Consumer", "Technology"),
    },
    {
        "category": "Capital availability, refinancing, and balance-sheet repair",
        "thesis": "Companies with debt maturities, high rates, or weak cash generation need access to lenders, capital markets, asset sales, or self-funded cash flow.",
        "affected_terms": ("debt", "refinance", "interest", "credit", "covenant", "cash burn", "negative owner earnings"),
        "enabler_terms": ("bank", "finance", "asset management", "insurance", "broker", "exchange", "financial"),
        "preferred_focus": (),
        "sector_bias": ("Financials", "Real Estate", "Energy", "Healthcare"),
    },
)

SUB_SECTOR_DEFINITIONS: dict[str, tuple[dict[str, Any], ...]] = {
    "Energy": (
        {"name": "Power for AI", "thesis": "Power, gas, grid, and cooling assets that can feed data-center load growth.", "terms": ("power", "electric", "natural gas", "pipeline", "utility", "energy", "data center", "cooling")},
        {"name": "Natural Gas / LNG", "thesis": "Gas producers, LNG-linked assets, and gas infrastructure that benefit from power-demand growth.", "terms": ("natural gas", "gas", "lng", "pipeline", "midstream")},
        {"name": "Pipelines & Midstream", "thesis": "Toll-road energy infrastructure with throughput, fractionation, storage, and export leverage.", "terms": ("pipeline", "midstream", "storage", "transportation", "fractionation", "gathering")},
        {"name": "Uranium / Nuclear", "thesis": "Nuclear fuel and related assets positioned for baseload power demand.", "terms": ("uranium", "nuclear", "reactor")},
        {"name": "Oil Cash Machines", "thesis": "Oil and royalty companies with cash generation, reserves, and capital discipline.", "terms": ("oil", "petroleum", "crude", "royalty", "permian", "exploration", "production")},
        {"name": "Grid Equipment", "thesis": "Electrical, pole-line, and grid-adjacent suppliers needed for interconnect and transmission buildout.", "terms": ("electric", "power", "grid", "transmission", "line", "equipment", "electrical")},
        {"name": "Critical Minerals", "thesis": "Minerals and materials needed for electrification, batteries, nuclear, and industrial expansion.", "terms": ("mining", "metal", "copper", "uranium", "lithium", "coal", "steel", "materials")},
    ),
    "Technology": (
        {"name": "AI Compute", "thesis": "AI infrastructure, accelerators, servers, networking, and compute platforms.", "terms": ("ai", "artificial intelligence", "compute", "accelerator", "server", "data center")},
        {"name": "Semiconductors", "thesis": "Chip designers, memory, packaging, test, and semiconductor supply-chain names.", "terms": ("semiconductor", "chip", "memory", "electronic", "integrated circuit")},
        {"name": "Software / Data", "thesis": "Software, data infrastructure, analytics, and workflow platforms.", "terms": ("software", "data processing", "information retrieval", "analytics", "platform")},
        {"name": "Networking / Connectivity", "thesis": "Communications, interconnect, storage, and bandwidth enablers.", "terms": ("communications", "network", "connectivity", "storage", "peripheral")},
        {"name": "Cyber / Mission Systems", "thesis": "Security, defense software, identity, and mission-critical systems.", "terms": ("security", "cyber", "defense", "mission", "intelligence")},
    ),
    "Industrials": (
        {"name": "Electrical Equipment / Grid", "thesis": "Industrial suppliers for grid expansion, electrical systems, and power buildout.", "terms": ("electrical", "electric", "power", "grid", "equipment")},
        {"name": "Automation / Machinery", "thesis": "Machinery, sensors, automation, and production equipment that expand capacity.", "terms": ("machinery", "automation", "equipment", "industrial", "manufacturing")},
        {"name": "Aerospace / Defense", "thesis": "Defense, aerospace, space, and high-reliability industrial systems.", "terms": ("aerospace", "defense", "aircraft", "space")},
        {"name": "Construction / Engineering", "thesis": "Engineering, construction, and project execution capacity for infrastructure buildout.", "terms": ("construction", "engineering", "building", "infrastructure")},
        {"name": "Transportation / Logistics", "thesis": "Rail, freight, trucking, shipping, and logistics throughput.", "terms": ("transportation", "logistics", "freight", "rail", "trucking", "shipping")},
    ),
    "Materials": (
        {"name": "Critical Minerals", "thesis": "Copper, lithium, uranium, rare materials, and mining assets.", "terms": ("mining", "metal", "copper", "lithium", "uranium", "gold", "silver")},
        {"name": "Chemicals / Specialty Inputs", "thesis": "Chemicals and specialty materials feeding industrial, chip, and healthcare supply chains.", "terms": ("chemical", "specialty", "materials", "resin", "polymer")},
        {"name": "Steel / Aluminum", "thesis": "Structural metals needed for energy, defense, construction, and reshoring.", "terms": ("steel", "aluminum", "metal")},
        {"name": "Construction Materials", "thesis": "Aggregates, lime, cement, lumber, and building materials.", "terms": ("construction", "cement", "lime", "lumber", "materials")},
        {"name": "Packaging / Paper", "thesis": "Packaging, paper, and containerboard linked to goods flow.", "terms": ("paper", "packaging", "container", "pulp")},
    ),
    "Healthcare": (
        {"name": "Biotech / Pipeline", "thesis": "Drug developers where runway, trial milestones, and funding discipline matter most.", "terms": ("biotech", "pharmaceutical", "therapeutics", "clinical", "drug")},
        {"name": "Med Devices", "thesis": "Device and surgical suppliers with procedure-volume and innovation leverage.", "terms": ("medical", "surgical", "device", "implant")},
        {"name": "Diagnostics / Tools", "thesis": "Diagnostics, lab tools, testing, and life-science infrastructure.", "terms": ("diagnostic", "laboratory", "testing", "genetic", "life science")},
        {"name": "Healthcare Services", "thesis": "Providers, payors, services, and outsourced care infrastructure.", "terms": ("health", "care", "hospital", "clinic", "services")},
        {"name": "Cash-Runway Watch", "thesis": "Pre-revenue and cash-burning names where dilution and runway are the key constraints.", "terms": ("biotech", "pre revenue", "cash burn", "therapeutics")},
    ),
    "Financials": (
        {"name": "Banks / Credit", "thesis": "Deposit, loan, credit quality, and spread-sensitive lenders.", "terms": ("bank", "credit", "loan", "deposit")},
        {"name": "Insurance", "thesis": "Underwriting, float, pricing, and claims-cycle businesses.", "terms": ("insurance", "underwriting", "claims")},
        {"name": "Brokers / Exchanges", "thesis": "Market-structure businesses that benefit from trading, rates, and risk transfer.", "terms": ("broker", "exchange", "markets", "clearing")},
        {"name": "Asset Managers", "thesis": "Fee-based platforms tied to AUM, flows, and market levels.", "terms": ("asset management", "investment", "advisory", "fund")},
        {"name": "Fintech / Payments", "thesis": "Payment rails, processing, platforms, and financial software.", "terms": ("payment", "processing", "fintech", "financial technology")},
    ),
    "Consumer": (
        {"name": "Retail / E-commerce", "thesis": "Retailers and online commerce exposed to inventory, traffic, and consumer demand.", "terms": ("retail", "e-commerce", "store", "merchandise")},
        {"name": "Restaurants / Food", "thesis": "Restaurants, food, beverage, and input-cost-sensitive operators.", "terms": ("restaurant", "food", "beverage", "dining")},
        {"name": "Apparel / Brands", "thesis": "Brands and apparel names where inventory and consumer demand are key.", "terms": ("apparel", "brand", "footwear", "clothing")},
        {"name": "Travel / Leisure", "thesis": "Hotels, leisure, gaming, and travel-linked consumer spend.", "terms": ("hotel", "leisure", "travel", "gaming", "entertainment")},
        {"name": "Consumer Products", "thesis": "Staples and discretionary product companies with margin and channel pressure.", "terms": ("consumer", "products", "household", "personal care")},
    ),
    "Utilities": (
        {"name": "Electric Utilities / Grid", "thesis": "Regulated power companies tied to load growth, grid capex, and reliability.", "terms": ("electric", "utility", "power", "grid")},
        {"name": "Gas Utilities", "thesis": "Gas distribution and pipeline-adjacent regulated utility exposure.", "terms": ("natural gas", "gas", "utility")},
        {"name": "Renewables / Storage", "thesis": "Renewable generation, storage, and grid balancing assets.", "terms": ("renewable", "solar", "wind", "storage", "battery")},
        {"name": "Water Utilities", "thesis": "Water infrastructure and regulated water assets.", "terms": ("water", "utility")},
        {"name": "Nuclear / Baseload", "thesis": "Baseload and nuclear-adjacent power exposure for reliability needs.", "terms": ("nuclear", "baseload", "uranium")},
    ),
    "Real Estate": (
        {"name": "Data Centers / Infrastructure", "thesis": "Real assets tied to compute, power, and digital infrastructure.", "terms": ("data center", "infrastructure", "communications", "tower")},
        {"name": "Industrial / Logistics REITs", "thesis": "Warehouses and logistics real estate tied to supply-chain throughput.", "terms": ("industrial", "warehouse", "logistics", "distribution")},
        {"name": "Residential / Housing", "thesis": "Housing, apartments, and residential-rate sensitivity.", "terms": ("residential", "apartment", "home", "housing")},
        {"name": "Retail / Office", "thesis": "Property types most exposed to traffic, tenants, refinancing, and utilization.", "terms": ("retail", "office", "property", "realty")},
        {"name": "Refinancing Watch", "thesis": "High-rate and maturity-wall pressure in real estate capital structures.", "terms": ("debt", "mortgage", "refinance", "interest")},
    ),
    "Communication Services": (
        {"name": "Telecom / Fiber", "thesis": "Networks, fiber, connectivity, and bandwidth infrastructure.", "terms": ("telecommunication", "telecom", "fiber", "network", "communications")},
        {"name": "Media / Streaming", "thesis": "Content, streaming, advertising, and media monetization.", "terms": ("media", "streaming", "broadcast", "content")},
        {"name": "Advertising / Platforms", "thesis": "Ad platforms, marketplaces, and audience monetization.", "terms": ("advertising", "platform", "search", "social")},
        {"name": "Entertainment / Gaming", "thesis": "Entertainment, gaming, live events, and content IP.", "terms": ("entertainment", "gaming", "music", "sports")},
    ),
    "General": (
        {"name": "AI / Compute Adjacent", "thesis": "General bucket names exposed to compute, data, software, or infrastructure themes.", "terms": ("ai", "compute", "software", "data", "semiconductor")},
        {"name": "Energy / Resources Adjacent", "thesis": "General names tied to energy, materials, power, or industrial input supply.", "terms": ("energy", "power", "mining", "metal", "oil", "gas")},
        {"name": "Profitable Compounders", "thesis": "General companies with stronger current scores and cleaner cash generation.", "terms": ("services", "products", "systems", "technology", "industrial")},
        {"name": "Turnaround / Repair", "thesis": "Names where the thesis depends on cash-flow repair, refinancing, or operating cleanup.", "terms": ("debt", "restructuring", "cash burn", "negative owner earnings", "turnaround")},
    ),
}


def list_sector_summaries(session: Session) -> list[dict[str, Any]]:
    rows = _sector_rows(session)
    grouped = _group_by_sector(rows)
    summaries = []
    for sector, items in grouped.items():
        scores = [_float(item["score"]) for item in items if _float(item["score"]) is not None]
        model_scores = [_float(item["model_family_score"]) for item in items if _float(item["model_family_score"]) is not None]
        bottlenecks = _top_bottlenecks(items, limit=3)
        summaries.append(
            {
                "sector": sector,
                "sector_slug": _slug(sector),
                "company_count": len(items),
                "avg_score": _round(mean(scores)) if scores else None,
                "avg_model_family_score": _round(mean(model_scores)) if model_scores else None,
                "bullish_count": sum(1 for item in items if "BULLISH" in str(item["stance"] or "")),
                "adequate_count": sum(1 for item in items if str(item["data_quality_tier"] or "").upper() == "ADEQUATE"),
                "ai_compute_count": sum(1 for item in items if item["focus_family"] == "AI / compute"),
                "energy_resources_count": sum(1 for item in items if item["focus_family"] == "Energy / resources"),
                "top_bottlenecks": bottlenecks,
            }
        )
    summaries.sort(key=lambda item: (item["company_count"], item["avg_score"] or 0), reverse=True)
    return summaries


def sector_profile(session: Session, sector_slug: str) -> dict[str, Any] | None:
    rows = _sector_rows(session)
    grouped = _group_by_sector(rows)
    sector = next((name for name in grouped if _slug(name) == sector_slug), None)
    if sector is None:
        return None
    items = grouped[sector]
    scores = [_float(item["score"]) for item in items if _float(item["score"]) is not None]
    model_scores = [_float(item["model_family_score"]) for item in items if _float(item["model_family_score"]) is not None]
    bottlenecks = _top_bottlenecks(items, limit=12)
    supply_chain = _supply_chain_bottlenecks(items)
    strategic_bottlenecks = _strategic_bottlenecks(sector, items, rows)
    enablers = _enablers(items, supply_chain)
    laggers = _laggers(items)
    leaders = _leaders(items)
    profile = {
        "version": SECTOR_INTELLIGENCE_VERSION,
        "sector": sector,
        "sector_slug": _slug(sector),
        "company_count": len(items),
        "avg_score": _round(mean(scores)) if scores else None,
        "avg_model_family_score": _round(mean(model_scores)) if model_scores else None,
        "bullish_count": sum(1 for item in items if "BULLISH" in str(item["stance"] or "")),
        "adequate_count": sum(1 for item in items if str(item["data_quality_tier"] or "").upper() == "ADEQUATE"),
        "top_bottlenecks": bottlenecks,
        "supply_chain_bottlenecks": supply_chain,
        "strategic_bottlenecks": strategic_bottlenecks,
        "sub_sectors": _sub_sector_summaries(sector, items, rows),
        "bottleneck_enablers": enablers,
        "laggers": laggers,
        "leaders": leaders,
        "profile_notes": _profile_notes(sector, items, supply_chain, laggers),
    }
    return profile


def sub_sector_profile(session: Session, sector_slug: str, sub_sector_slug: str) -> dict[str, Any] | None:
    rows = _sector_rows(session)
    grouped = _group_by_sector(rows)
    sector = next((name for name in grouped if _slug(name) == sector_slug), None)
    if sector is None:
        return None
    definition = _sub_sector_definition(sector, sub_sector_slug)
    if definition is None:
        return None
    sector_items = grouped[sector]
    items = _sub_sector_items(sector_items, definition)
    scores = [_float(item["score"]) for item in items if _float(item["score"]) is not None]
    model_scores = [_float(item["model_family_score"]) for item in items if _float(item["model_family_score"]) is not None]
    bottlenecks = _top_bottlenecks(items, limit=10)
    supply_chain = _supply_chain_bottlenecks(items)
    strategic_bottlenecks = _strategic_bottlenecks(f"{sector} / {definition['name']}", items, rows)
    return {
        "version": SECTOR_INTELLIGENCE_VERSION,
        "sector": sector,
        "sector_slug": _slug(sector),
        "sub_sector": definition["name"],
        "sub_sector_slug": _slug(definition["name"]),
        "thesis": definition["thesis"],
        "company_count": len(items),
        "avg_score": _round(mean(scores)) if scores else None,
        "avg_model_family_score": _round(mean(model_scores)) if model_scores else None,
        "bullish_count": sum(1 for item in items if "BULLISH" in str(item["stance"] or "")),
        "adequate_count": sum(1 for item in items if str(item["data_quality_tier"] or "").upper() == "ADEQUATE"),
        "top_bottlenecks": bottlenecks,
        "supply_chain_bottlenecks": supply_chain,
        "strategic_bottlenecks": strategic_bottlenecks,
        "bottleneck_enablers": _enablers(items, supply_chain),
        "laggers": _laggers(items),
        "leaders": _leaders(items),
        "profile_notes": [
            f"{definition['name']} is a {sector} sub-sector lane built from {len(items)} matching company reports.",
            definition["thesis"],
        ],
    }


def _sector_rows(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(Company, CompanyReport, CompanyBottleneckSnapshot)
        .join(CompanyReport, CompanyReport.company_id == Company.id)
        .outerjoin(CompanyBottleneckSnapshot, CompanyBottleneckSnapshot.company_id == Company.id)
    ).all()
    payload = []
    for company, report, bottleneck in rows:
        stats = dict(report.key_stats or {})
        sector = _sector_from_report(company, report, stats)
        payload.append(
            {
                "sector": sector,
                "ticker": report.ticker,
                "company_name": report.company_name,
                "sic_description": company.sic_description,
                "sector_text": f"{sector} {company.sic_description or ''} {report.company_name}",
                "stance": report.stance,
                "score": report.composite_score,
                "bullish_score": report.bullish_score,
                "bearish_score": report.bearish_score,
                "data_quality_tier": report.data_quality_tier,
                "latest_filing_date": report.latest_filing_date,
                "focus_family": bottleneck.focus_family if bottleneck else "General",
                "model_family": bottleneck.model_family if bottleneck else stats.get("route_family") or "unknown",
                "model_family_score": bottleneck.model_family_score if bottleneck else None,
                "bottlenecks": list(bottleneck.bottlenecks or []) if bottleneck else [],
                "management_bottlenecks": list(bottleneck.management_bottlenecks or []) if bottleneck else [],
                "revenue_growth_pct": _float(stats.get("revenue_growth_pct")),
                "owner_earnings": _float(stats.get("owner_earnings")),
                "owner_earnings_margin_pct": _float(stats.get("owner_earnings_margin_pct")),
                "accounting_quality_score": _float(stats.get("accounting_quality_score")),
                "a_his_score": _float(stats.get("a_his_score")),
                "canonical_facts_count": int(stats.get("canonical_facts_count") or 0),
                "future_bucket": stats.get("future_bucket"),
                "future_reason": stats.get("future_reason"),
            }
        )
    return payload


def _group_by_sector(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["sector"]].append(row)
    return dict(sorted(grouped.items(), key=lambda item: item[0]))


def _sector_from_report(company: Company, report: CompanyReport, stats: dict[str, Any]) -> str:
    if isinstance(stats.get("gics_sector"), str) and stats["gics_sector"]:
        return str(stats["gics_sector"])
    text = (company.sic_description or "").lower()
    mapping = (
        ("Technology", ("software", "computer", "semiconductor", "data processing", "electronic", "communications")),
        ("Energy", ("oil", "gas", "petroleum", "coal", "drilling", "pipeline", "energy")),
        ("Materials", ("mining", "metal", "chemical", "paper", "lumber", "steel")),
        ("Industrials", ("machinery", "transportation", "aerospace", "defense", "construction", "industrial")),
        ("Consumer", ("retail", "restaurant", "apparel", "food", "beverage", "consumer", "hotel")),
        ("Healthcare", ("medical", "pharmaceutical", "biotech", "health", "diagnostic", "surgical")),
        ("Financials", ("bank", "insurance", "finance", "broker", "asset management")),
        ("Real Estate", ("real estate", "reit", "property", "realty")),
        ("Utilities", ("utility", "electric", "water", "natural gas transmission")),
        ("Communication Services", ("media", "telecommunications", "broadcast", "entertainment")),
    )
    for sector, keywords in mapping:
        if any(keyword in text for keyword in keywords):
            return sector
    return "General"


def _top_bottlenecks(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    severity: dict[str, float] = defaultdict(float)
    examples: dict[str, list[str]] = defaultdict(list)
    for item in items:
        for blocker in item["bottlenecks"][:3]:
            category = str(blocker.get("category") or "")
            if not category:
                continue
            counts[category] += 1
            severity[category] = max(severity[category], _float(blocker.get("severity")) or 0.0)
            if len(examples[category]) < 5:
                examples[category].append(f"{item['ticker']}: {blocker.get('detail') or category}")
    return [
        {
            "category": category,
            "company_count": count,
            "max_severity": _round(severity[category]),
            "examples": examples[category],
        }
        for category, count in counts.most_common(limit)
    ]


def _supply_chain_bottlenecks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    evidence: dict[str, list[str]] = defaultdict(list)
    keywords = ("supply", "energy", "power", "commodity", "inventory", "working-capital", "demand", "backlog", "ai compute", "gpu", "capacity", "debt", "refinancing")
    for item in items:
        blockers = [*item["management_bottlenecks"], *item["bottlenecks"]]
        for blocker in blockers:
            category = str(blocker.get("category") or "")
            detail = str(blocker.get("detail") or blocker.get("evidence") or category)
            haystack = f"{category} {detail}".lower()
            if not any(keyword in haystack for keyword in keywords):
                continue
            counts[category] += 1
            if len(evidence[category]) < 5:
                evidence[category].append(f"{item['ticker']}: {detail[:180]}")
    return [
        {"category": category, "company_count": count, "evidence": evidence[category]}
        for category, count in counts.most_common(8)
    ]


def _strategic_bottlenecks(
    sector: str,
    sector_items: list[dict[str, Any]],
    all_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results = []
    sector_haystack = " ".join(_item_text(item) for item in sector_items).lower()
    for definition in STRATEGIC_BOTTLENECKS:
        affected_count = _affected_count(sector_items, definition)
        sector_bias = 18 if sector in definition["sector_bias"] else 0
        term_pressure = sum(1 for term in definition["affected_terms"] if term in sector_haystack) * 5
        pressure_score = min(100, affected_count * 2 + sector_bias + term_pressure)
        if pressure_score < 18:
            continue
        enablers = _strategic_enablers(all_items, definition)
        if not enablers:
            continue
        results.append(
            {
                "category": definition["category"],
                "thesis": definition["thesis"],
                "pressure_score": round(float(pressure_score), 1),
                "affected_company_count": affected_count,
                "enablers": enablers,
            }
        )
    results.sort(key=lambda item: (item["pressure_score"], item["affected_company_count"]), reverse=True)
    return results[:5]


def _affected_count(items: list[dict[str, Any]], definition: dict[str, Any]) -> int:
    count = 0
    for item in items:
        text = _item_text(item)
        if any(term in text for term in definition["affected_terms"]):
            count += 1
            continue
        blockers = " ".join(
            f"{blocker.get('category', '')} {blocker.get('detail', '')} {blocker.get('evidence', '')}"
            for blocker in [*item["management_bottlenecks"], *item["bottlenecks"]]
        ).lower()
        if any(term in blockers for term in definition["affected_terms"]):
            count += 1
    return count


def _strategic_enablers(items: list[dict[str, Any]], definition: dict[str, Any]) -> list[dict[str, Any]]:
    scored = []
    for item in items:
        text = _item_text(item)
        matched_terms = [term for term in definition["enabler_terms"] if term in text]
        if not matched_terms:
            continue
        score = _float(item["score"]) or 0.0
        model_score = _float(item["model_family_score"]) or score
        quality = _float(item["accounting_quality_score"]) or score
        revenue_growth = _float(item["revenue_growth_pct"]) or 0.0
        owner_earnings = _float(item["owner_earnings"]) or 0.0
        strategic_score = (
            min(5, len(matched_terms)) * 8.0
            + score * 0.22
            + model_score * 0.18
            + quality * 0.16
            + max(-10.0, min(30.0, revenue_growth)) * 0.18
        )
        if owner_earnings > 0:
            strategic_score += 8
        if item["focus_family"] in definition["preferred_focus"]:
            strategic_score += 10
        scored.append((strategic_score, matched_terms, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    payload = []
    seen: set[str] = set()
    for strategic_score, matched_terms, item in scored:
        if item["ticker"] in seen:
            continue
        seen.add(item["ticker"])
        stock = _stock_payload(item, enabler_score=round(strategic_score, 1))
        stock["strategic_role"] = ", ".join(matched_terms[:4])
        payload.append(stock)
        if len(payload) >= 8:
            break
    return payload


def _sub_sector_summaries(
    sector: str,
    sector_items: list[dict[str, Any]],
    all_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summaries = []
    for definition in SUB_SECTOR_DEFINITIONS.get(sector, SUB_SECTOR_DEFINITIONS["General"]):
        items = _sub_sector_items(sector_items, definition)
        if not items:
            continue
        scores = [_float(item["score"]) for item in items if _float(item["score"]) is not None]
        model_scores = [_float(item["model_family_score"]) for item in items if _float(item["model_family_score"]) is not None]
        strategic = _strategic_bottlenecks(f"{sector} / {definition['name']}", items, all_items)
        summaries.append(
            {
                "name": definition["name"],
                "slug": _slug(definition["name"]),
                "thesis": definition["thesis"],
                "company_count": len(items),
                "avg_score": _round(mean(scores)) if scores else None,
                "avg_model_family_score": _round(mean(model_scores)) if model_scores else None,
                "bullish_count": sum(1 for item in items if "BULLISH" in str(item["stance"] or "")),
                "top_bottlenecks": _top_bottlenecks(items, limit=3),
                "strategic_bottlenecks": strategic[:3],
                "leaders": _leaders(items)[:5],
            }
        )
    summaries.sort(key=lambda item: (item["company_count"], item["avg_score"] or 0), reverse=True)
    return summaries


def _sub_sector_definition(sector: str, sub_sector_slug: str) -> dict[str, Any] | None:
    for definition in SUB_SECTOR_DEFINITIONS.get(sector, SUB_SECTOR_DEFINITIONS["General"]):
        if _slug(definition["name"]) == sub_sector_slug:
            return definition
    return None


def _sub_sector_items(items: list[dict[str, Any]], definition: dict[str, Any]) -> list[dict[str, Any]]:
    matched = []
    terms = tuple(str(term).lower() for term in definition["terms"])
    for item in items:
        haystack = _item_full_text(item)
        blockers = " ".join(
            f"{blocker.get('category', '')} {blocker.get('detail', '')} {blocker.get('evidence', '')}"
            for blocker in [*item["management_bottlenecks"], *item["bottlenecks"]]
        ).lower()
        if any(term in haystack or term in blockers for term in terms):
            matched.append(item)
    return matched


def _enablers(items: list[dict[str, Any]], supply_chain: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocker_terms = " ".join(item["category"] for item in supply_chain).lower()
    scored = []
    for item in items:
        score = _float(item["score"]) or 0.0
        model_score = _float(item["model_family_score"]) or score
        revenue_growth = _float(item["revenue_growth_pct"]) or 0.0
        owner_earnings = _float(item["owner_earnings"]) or 0.0
        quality = _float(item["accounting_quality_score"]) or score
        enabler_score = (score * 0.35) + (model_score * 0.25) + (quality * 0.2) + max(-20.0, min(40.0, revenue_growth)) * 0.2
        if owner_earnings > 0:
            enabler_score += 8
        if item["focus_family"] == "AI / compute" and any(term in blocker_terms for term in ("ai", "gpu", "capacity", "compute")):
            enabler_score += 10
        if item["focus_family"] == "Energy / resources" and any(term in blocker_terms for term in ("energy", "power", "commodity")):
            enabler_score += 10
        if enabler_score < 55:
            continue
        scored.append((enabler_score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [_stock_payload(item, enabler_score=round(score, 1)) for score, item in scored[:12]]


def _laggers(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for item in items:
        score = _float(item["score"]) or 0.0
        blocker_severity = max([_float(blocker.get("severity")) or 0.0 for blocker in item["bottlenecks"]] or [0.0])
        lag_score = (100.0 - score) + blocker_severity * 0.45
        if item["data_quality_tier"] in {"INSUFFICIENT", "PARTIAL"}:
            lag_score += 12
        scored.append((lag_score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [_stock_payload(item, enabler_score=round(score, 1)) for score, item in scored[:15]]


def _leaders(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(items, key=lambda item: (_float(item["score"]) or 0.0, _float(item["model_family_score"]) or 0.0), reverse=True)
    return [_stock_payload(item) for item in ordered[:12]]


def _stock_payload(item: dict[str, Any], *, enabler_score: float | None = None) -> dict[str, Any]:
    return {
        "ticker": item["ticker"],
        "company_name": item["company_name"],
        "stance": item["stance"],
        "score": _round(_float(item["score"])),
        "model_family": item["model_family"],
        "model_family_score": _round(_float(item["model_family_score"])),
        "data_quality_tier": item["data_quality_tier"],
        "latest_filing_date": item["latest_filing_date"],
        "revenue_growth_pct": _round(_float(item["revenue_growth_pct"])),
        "owner_earnings": _round(_float(item["owner_earnings"])),
        "accounting_quality_score": _round(_float(item["accounting_quality_score"])),
        "a_his_score": _round(_float(item["a_his_score"])),
        "enabler_score": enabler_score,
        "top_bottleneck": item["bottlenecks"][0] if item["bottlenecks"] else None,
        "future_bucket": item["future_bucket"],
    }


def _profile_notes(sector: str, items: list[dict[str, Any]], supply_chain: list[dict[str, Any]], laggers: list[dict[str, Any]]) -> list[str]:
    notes = [
        f"{sector} profile is built from {len(items)} cached company reports and bottleneck snapshots.",
    ]
    if supply_chain:
        notes.append(f"Most visible sector constraint: {supply_chain[0]['category']} across {supply_chain[0]['company_count']} companies.")
    if laggers:
        notes.append(f"Lagger watch starts with {laggers[0]['ticker']} due to score/bottleneck pressure.")
    return notes


def _item_text(item: dict[str, Any]) -> str:
    return f"{item.get('sector_text') or ''} {item.get('focus_family') or ''} {item.get('model_family') or ''}".lower()


def _item_full_text(item: dict[str, Any]) -> str:
    blockers = " ".join(
        f"{blocker.get('category', '')} {blocker.get('detail', '')} {blocker.get('evidence', '')}"
        for blocker in [*item.get("management_bottlenecks", []), *item.get("bottlenecks", [])]
    )
    return f"{_item_text(item)} {blockers}".lower()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "general"


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None
