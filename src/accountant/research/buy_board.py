from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from accountant.db import create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import BuyBoardCandidate, BuyBoardSnapshot, CompanyReport, RawFact
from accountant.logging import get_logger
from accountant.market.alpaca_research import quote as alpaca_quote

log = get_logger(__name__)

_ET = ZoneInfo("America/New_York")
_ACTIVE_STANCES = {"MOST_BULLISH", "BULLISH"}


@dataclass
class BuyBoardSnapshotState:
    running: bool = False
    started_at: str | None = None
    next_refresh_at: str | None = None
    last_refresh_at: str | None = None
    last_action: str | None = None
    last_error: str | None = None
    candidate_count: int = 0
    last_refresh_count: int = 0
    last_success_count: int = 0


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _safe_float(value) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _as_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _pick_price(quote_payload: dict[str, float | None] | None) -> float | None:
    if not quote_payload:
        return None
    for key in ("last", "close", "bid", "ask"):
        price = _safe_float(quote_payload.get(key))
        if price and price > 0:
            return price
    bid = _safe_float(quote_payload.get("bid"))
    ask = _safe_float(quote_payload.get("ask"))
    if bid and ask and bid > 0 and ask > 0:
        return round((bid + ask) / 2, 4)
    return None


def _qualifies_for_buy_board(report: CompanyReport) -> bool:
    stats = report.key_stats or {}
    canonical = int(stats.get("canonical_facts_count") or 0)
    quality = _safe_float(stats.get("accounting_quality_score")) or report.composite_score
    owner_earnings = _safe_float(stats.get("owner_earnings"))
    net_income = _safe_float(stats.get("net_income"))
    revenue_growth = _safe_float(stats.get("revenue_growth_pct")) or 0.0
    return (
        report.stance in _ACTIVE_STANCES
        and report.composite_score >= 70
        and (report.data_quality_tier or "").upper() == "ADEQUATE"
        and canonical > 0
        and quality >= 60
        and revenue_growth > 0
        and any(value is not None and value > 0 for value in (owner_earnings, net_income))
    )


def _estimate_share_count(session: Session, report: CompanyReport) -> float | None:
    stats = report.key_stats or {}
    for key in (
        "shares_outstanding",
        "weighted_avg_diluted_shares",
        "weighted_avg_basic_shares",
    ):
        shares = _safe_float(stats.get(key))
        if shares is not None and shares > 0:
            return shares
    shares = _latest_fact_value(
        session,
        report.company_id,
        [
            "CommonStockSharesOutstanding",
            "EntityCommonStockSharesOutstanding",
            "WeightedAverageNumberOfDilutedSharesOutstanding",
            "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
            "WeightedAverageNumberOfSharesOutstandingBasic",
        ],
    )
    if shares is None or shares <= 0:
        return None
    return shares


def _estimate_cc_valuation(session: Session, report: CompanyReport) -> float | None:
    stats = report.key_stats or {}
    owner_earnings = _safe_float(stats.get("owner_earnings"))
    net_income = _safe_float(stats.get("net_income"))
    equity = _safe_float(stats.get("equity"))
    growth_pct = _safe_float(stats.get("revenue_growth_pct")) or 0.0
    quality = _safe_float(stats.get("accounting_quality_score")) or report.composite_score
    earnings_power = owner_earnings if owner_earnings and owner_earnings > 0 else net_income
    if earnings_power is None or earnings_power <= 0:
        if equity and equity > 0:
            earnings_power = equity * 0.08
        else:
            return None
    share_count = _estimate_share_count(session, report)
    if share_count is None or share_count <= 0:
        return None
    base_multiple = 8.0 + max(0.0, (quality - 50.0) / 10.0)
    growth_bonus = max(0.0, min(8.0, growth_pct / 18.0))
    stance_bonus = 1.5 if report.stance == "MOST_BULLISH" else 0.75
    equity_value = earnings_power * (base_multiple + growth_bonus + stance_bonus)
    return round(equity_value / share_count, 2)


