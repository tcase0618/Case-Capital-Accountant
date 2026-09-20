from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from accountant.db.models import Company, CompanyBottleneckSnapshot, CompanyReport
from accountant.ingest.filing_text_parser import FilingTextParser, TextSourceType
from accountant.research.company_router import CompanyRoute, route_company


BOTTLENECK_ENGINE_VERSION = "BOTTLENECK_ENGINE_V1"

AI_SIC_KEYWORDS = (
    "semiconductors",
    "semiconductor",
    "software",
    "prepackaged software",
    "computer programming",
    "data processing",
    "information retrieval",
    "computer integrated systems",
    "computer communications",
    "electronic computers",
    "computer peripheral",
    "computer storage",
)
AI_NAME_KEYWORDS = (
    "artificial intelligence",
    "machine learning",
    "cerebras",
    "palantir",
    "nvidia",
    "super micro computer",
    "soundhound ai",
    "c3.ai",
    "bigbear.ai",
    "guardforce ai",
    "applied digital",
    "coreweave",
    "datadog",
    "snowflake",
)
ENERGY_KEYWORDS = (
    "oil",
    "gas",
    "petroleum",
    "natural gas",
    "crude",
    "drilling",
    "coal",
    "pipeline",
    "energy",
    "electric services",
    "power",
    "solar",
    "renewable",
    "uranium",
    "nuclear",
    "metal mining",
    "gold and silver ores",
    "lithium",
    "battery",
)

_MANAGEMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "AI compute capacity / GPU supply": (
        "gpu",
        "accelerator",
        "compute capacity",
        "data center capacity",
        "artificial intelligence",
        "ai demand",
        "supply constrained",
    ),
    "Energy input cost / power availability": (
        "power availability",
        "electricity costs",
        "energy costs",
        "natural gas prices",
        "commodity prices",
        "fuel costs",
        "crude oil",
    ),
    "Debt maturity / refinancing pressure": (
        "debt maturity",
        "maturities",
        "refinance",
        "refinancing",
        "credit facility",
        "covenant",
        "interest expense",
    ),
    "Customer demand / backlog pressure": (
        "customer demand",
        "backlog",
        "order volume",
        "bookings",
        "sales cycle",
        "customer concentration",
    ),
    "Supply chain / input cost pressure": (
        "supply chain",
        "component shortage",
        "raw materials",
        "inflationary pressure",
        "freight",
        "logistics",
    ),
    "Inventory / working-capital pressure": (
        "inventory",
        "working capital",
        "accounts receivable",
        "collection",
        "obsolescence",
        "write-down",
    ),
    "Regulatory / legal overhang": (
        "regulatory",
        "litigation",
        "investigation",
        "compliance",
        "lawsuit",
        "subpoena",
    ),
    "Labor / execution constraints": (
        "labor",
        "wage",
        "hiring",
        "retention",
        "turnover",
        "skilled personnel",
    ),
}


@dataclass(frozen=True)
class BottleneckPayload:
    focus_family: str
    model_family: str
    model_family_reason: str
    model_family_score: float | None
    bottlenecks: list[dict[str, object]]
    management_bottlenecks: list[dict[str, object]]


def classify_focus_family(ticker: str, name: str, sic_description: str | None) -> str:
    sic = (sic_description or "").lower()
    company = (name or "").lower()
    normalized_ticker = (ticker or "").upper()
    if (
        any(keyword in sic for keyword in AI_SIC_KEYWORDS)
        or any(keyword in company for keyword in AI_NAME_KEYWORDS)
        or normalized_ticker in {"AI", "NVDA", "PLTR", "SMCI", "SOUN", "BBAI"}
    ):
        return "AI / compute"
    if any(keyword in sic for keyword in ENERGY_KEYWORDS) or any(keyword in company for keyword in ENERGY_KEYWORDS):
        return "Energy / resources"
    return "General"


