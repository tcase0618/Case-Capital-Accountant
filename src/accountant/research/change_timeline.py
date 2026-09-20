"""Deterministic per-company report-card change timeline.

The timeline reads immutable report cards only.  It never reconstructs a past
valuation from current data: legacy cards without a captured valuation snapshot
remain explicitly unavailable.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from accountant.db.models import ReportCard

_MATERIAL_EVENT_FORMS = {"8-K", "8-K/A", "NT 10-K", "NT 10-Q", "UPLOAD", "CORRESP"}
_CORE_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A", "6-K"}
_EVENT_FLAGS = (
    ("going_concern_flag", "Going-concern disclosure was added."),
    ("material_weakness_flag", "A material weakness was disclosed."),
    ("auditor_changed_flag", "An auditor-change signal was recorded."),
    ("late_filer_flag", "A late-filer signal was recorded."),
    ("sec_comment_letter_flag", "An SEC comment-letter signal was recorded."),
    ("cfo_turnover_flag", "A CFO-turnover signal was recorded."),
    ("ceo_turnover_flag", "A CEO-turnover signal was recorded."),
)


def build_company_change_timeline(cards: Iterable[ReportCard], *, limit: int = 80) -> dict[str, object] | None:
    """Return material, auditable report-card changes in chronological order."""
    ordered = sorted(cards, key=_card_time)
    if not ordered:
        return None

    events: list[dict[str, object]] = []
    prior: ReportCard | None = None
    for card in ordered:
        event = _build_event(card, prior)
        if event is not None:
            events.append(event)
        prior = card

    newest = ordered[-1]
    return {
        "ticker": newest.ticker,
        "company_name": newest.company_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "model_version": "REPORT_CHANGE_TIMELINE_V1",
        "events": list(reversed(events[-limit:])),
    }


def _build_event(card: ReportCard, prior: ReportCard | None) -> dict[str, object] | None:
    current = _snapshot(card)
    previous = _snapshot(prior) if prior is not None else None
    reasons = _change_reasons(current, previous)
    form = card.filing_type.upper()
    material_form = form in _MATERIAL_EVENT_FORMS
    core_form = form in _CORE_FORMS
    score_changed = previous is not None and _meaningful_change(current["score"], previous["score"], threshold=3.0)
    valuation_changed = previous is not None and _meaningful_change(
        current["valuation"], previous["valuation"], threshold_pct=5.0
    )
    action_changed = previous is not None and current["action"] != previous["action"]
    grade_changed = previous is not None and current["grade"] != previous["grade"]

    if prior is not None and not any((material_form, core_form, score_changed, valuation_changed, action_changed, grade_changed)):
        return None

    event_kind = "BASELINE" if prior is None else "FILING_UPDATE"
    if material_form:
        event_kind = "MATERIAL_EVENT"
    elif action_changed or grade_changed or score_changed or valuation_changed:
        event_kind = "RESEARCH_REVALUATION"

    title = "Baseline report-card snapshot" if prior is None else f"{form} report update"
    if event_kind == "MATERIAL_EVENT":
        title = f"{form} material filing event"
    elif event_kind == "RESEARCH_REVALUATION":
        title = f"{form} revaluation and grade update"
    summary = "Baseline filing snapshot captured for future comparisons." if prior is None else _summary(reasons)

    return {
        "event_id": card.report_card_id,
        "occurred_at": _card_time(card).isoformat(),
        "filing_type": card.filing_type,
        "filing_date": card.filed_date.isoformat(),
        "accepted_at": card.accepted_at.isoformat() if card.accepted_at else None,
        "accession_number": card.accession_number,
        "source_url": card.source_url,
        "event_kind": event_kind,
        "title": title,
        "summary": summary,
        "old_valuation": previous["valuation"] if previous else None,
        "new_valuation": current["valuation"],
        "valuation_change_pct": _change_pct(previous["valuation"], current["valuation"]) if previous else None,
        "old_price": previous["price"] if previous else None,
        "new_price": current["price"],
        "price_change_pct": _change_pct(previous["price"], current["price"]) if previous else None,
        "old_score": previous["score"] if previous else None,
        "new_score": current["score"],
        "old_action": previous["action"] if previous else None,
        "new_action": current["action"],
        "old_grade": previous["grade"] if previous else None,
        "new_grade": current["grade"],
        "valuation_status": current["valuation_status"],
        "reasons": reasons,
    }


def _snapshot(card: ReportCard | None) -> dict[str, object]:
    if card is None:
        return {}
    verdict = _mapping(card.final_verdict)
    market = _mapping(card.market_data_linkage)
    valuation_snapshot = _mapping(verdict.get("valuation_snapshot"))
    valuation = _number(valuation_snapshot.get("cc_valuation"))
    return {
        "score": _number(verdict.get("grade_score")) or _number(verdict.get("composite_score")),
        "action": _text(verdict.get("current_action")),
        "grade": _text(verdict.get("grade")),
        "valuation": valuation,
        "valuation_status": "captured" if valuation is not None else "not_recorded_before_timeline_v1",
        "price": _number(valuation_snapshot.get("market_price")) or _number(market.get("price_asof")),
        "financials": _mapping(card.standardized_financials),
        "growth": _mapping(card.growth_trend_deltas),
        "cash_quality": _mapping(card.accrual_cash_quality),
        "flags": _mapping(card.event_red_flags),
    }


def _change_reasons(current: dict[str, object], previous: dict[str, object] | None) -> list[str]:
    if previous is None:
        return ["Initial immutable report-card snapshot."]
    reasons: list[str] = []
    if current["action"] != previous["action"]:
        reasons.append(f"Action changed from {previous['action'] or 'UNSET'} to {current['action'] or 'UNSET'}.")
    if current["grade"] != previous["grade"]:
        reasons.append(f"Grade changed from {previous['grade'] or 'UNSET'} to {current['grade'] or 'UNSET'}.")
    score_delta = _delta(previous["score"], current["score"])
    if score_delta is not None and abs(score_delta) >= 0.1:
        reasons.append(f"Report score moved {score_delta:+.1f} points.")
    valuation_delta = _change_pct(previous["valuation"], current["valuation"])
    if valuation_delta is not None:
        reasons.append(f"CC valuation moved {valuation_delta:+.1f}% from the prior captured snapshot.")

    _append_metric_change(reasons, "Revenue growth", previous["growth"], current["growth"], "revenue_yoy_growth", suffix="%")
    _append_metric_change(reasons, "Gross margin", previous["growth"], current["growth"], "gross_margin", suffix="%")
    _append_metric_change(reasons, "Cash conversion", previous["cash_quality"], current["cash_quality"], "cash_conversion_ratio")
    _append_metric_change(reasons, "FCF / net income", previous["cash_quality"], current["cash_quality"], "fcf_ni_ratio")
    _append_metric_change(reasons, "Long-term debt", previous["financials"], current["financials"], "lt_debt", percent=True)
    _append_metric_change(reasons, "Diluted shares", previous["growth"], current["growth"], "diluted_shares_yoy_change", suffix="%")
    previous_flags = _mapping(previous["flags"])
    current_flags = _mapping(current["flags"])
    for key, message in _EVENT_FLAGS:
        if bool(current_flags.get(key)) and not bool(previous_flags.get(key)):
            reasons.append(message)
    return reasons or ["A new SEC filing was incorporated; no material deterministic score delta was recorded."]


def _append_metric_change(
    reasons: list[str], label: str, old: object, new: object, key: str, *, suffix: str = "", percent: bool = False
) -> None:
    old_value = _number(_mapping(old).get(key))
    new_value = _number(_mapping(new).get(key))
    if old_value is None or new_value is None:
        return
    change = _change_pct(old_value, new_value) if percent else new_value - old_value
    if change is None or abs(change) < 0.01:
        return
    unit = "%" if percent else suffix
    reasons.append(f"{label} changed {change:+.1f}{unit} versus the prior report-card snapshot.")


def _summary(reasons: list[str]) -> str:
    return " ".join(reasons[:2]) if reasons else "New filing incorporated without a material deterministic change."


def _card_time(card: ReportCard) -> datetime:
    value = card.accepted_at or card.created_at
    if value is not None:
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.combine(card.filed_date, datetime.min.time(), tzinfo=UTC)


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _number(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _delta(old: object, new: object) -> float | None:
    old_value, new_value = _number(old), _number(new)
    return new_value - old_value if old_value is not None and new_value is not None else None


def _change_pct(old: object, new: object) -> float | None:
    old_value, new_value = _number(old), _number(new)
    if old_value in (None, 0) or new_value is None:
        return None
    return ((new_value - old_value) / abs(old_value)) * 100


def _meaningful_change(old: object, new: object, *, threshold: float = 0.0, threshold_pct: float | None = None) -> bool:
    if threshold_pct is not None:
        change = _change_pct(old, new)
        return change is not None and abs(change) >= threshold_pct
    change = _delta(old, new)
    return change is not None and abs(change) >= threshold