def _estimate_growth_forecast(report: CompanyReport) -> float:
    stats = report.key_stats or {}
    growth_pct = _safe_float(stats.get("revenue_growth_pct")) or 0.0
    quality = _safe_float(stats.get("accounting_quality_score")) or report.composite_score
    forecast = (growth_pct * 0.18) + max(0.0, quality - 60.0) * 0.28
    return round(max(4.0, min(35.0, forecast)), 2)


def _latest_fact_value(session: Session, company_id, concepts: list[str]) -> float | None:
    fact = session.execute(
        select(RawFact)
        .where(RawFact.company_id == company_id, RawFact.concept.in_(concepts), RawFact.value_numeric.is_not(None))
        .order_by(RawFact.period_end.desc(), RawFact.filed_date.desc(), RawFact.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if fact is None or fact.value_numeric is None:
        return None
    return float(fact.value_numeric)


def _estimate_eps(session: Session, report: CompanyReport) -> float | None:
    stats = report.key_stats or {}
    for key in ("diluted_eps", "eps", "eps_diluted", "eps_basic"):
        eps = _safe_float(stats.get(key))
        if eps is not None:
            return round(eps, 2)

    direct_eps = _latest_fact_value(
        session,
        report.company_id,
        ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    )
    if direct_eps is not None:
        return round(direct_eps, 2)

    net_income = _safe_float(stats.get("net_income"))
    shares = _safe_float(stats.get("weighted_avg_diluted_shares")) or _safe_float(stats.get("weighted_avg_basic_shares"))
    if shares is None:
        shares = _latest_fact_value(
            session,
            report.company_id,
            [
                "WeightedAverageNumberOfDilutedSharesOutstanding",
                "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
                "WeightedAverageNumberOfSharesOutstandingBasic",
                "CommonStockSharesOutstanding",
            ],
        )
    if net_income is None or shares in (None, 0):
        return None
    return round(net_income / shares, 2)


def _estimate_eps_forecast(eps: float | None, growth_forecast_pct: float) -> float | None:
    if eps is None:
        return None
    return round(eps * (1 + (growth_forecast_pct / 100)), 2)


def _sector_from_description(sic_description: str | None) -> str:
    text = (sic_description or "").strip().lower()
    if not text:
        return "Unclassified"
    mapping = [
        ("Technology", ("software", "computer", "semiconductor", "electronic", "data processing", "communications equipment")),
        ("Healthcare", ("pharmaceutical", "biological", "medical", "health", "surgical", "hospital")),
        ("Financials", ("bank", "finance", "financial", "insurance", "title", "asset management", "investment")),
        ("Industrials", ("industrial", "transportation", "machinery", "aerospace", "aircraft", "manufacturing")),
        ("Consumer", ("retail", "food", "restaurant", "apparel", "beverage", "consumer", "catalog")),
        ("Energy", ("oil", "gas", "petroleum", "energy", "pipeline", "drilling")),
        ("Real Estate", ("reit", "real estate", "homes", "property", "realty")),
        ("Materials", ("chemical", "mining", "steel", "paper", "forest", "materials")),
        ("Utilities", ("utility", "electric", "water", "telecommunications")),
        ("Communication Services", ("media", "broadcast", "internet", "publishing", "entertainment")),
    ]
    for sector, keywords in mapping:
        if any(keyword in text for keyword in keywords):
            return sector
    return (sic_description or "Unclassified")[:48]


def _sector_label(report: CompanyReport) -> str:
    company = getattr(report, "company", None)
    return _sector_from_description(getattr(company, "sic_description", None))


def _designation_profile(report: CompanyReport) -> str:
    stats = report.key_stats or {}
    return str(stats.get("designation_profile") or "Developing Coverage")


def _forecast_pack(report: CompanyReport, *, eps: float | None, eps_forecast: float | None) -> dict[str, float | str | None]:
    stats = report.key_stats or {}
    return {
        "designation_profile": _designation_profile(report),
        "forecast_confidence_pct": _safe_float(stats.get("forecast_confidence_pct")),
        "revenue_forecast_next_quarter_pct": _safe_float(stats.get("revenue_forecast_next_quarter_pct")),
        "revenue_forecast_next_year_pct": _safe_float(stats.get("revenue_forecast_next_year_pct")),
        "margin_forecast_pct": _safe_float(stats.get("margin_forecast_pct")),
        "owner_earnings_forecast": _safe_float(stats.get("owner_earnings_forecast")),
        "dilution_growth_pct": _safe_float(stats.get("dilution_growth_pct")),
        "eps": eps,
        "eps_forecast": eps_forecast,
        "surprise_score": _safe_float(stats.get("surprise_score")),
        "surprise_upside_pct": _safe_float(stats.get("surprise_upside_pct")),
        "scenario_bear_value": _safe_float(stats.get("scenario_bear_value")),
        "scenario_base_value": _safe_float(stats.get("scenario_base_value")),
        "scenario_bull_value": _safe_float(stats.get("scenario_bull_value")),
    }


def _build_why_buy(report: CompanyReport) -> list[str]:
    stats = report.key_stats or {}
    reasons: list[str] = []
    growth = _safe_float(stats.get("revenue_growth_pct"))
    owner_earnings = _safe_float(stats.get("owner_earnings"))
    quality = _safe_float(stats.get("accounting_quality_score"))
    canonical = int(stats.get("canonical_facts_count") or 0)
    if growth is not None:
        reasons.append(f"Revenue growth screens at {growth:.1f}% on the latest accountant pass.")
    if owner_earnings is not None:
        reasons.append(f"Owner earnings proxy remains positive at ${owner_earnings:,.0f}.")
    if quality is not None:
        reasons.append(f"Accounting quality score holds at {quality:.1f}.")
    reasons.append(f"Canonical coverage now includes {canonical:,} mapped facts for comparability.")
    return reasons[:4]


def _build_synopsis(report: CompanyReport) -> str:
    stats = report.key_stats or {}
    canonical = int(stats.get("canonical_facts_count") or 0)
    growth = _safe_float(stats.get("revenue_growth_pct"))
    owner_earnings = _safe_float(stats.get("owner_earnings"))
    owner_text = "N/A" if owner_earnings is None else f"${owner_earnings:,.0f}"
    growth_text = "N/A" if growth is None else f"{growth:.1f}%"
    return (
        f"{report.company_name} qualifies as a buy-board trade candidate because the accountant model "
        f"flags {report.stance.lower()} quality with {canonical:,} canonical facts, revenue growth at "
        f"{growth_text}, and owner earnings at {owner_text}."
    )


def _build_future_synopsis(report: CompanyReport) -> str:
    stats = report.key_stats or {}
    surprise = _safe_float(stats.get("surprise_score"))
    rev_fcst = _safe_float(stats.get("revenue_forecast_next_year_pct"))
    confidence = _safe_float(stats.get("forecast_confidence_pct"))
    surprise_text = "N/A" if surprise is None else f"{surprise:.1f}"
    rev_text = "N/A" if rev_fcst is None else f"{rev_fcst:.1f}%"
    confidence_text = "N/A" if confidence is None else f"{confidence:.1f}%"
    return (
        f"{report.company_name} screens as a future upside candidate with surprise score "
        f"{surprise_text}, next-year revenue forecast {rev_text}, and forecast confidence "
        f"{confidence_text}."
    )


def _build_accounting_basis(
    report: CompanyReport,
    *,
    eps: float | None,
    eps_forecast: float | None,
) -> dict[str, float | int | str | None]:
    stats = report.key_stats or {}
    forecast_pack = _forecast_pack(report, eps=eps, eps_forecast=eps_forecast)
    return {
        "stance": report.stance,
        "sector": _sector_label(report),
        "composite_score": report.composite_score,
        "bullish_score": report.bullish_score,
        "data_quality_tier": report.data_quality_tier,
        "filings_count": stats.get("filings_count"),
        "raw_facts_count": stats.get("raw_facts_count"),
        "canonical_facts_count": stats.get("canonical_facts_count"),
        "revenue_growth_pct": stats.get("revenue_growth_pct"),
        "owner_earnings": stats.get("owner_earnings"),
        "net_income": stats.get("net_income"),
        "equity": stats.get("equity"),
        "eps": eps,
        "eps_forecast": eps_forecast,
        "designation_profile": forecast_pack.get("designation_profile"),
        "forecast_confidence_pct": forecast_pack.get("forecast_confidence_pct"),
        "revenue_forecast_next_quarter_pct": forecast_pack.get("revenue_forecast_next_quarter_pct"),
        "revenue_forecast_next_year_pct": forecast_pack.get("revenue_forecast_next_year_pct"),
        "margin_forecast_pct": forecast_pack.get("margin_forecast_pct"),
        "owner_earnings_forecast": forecast_pack.get("owner_earnings_forecast"),
        "dilution_growth_pct": forecast_pack.get("dilution_growth_pct"),
        "surprise_score": forecast_pack.get("surprise_score"),
        "surprise_upside_pct": forecast_pack.get("surprise_upside_pct"),
        "scenario_bear_value": forecast_pack.get("scenario_bear_value"),
        "scenario_base_value": forecast_pack.get("scenario_base_value"),
        "scenario_bull_value": forecast_pack.get("scenario_bull_value"),
        "accounting_quality_score": stats.get("accounting_quality_score"),
    }


def _build_battle_card(report: CompanyReport, valuation: float | None, forecast_growth_pct: float) -> dict[str, object]:
    stats = report.key_stats or {}
    canonical = int(stats.get("canonical_facts_count") or 0)
    forecast_pack = _forecast_pack(report, eps=None, eps_forecast=None)
    return {
        "headline": f"{report.ticker} promoted to BUY BOARD",
        "synopsis": _build_synopsis(report),
        "valuation_framework": "CC_EARNINGS_POWER",
        "designation_profile": _designation_profile(report),
        "forecast_pack": forecast_pack,
        "why_buy": _build_why_buy(report),
        "bull_case": [
            f"Composite score {report.composite_score:.1f} with stance {report.stance}.",
            f"Canonical fact base at {canonical:,} mapped items allows cleaner cross-company comparisons.",
            f"CC valuation prints at ${valuation:,.0f} with {forecast_growth_pct:.1f}% internal growth forecast." if valuation else f"Growth forecast prints at {forecast_growth_pct:.1f}% pending valuation fill.",
        ],
        "risk_flags": [
            report.highlights[1] if len(report.highlights) > 1 else "Data quality should still be monitored on each refresh.",
            report.highlights[2] if len(report.highlights) > 2 else "Price and valuation gaps can compress even with solid accounting signals.",
        ],
        "accounting_triggers": {
            "revenue_growth_pct": stats.get("revenue_growth_pct"),
            "owner_earnings": stats.get("owner_earnings"),
            "accounting_quality_score": stats.get("accounting_quality_score"),
            "canonical_facts_count": stats.get("canonical_facts_count"),
        },
        "scenario_matrix": {
            "bear": stats.get("scenario_bear_value"),
            "base": stats.get("scenario_base_value"),
            "bull": stats.get("scenario_bull_value"),
        },
    }


def sync_buy_board_candidate(session: Session, report: CompanyReport) -> BuyBoardCandidate | None:
    candidate = session.execute(
        select(BuyBoardCandidate).where(BuyBoardCandidate.company_id == report.company_id)
    ).scalar_one_or_none()
    now = _now_utc()
    eps = _estimate_eps(session, report)
    growth_forecast_pct = _estimate_growth_forecast(report)
    eps_forecast = _estimate_eps_forecast(eps, growth_forecast_pct)
    if not _qualifies_for_buy_board(report):
        if candidate:
            candidate.status = "MONITOR"
            candidate.company_name = report.company_name
            candidate.ticker = report.ticker
            candidate.source_report_date = report.as_of_date
            candidate.source_report_score = report.composite_score
            candidate.current_cc_valuation = _estimate_cc_valuation(session, report)
            candidate.current_valuation_at = now
            candidate.cc_valuation_growth_forecast_pct = growth_forecast_pct
            candidate.synopsis = _build_synopsis(report)
            candidate.why_buy = _build_why_buy(report)
            candidate.accounting_basis = _build_accounting_basis(report, eps=eps, eps_forecast=eps_forecast)
            candidate.battle_card = _build_battle_card(
                report,
                candidate.current_cc_valuation,
                candidate.cc_valuation_growth_forecast_pct or 0.0,
            )
        return candidate

    valuation = _estimate_cc_valuation(session, report)
    forecast_growth_pct = growth_forecast_pct
    if candidate is None:
        candidate = BuyBoardCandidate(
            company_id=report.company_id,
            ticker=report.ticker,
            company_name=report.company_name,
            status="ACTIVE",
            first_qualified_at=now,
        )
        session.add(candidate)
    candidate.status = "ACTIVE"
    candidate.ticker = report.ticker
    candidate.company_name = report.company_name
    candidate.source_report_date = report.as_of_date
    candidate.source_report_score = report.composite_score
    candidate.last_qualified_at = now
    candidate.current_cc_valuation = valuation
    candidate.current_valuation_at = now
    candidate.cc_valuation_growth_forecast_pct = forecast_growth_pct
    candidate.synopsis = _build_synopsis(report)
    candidate.why_buy = _build_why_buy(report)
    candidate.accounting_basis = _build_accounting_basis(report, eps=eps, eps_forecast=eps_forecast)
    candidate.battle_card = _build_battle_card(report, valuation, forecast_growth_pct)
    if candidate.first_cc_valuation is None and valuation is not None:
        candidate.first_cc_valuation = valuation
        candidate.first_valuation_at = now
    return candidate


def refresh_buy_board_prices(session: Session, *, refresh_reason: str = "manual") -> dict[str, int | str]:
    candidates = session.execute(
        select(BuyBoardCandidate)
        .where(BuyBoardCandidate.status == "ACTIVE")
        .order_by(BuyBoardCandidate.ticker.asc())
    ).scalars().all()
    updated = 0
    successes = 0
    now = _now_utc()
    session_label = _session_label(now.astimezone(_ET))
    fatal_reason: str | None = None
    for candidate in candidates:
        if fatal_reason:
            candidate.last_price_error = fatal_reason
            candidate.last_price_refresh_at = now
            continue
        payload = alpaca_quote(candidate.ticker)
        checked_at = payload.get("checked_at")
        checked_dt = datetime.fromisoformat(checked_at) if isinstance(checked_at, str) else now
        if not payload.get("ok"):
            failure_reason = str(payload.get("reason") or "Alpaca quote failed")[:500]
            candidate.last_price_error = failure_reason
            candidate.last_price_refresh_at = checked_dt
            if "rejected by the data api" in failure_reason.lower():
                fatal_reason = failure_reason
            continue
        quote_payload = payload.get("quote")
        price = _pick_price(quote_payload if isinstance(quote_payload, dict) else None)
        if price is None:
            candidate.last_price_error = "Alpaca returned no usable price"
            candidate.last_price_refresh_at = checked_dt
            continue
        if candidate.first_price is None:
            candidate.first_price = price
            candidate.first_price_at = checked_dt
        candidate.current_price = price
        candidate.current_price_at = checked_dt
        candidate.last_price_refresh_at = checked_dt
        candidate.last_price_source = "ALPACA"
        candidate.current_market_data_quality = str(payload.get("data_quality") or "unknown")
        candidate.last_price_error = None
        session.add(
            BuyBoardSnapshot(
                candidate_id=candidate.id,
                session_label=session_label,
                refresh_reason=refresh_reason,
                price=price,
                cc_valuation=candidate.current_cc_valuation,
                upside_pct=_upside_pct(candidate.current_cc_valuation, price),
                data_quality=candidate.current_market_data_quality,
                source="ALPACA",
                captured_at=checked_dt,
            )
        )
        updated += 1
        successes += 1
    return {
        "candidate_count": len(candidates),
        "updated": updated,
        "successes": successes,
        "session_label": session_label,
    }


def backfill_buy_board_candidates(session: Session) -> dict[str, int]:
    reports = session.execute(select(CompanyReport).order_by(CompanyReport.updated_at.desc())).scalars().all()
    active = 0
    monitor = 0
    for report in reports:
        candidate = sync_buy_board_candidate(session, report)
        if candidate is None:
            continue
        if candidate.status == "ACTIVE":
            active += 1
        else:
            monitor += 1
    return {
        "reports_examined": len(reports),
        "active_candidates": active,
        "monitor_candidates": monitor,
    }


def future_upside_candidates(session: Session, limit: int = 24) -> list[dict[str, object]]:
    reports = session.execute(
        select(CompanyReport)
        .where(CompanyReport.composite_score >= 60)
        .order_by(CompanyReport.composite_score.desc(), CompanyReport.updated_at.desc())
    ).scalars().all()
    ranked: list[dict[str, object]] = []
    for report in reports:
        stats = report.key_stats or {}
        if stats.get("future_bucket") != "FUTURE":
            continue
        surprise = _safe_float(stats.get("surprise_score"))
        confidence = _safe_float(stats.get("forecast_confidence_pct"))
        rev_next_year = _safe_float(stats.get("revenue_forecast_next_year_pct"))
        if surprise is None or confidence is None or rev_next_year is None:
            continue
        eps = _safe_float(stats.get("eps"))
        eps_forecast = _safe_float(stats.get("eps_forecast"))
        valuation = _estimate_cc_valuation(session, report)
        candidate = session.execute(
            select(BuyBoardCandidate).where(BuyBoardCandidate.company_id == report.company_id)
        ).scalar_one_or_none()
        current_price = None
        if candidate is not None:
            current_price = _best_price(_safe_float(candidate.current_price), _safe_float(candidate.first_price))
            if valuation is None:
                valuation = _best_price(_safe_float(candidate.current_cc_valuation), _safe_float(candidate.first_cc_valuation))
        if current_price is None:
            current_price = _safe_float(report.current_price)
        forecast_growth_pct = _estimate_growth_forecast(report)
        accounting_basis = _build_accounting_basis(report, eps=eps, eps_forecast=eps_forecast)
        battle_card = _build_battle_card(report, valuation, forecast_growth_pct)
        why_buy = _build_why_buy(report)
        ranked.append(
            {
                "ticker": report.ticker,
                "company_name": report.company_name,
                "sector": accounting_basis.get("sector"),
                "stance": report.stance,
                "composite_score": report.composite_score,
                "source_report_date": report.as_of_date,
                "source_report_score": report.composite_score,
                "current_price": current_price,
                "current_cc_valuation": valuation,
                "cc_valuation_growth_forecast_pct": forecast_growth_pct,
                "upside_pct": _upside_pct(valuation, current_price),
                "synopsis": _build_future_synopsis(report),
                "designation_profile": accounting_basis.get("designation_profile"),
                "forecast_confidence_pct": confidence,
                "surprise_score": surprise,
                "surprise_upside_pct": _safe_float(stats.get("surprise_upside_pct")),
                "revenue_forecast_next_quarter_pct": _safe_float(stats.get("revenue_forecast_next_quarter_pct")),
                "revenue_forecast_next_year_pct": rev_next_year,
                "margin_forecast_pct": _safe_float(stats.get("margin_forecast_pct")),
                "owner_earnings_forecast": _safe_float(stats.get("owner_earnings_forecast")),
                "eps": eps,
                "eps_forecast": eps_forecast,
                "scenario_bear_value": _safe_float(stats.get("scenario_bear_value")),
                "scenario_base_value": _safe_float(stats.get("scenario_base_value")),
                "scenario_bull_value": _safe_float(stats.get("scenario_bull_value")),
                "why_buy": why_buy,
                "accounting_basis": accounting_basis,
                "battle_card": battle_card,
            }
        )
    ranked.sort(
        key=lambda item: (
            float(item.get("surprise_score") or 0),
            float(item.get("forecast_confidence_pct") or 0),
            float(item.get("composite_score") or 0),
        ),
        reverse=True,
    )
    return ranked[:limit]


def _active_candidate_count(session: Session) -> int:
    return int(
        session.execute(
            select(func.count()).select_from(BuyBoardCandidate).where(BuyBoardCandidate.status == "ACTIVE")
        ).scalar_one()
    )


def _session_label(now_et: datetime) -> str:
    current = now_et.timetz().replace(tzinfo=None)
    if current < time(12, 0):
        return "OPEN_0930"
    if current < time(16, 0):
        return "MIDDAY"
    return "CLOSE_1600"


def _upside_pct(valuation: float | None, price: float | None) -> float | None:
    if valuation is None or price in (None, 0):
        return None
    return round(((valuation - price) / price) * 100, 2)


def _best_price(*prices: float | None) -> float | None:
    for price in prices:
        if price not in (None, 0):
            return price
    return None


class BuyBoardScheduler:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._snapshot = BuyBoardSnapshotState()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._snapshot.running = True
            self._snapshot.started_at = _now_utc().isoformat()
            self._thread = threading.Thread(target=self._run, daemon=True, name="accountant-buy-board")
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self._snapshot.running = False

    def run_once(self) -> dict[str, object]:
        summary = self._refresh("manual")
        snapshot = self.snapshot()
        snapshot["manual_refresh"] = summary
        return snapshot

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            running = bool(self._thread and self._thread.is_alive() and not self._stop.is_set())
            self._snapshot.running = running
            return {
                "running": running,
                "started_at": self._snapshot.started_at,
                "next_refresh_at": self._snapshot.next_refresh_at,
                "last_refresh_at": self._snapshot.last_refresh_at,
                "last_action": self._snapshot.last_action,
                "last_error": self._snapshot.last_error,
                "candidate_count": self._snapshot.candidate_count,
                "last_refresh_count": self._snapshot.last_refresh_count,
                "last_success_count": self._snapshot.last_success_count,
            }

    def _run(self) -> None:
        try:
            self._prime_snapshot()
            while not self._stop.is_set():
                now_et = datetime.now(_ET)
                target = _next_refresh_time(now_et)
                with self._lock:
                    self._snapshot.next_refresh_at = target.astimezone(UTC).isoformat()
                timeout = max(1.0, (target - now_et).total_seconds())
                if self._stop.wait(timeout=timeout):
                    break
                label = "scheduled_open" if target.timetz().replace(tzinfo=None) == time(9, 30) else "scheduled_close"
                self._refresh(label)
        finally:
            with self._lock:
                self._snapshot.running = False

    def _prime_snapshot(self) -> None:
        engine = create_db_engine()
        factory = create_session_factory(engine)
        session = factory()
        try:
            with self._lock:
                self._snapshot.candidate_count = _active_candidate_count(session)
                self._snapshot.last_action = "awaiting scheduled price refresh"
                self._snapshot.last_error = None
        except Exception as exc:
            error_text = str(exc)[:500]
            log.warning("buy_board.snapshot_prime_failed", error=error_text)
            with self._lock:
                self._snapshot.last_error = error_text
                self._snapshot.last_action = "buy board snapshot prime failed"
        finally:
            session.close()
            engine.dispose()

    def _refresh(self, refresh_reason: str) -> dict[str, int | str]:
        engine = create_db_engine()
        factory = create_session_factory(engine)
        session = factory()
        try:
            with sqlite_write_guard(timeout_seconds=2.0):
                summary = refresh_buy_board_prices(session, refresh_reason=refresh_reason)
                session.commit()
            with self._lock:
                self._snapshot.last_refresh_at = _now_utc().isoformat()
                self._snapshot.last_action = f"refreshed buy board ({summary['updated']} quotes)"
                self._snapshot.last_error = None
                self._snapshot.candidate_count = int(summary["candidate_count"])
                self._snapshot.last_refresh_count = int(summary["updated"])
                self._snapshot.last_success_count = int(summary["successes"])
            return summary
        except Exception as exc:
            session.rollback()
            error_text = str(exc)[:500]
            log.warning("buy_board.refresh_failed", error=error_text, reason=refresh_reason)
            with self._lock:
                self._snapshot.last_error = error_text
                self._snapshot.last_action = f"refresh failed ({refresh_reason})"
            return {"candidate_count": 0, "updated": 0, "successes": 0, "session_label": "FAILED"}
        finally:
            session.close()
            engine.dispose()


def _next_refresh_time(now_et: datetime) -> datetime:
    today = now_et.date()
    open_refresh = datetime.combine(today, time(9, 30), tzinfo=_ET)
    close_refresh = datetime.combine(today, time(16, 0), tzinfo=_ET)
    if now_et < open_refresh:
        return open_refresh
    if now_et < close_refresh:
        return close_refresh
    tomorrow = today + timedelta(days=1)
    return datetime.combine(tomorrow, time(9, 30), tzinfo=_ET)


BUY_BOARD = BuyBoardScheduler()