def build_bottleneck_payload(
    *,
    company: Company,
    report: CompanyReport,
    filing_text: str | None = None,
) -> BottleneckPayload:
    stats = _as_dict(report.key_stats)
    route = route_company(
        gics_sector=_string(stats.get("gics_sector")),
        sic_description=company.sic_description,
        revenue=_float(stats.get("revenue")),
        owner_earnings=_float(stats.get("owner_earnings")),
        net_income=_float(stats.get("net_income")),
    )
    return BottleneckPayload(
        focus_family=classify_focus_family(report.ticker, report.company_name, company.sic_description),
        model_family=route.family,
        model_family_reason=route.reason,
        model_family_score=_model_family_score(route, stats),
        bottlenecks=_metric_bottlenecks(report, stats, route),
        management_bottlenecks=extract_management_bottlenecks(filing_text or report.report_markdown),
    )


def upsert_company_bottleneck_snapshot(
    session: Session,
    *,
    company: Company,
    report: CompanyReport,
    filing_text: str | None = None,
) -> CompanyBottleneckSnapshot:
    payload = build_bottleneck_payload(company=company, report=report, filing_text=filing_text)
    values = {
        "company_id": company.id,
        "ticker": report.ticker,
        "company_name": report.company_name,
        "sic": company.sic,
        "sic_description": company.sic_description,
        "focus_family": payload.focus_family,
        "model_family": payload.model_family,
        "model_family_reason": payload.model_family_reason,
        "stance": report.stance,
        "score": report.composite_score,
        "model_family_score": payload.model_family_score,
        "data_quality_tier": report.data_quality_tier,
        "latest_filing_date": report.latest_filing_date,
        "bottlenecks": payload.bottlenecks,
        "management_bottlenecks": payload.management_bottlenecks,
        "source": BOTTLENECK_ENGINE_VERSION,
    }
    stmt = pg_insert(CompanyBottleneckSnapshot).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_company_bottleneck_snapshots_company",
        set_={**values, "updated_at": stmt.excluded.updated_at},
    )
    session.execute(stmt)
    session.flush()
    return session.execute(
        select(CompanyBottleneckSnapshot).where(CompanyBottleneckSnapshot.company_id == company.id)
    ).scalar_one()


def refresh_bottleneck_cache(session: Session, *, limit: int | None = None) -> dict[str, Any]:
    query = (
        select(Company, CompanyReport)
        .join(CompanyReport, CompanyReport.company_id == Company.id)
        .order_by(CompanyReport.ticker.asc())
    )
    if limit:
        query = query.limit(limit)
    rows = session.execute(query).all()
    family_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    for company, report in rows:
        snapshot = upsert_company_bottleneck_snapshot(session, company=company, report=report)
        family_counts[snapshot.focus_family] += 1
        for item in (snapshot.bottlenecks or [])[:3]:
            category = str(item.get("category") or "")
            if category:
                category_counts[category] += 1
    return {
        "companies_refreshed": len(rows),
        "focus_family_counts": dict(family_counts),
        "top_bottlenecks": [
            {"category": category, "company_count": count}
            for category, count in category_counts.most_common(15)
        ],
    }


def bottleneck_summary_from_cache(session: Session) -> dict[str, Any]:
    rows = session.execute(select(CompanyBottleneckSnapshot)).scalars().all()
    family_counts: Counter[str] = Counter()
    overall_counts: Counter[str] = Counter()
    family_bottlenecks: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        family_counts[row.focus_family] += 1
        for item in (row.bottlenecks or [])[:3]:
            category = str(item.get("category") or "")
            detail = str(item.get("detail") or "")
            if not category:
                continue
            overall_counts[category] += 1
            family_bottlenecks[row.focus_family][category] += 1
            if len(examples[row.focus_family][category]) < 8:
                examples[row.focus_family][category].append(f"{row.ticker}: {detail}")
    return {
        "companies_analyzed": len(rows),
        "focus_family_counts": dict(family_counts),
        "ai_compute_top_bottlenecks": _family_payload("AI / compute", family_bottlenecks, examples),
        "energy_resources_top_bottlenecks": _family_payload("Energy / resources", family_bottlenecks, examples),
        "overall_top_bottlenecks": [
            {"category": category, "company_count": count}
            for category, count in overall_counts.most_common(15)
        ],
    }


