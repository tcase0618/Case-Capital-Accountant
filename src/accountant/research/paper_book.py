from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from accountant.db.models import PaperBookPosition, ReportCard


@dataclass(frozen=True)
class PaperBookLaunchResult:
    book_name: str
    launch_date: date
    selected: int
    skipped_existing: int


def launch_lane1_paper_book(
    session: Session,
    *,
    launch_date: date,
    size: int = 20,
    book_name: str | None = None,
) -> PaperBookLaunchResult:
    resolved_book_name = book_name or f"lane1-paper-book-{launch_date.isoformat()}"
    rows = _latest_report_cards(session)
    eligible = [row for row in rows if _lane1_eligible(row)]
    eligible.sort(key=lambda row: _score(row), reverse=True)

    selected = 0
    skipped_existing = 0
    target_weight = round(1 / max(1, min(size, len(eligible))), 6) if eligible else 0.0
    for row in eligible[:size]:
        existing = session.execute(
            select(PaperBookPosition).where(
                PaperBookPosition.book_name == resolved_book_name,
                PaperBookPosition.ticker == row.ticker,
            )
        ).scalar_one_or_none()
        if existing is not None:
            skipped_existing += 1
            continue
        final_verdict = dict(row.final_verdict or {})
        market_data = dict(row.market_data_linkage or {})
        research_lane = _research_lane(final_verdict)
        thesis_snapshot = {
            "report_card_id": row.report_card_id,
            "grade": final_verdict.get("grade"),
            "grade_score": final_verdict.get("grade_score"),
            "current_action": final_verdict.get("current_action"),
            "veto_triggered": final_verdict.get("veto_triggered"),
            "veto_reason": final_verdict.get("veto_reason"),
            "confidence": final_verdict.get("confidence"),
            "route_family": final_verdict.get("route_family"),
            "route_reason": final_verdict.get("route_reason"),
            "data_completeness_pct": final_verdict.get("data_completeness_pct"),
            "research_score": _research_score(row),
            "selection_policy": "Lane 1 research evidence only; execution readiness remains in Trading Terminal.",
            "market_data_linkage": market_data,
            "positive_quality": dict(row.positive_quality or {}),
            "universe_tradability": dict(row.universe_tradability or {}),
        }
        session.add(
            PaperBookPosition(
                company_id=row.company_id,
                book_name=resolved_book_name,
                launch_date=launch_date,
                lane=research_lane,
                route_family=str(final_verdict.get("route_family") or "unknown"),
                route_reason=str(final_verdict.get("route_reason") or ""),
                ticker=row.ticker,
                company_name=row.company_name,
                report_card_id=row.report_card_id,
                entry_price=_safe_float(market_data.get("price_asof")),
                target_weight=target_weight,
                status="OPEN",
                thesis_snapshot=thesis_snapshot,
                notes="Pre-registered Lane 1 paper book launched from latest report cards.",
            )
        )
        selected += 1
    session.flush()
    return PaperBookLaunchResult(
        book_name=resolved_book_name,
        launch_date=launch_date,
        selected=selected,
        skipped_existing=skipped_existing,
    )


def _latest_report_cards(session: Session) -> list[ReportCard]:
    rows = session.execute(
        select(ReportCard).order_by(
            ReportCard.cik.asc(),
            ReportCard.accepted_at.desc(),
            ReportCard.filed_date.desc(),
            ReportCard.created_at.desc(),
        )
    ).scalars().all()
    latest: dict[str, ReportCard] = {}
    for row in rows:
        latest.setdefault(row.cik, row)
    return list(latest.values())


def _lane1_eligible(row: ReportCard) -> bool:
    verdict = dict(row.final_verdict or {})
    tradability = dict(row.universe_tradability or {})
    if not bool(verdict.get("lane1_supported")):
        return False
    if verdict.get("current_action") == "EXIT":
        return False
    if _catastrophic_veto(row):
        return False
    if any(
        bool(tradability.get(flag))
        for flag in ("excluded_financial_reit", "excluded_biotech_prerevenue", "excluded_recent_ipo")
    ):
        return False
    return _research_score(row) >= 75.0


def _score(row: ReportCard) -> float:
    return _research_score(row)


def _research_score(row: ReportCard) -> float:
    verdict = dict(row.final_verdict or {})
    positive_quality = dict(row.positive_quality or {})
    candidates = (
        _safe_float(verdict.get("grade_score")),
        _safe_float(positive_quality.get("positive_quality_score")),
        _safe_float(verdict.get("composite_score")),
        _safe_float(verdict.get("pqc")),
    )
    return max((value for value in candidates if value is not None), default=0.0)


def _catastrophic_veto(row: ReportCard) -> bool:
    verdict = dict(row.final_verdict or {})
    event_flags = dict(row.event_red_flags or {})
    if bool(event_flags.get("going_concern_flag")):
        return True
    if str(event_flags.get("restatement_severity") or "").lower() == "big-r":
        return True
    veto_reason = str(verdict.get("veto_reason") or "").lower()
    return any(
        phrase in veto_reason
        for phrase in (
            "going concern",
            "big-r",
            "sustained beneish",
            "unscheduled auditor change",
        )
    )


def _research_lane(verdict: dict[str, object]) -> str:
    action = str(verdict.get("current_action") or "WATCH").upper()
    if action == "BUY":
        return "RESEARCH_BUY"
    if action in {"HOLD", "WATCH"}:
        return "RESEARCH_WATCH"
    return "RESEARCH_REVIEW"


def _safe_float(value: object) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