def extract_management_bottlenecks(text: str | None) -> list[dict[str, object]]:
    if not text:
        return []
    parsed = FilingTextParser.parse_filing_text(
        text[:250_000],
        company_id="unknown",
        fiscal_year=0,
        source_type=TextSourceType.ITEM_7_MD_A,
    )
    hits: dict[str, dict[str, object]] = {}
    for sentence in FilingTextParser.filter_sentences(parsed, min_words=6, max_words=80):
        normalized = sentence.normalized_text
        for category, keywords in _MANAGEMENT_KEYWORDS.items():
            matched = [keyword for keyword in keywords if keyword in normalized]
            if not matched:
                continue
            current = hits.setdefault(
                category,
                {
                    "category": category,
                    "severity": 50.0,
                    "evidence": sentence.original_text[:220],
                    "matched_terms": [],
                    "source": "filing_text",
                },
            )
            current["severity"] = min(100.0, float(current["severity"]) + 8.0)
            current["matched_terms"] = sorted(set([*current["matched_terms"], *matched]))
            break
    return sorted(hits.values(), key=lambda item: float(item["severity"]), reverse=True)[:5]


def _metric_bottlenecks(
    report: CompanyReport,
    stats: dict[str, Any],
    route: CompanyRoute,
) -> list[dict[str, object]]:
    items: list[tuple[float, str, str]] = []

    def add(severity: float, category: str, detail: str) -> None:
        items.append((severity, category, detail))

    revenue = _float(stats.get("revenue"))
    revenue_growth = _float(stats.get("revenue_growth_pct"))
    net_income = _float(stats.get("net_income"))
    owner_earnings = _float(stats.get("owner_earnings"))
    owner_margin = _float(stats.get("owner_earnings_margin_pct"))
    margin = _float(stats.get("margin_pct"))
    assets = _float(stats.get("assets"))
    liabilities = _float(stats.get("liabilities"))
    dilution = _float(stats.get("dilution_growth_pct"))
    coverage = _float(stats.get("overall_coverage_pct"))
    accounting_quality = _float(stats.get("accounting_quality_score"))
    a_his = _float(stats.get("a_his_score"))
    factor_warnings = _float(stats.get("factor_warning_count"))
    eps_forecast = _float(stats.get("eps_forecast"))
    leverage = liabilities / assets * 100 if liabilities is not None and assets and assets > 0 else None

    if report.data_quality_tier in {"INSUFFICIENT", "PARTIAL"} or (coverage is not None and coverage < 55):
        add(90, "Insufficient earnings-data coverage", f"tier={report.data_quality_tier}, coverage={_fmt(coverage, '%')}")
    if factor_warnings and factor_warnings > 0:
        add(82, "Missing/incomplete accounting factor pack", f"factor warnings={factor_warnings:.0f}")
    elif any(stats.get(key) is None for key in ("beneish_m_score", "piotroski_f_score", "altman_z_score")):
        add(68, "Missing/incomplete accounting factor pack", "Beneish/Piotroski/Altman unavailable")
    if revenue is None or revenue_growth is None:
        add(70, "Revenue visibility gap", f"revenue={_fmt(revenue)}, revenue growth={_fmt(revenue_growth, '%')}")
    elif revenue_growth < 0:
        add(82 + min(abs(revenue_growth), 30) / 2, "Revenue contraction", f"revenue growth={_fmt(revenue_growth, '%')}")
    elif revenue_growth < 5 and route.family in {"operating_company", "ai_compute", "energy_resources"}:
        add(55, "Slow revenue growth", f"revenue growth={_fmt(revenue_growth, '%')}")
    if owner_earnings is None:
        add(62, "Owner-earnings visibility gap", "owner earnings proxy=N/A")
    elif owner_earnings < 0:
        add(84, "Negative owner earnings / cash burn", f"owner earnings={owner_earnings:,.0f}, owner margin={_fmt(owner_margin, '%')}")
    if net_income is not None and net_income < 0:
        add(82, "Net losses / weak profitability", f"net income={net_income:,.0f}, margin={_fmt(margin, '%')}")
    elif margin is not None and margin < 5:
        add(62, "Thin profit margin", f"margin={_fmt(margin, '%')}")
    if leverage is not None:
        if leverage >= 90:
            add(92, "Very high leverage", f"liabilities/assets={leverage:.1f}%")
        elif leverage >= 75:
            add(78, "High leverage", f"liabilities/assets={leverage:.1f}%")
        elif leverage >= 60:
            add(60, "Elevated leverage", f"liabilities/assets={leverage:.1f}%")
    if dilution is not None:
        if dilution >= 25:
            add(92, "Severe dilution", f"share count growth={_fmt(dilution, '%')}")
        elif dilution >= 10:
            add(78, "Material dilution", f"share count growth={_fmt(dilution, '%')}")
    if accounting_quality is not None and accounting_quality < 50:
        add(75, "Weak accounting quality score", f"accounting quality={_fmt(accounting_quality)}")
    if a_his is not None and a_his < 50:
        add(76, "Weak A-HIS accounting ledger score", f"A-HIS={_fmt(a_his)}")
    if eps_forecast is not None and eps_forecast < 0:
        add(70, "Negative EPS forecast", f"CC EPS forecast={eps_forecast:.2f}")

    if not items:
        items.append((20, "No major blocker detected", "No deterministic blocker triggered"))

    by_category: dict[str, tuple[float, str]] = {}
    for severity, category, detail in items:
        if category not in by_category or severity > by_category[category][0]:
            by_category[category] = (severity, detail)
    return [
        {"category": category, "severity": round(severity, 1), "detail": detail}
        for category, (severity, detail) in sorted(by_category.items(), key=lambda item: item[1][0], reverse=True)[:3]
    ]


def _model_family_score(route: CompanyRoute, stats: dict[str, Any]) -> float | None:
    base = _float(stats.get("a_his_score")) or _float(stats.get("factor_quality_score")) or _float(stats.get("accounting_quality_score"))
    revenue_growth = _float(stats.get("revenue_growth_pct"))
    owner_margin = _float(stats.get("owner_earnings_margin_pct"))
    margin = _float(stats.get("margin_pct"))
    leverage = _leverage_pct(stats)
    dilution = _float(stats.get("dilution_growth_pct"))
    score = 50.0 if base is None else base
    if route.family == "financials":
        score = _blend(score, 100.0 - min(abs(leverage or 75.0), 100.0), 0.25)
    elif route.family == "reit_asset_heavy":
        score = _blend(score, 100.0 - min(abs(leverage or 65.0), 100.0), 0.30)
        score = _blend(score, _bounded(owner_margin, 0.0, 40.0), 0.20)
    elif route.family == "pre_revenue":
        score = _blend(score, 100.0 - min(max(dilution or 0.0, 0.0) * 2.0, 100.0), 0.35)
        score = _blend(score, 100.0 - min(abs(owner_margin or -50.0), 100.0), 0.25)
    elif route.family == "operating_company":
        score = _blend(score, _bounded(owner_margin, -20.0, 40.0), 0.20)
        score = _blend(score, _bounded(revenue_growth, -20.0, 50.0), 0.15)
    else:
        score = _blend(score, _bounded(margin, -30.0, 30.0), 0.20)
    return round(max(0.0, min(100.0, score)), 1)


def _family_payload(
    family: str,
    family_bottlenecks: dict[str, Counter[str]],
    examples: dict[str, dict[str, list[str]]],
) -> list[dict[str, Any]]:
    return [
        {
            "category": category,
            "company_count": count,
            "examples": examples[family][category],
        }
        for category, count in family_bottlenecks[family].most_common(10)
    ]


def _bounded(value: float | None, low: float, high: float) -> float:
    if value is None:
        return 50.0
    if high == low:
        return 50.0
    return max(0.0, min(100.0, (value - low) / (high - low) * 100.0))


def _blend(left: float, right: float, right_weight: float) -> float:
    return left * (1.0 - right_weight) + right * right_weight


def _leverage_pct(stats: dict[str, Any]) -> float | None:
    assets = _float(stats.get("assets"))
    liabilities = _float(stats.get("liabilities"))
    if assets in (None, 0) or liabilities is None:
        return None
    return liabilities / assets * 100.0


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _fmt(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}{suffix}"
