"""Versioned, fail-closed publication contract; transport success is not QA."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import Any

from accountant.ops.edgar_calendar import edgar_business_days_since

PACKET_VERSION = "ACCOUNTANT_RESEARCH_PACKET_V2"
VALIDATION_VERSION = "FINANCIAL_QA_V1"
REQUIRED_QA_CHECKS = (
    "source_identity",
    "period_alignment",
    "units_and_dimensions",
    "share_basis",
    "score_reconciliation",
    "archive_rebuildability",
    "disclosure_evidence",
)


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def _object(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def evaluate_packet_acceptance(
    *,
    ticker: str,
    report: Any,
    card: Any,
    mode: dict,
    source: dict,
    storage_blocked: bool,
    now: datetime | None = None,
) -> dict:
    """Only independently validated, current evidence may cross the handoff."""
    now = now or datetime.now(UTC)
    reasons: list[str] = []
    mode = _object(mode)
    source = _object(source)
    sec = _object(source.get("sec"))
    source_as_of = sec.get("latest_filing_date")
    report_as_of = report.as_of_date if report is not None else None
    if storage_blocked:
        reasons.append("pipeline_storage_blocked")
    if mode.get("terminal_handoff_allowed") is not True:
        reasons.append("terminal_handoff_disallowed")
    if mode.get("execution_allowed") is not False or mode.get("research_only") is not True:
        reasons.append("invalid_authority")
    if source.get("source_grade") not in {"STRONG", "WATCH"}:
        reasons.append("source_integrity_not_acceptable")
    try:
        if not isinstance(source_as_of, str):
            raise ValueError("missing source date")
        source_date = date.fromisoformat(source_as_of)
        age = edgar_business_days_since(source_date, as_of=now.date())
        if source_date > now.date():
            reasons.append("source_date_in_future")
        if age > 3:
            reasons.append("source_stale")
    except (ValueError, TypeError):
        reasons.append("source_date_invalid")
    if report is None or card is None:
        reasons.append("report_or_card_missing")
    else:
        if report.ticker != ticker or card.ticker != ticker or report.company_id != card.company_id:
            reasons.append("report_identity_mismatch")
        if report.pipeline_stage != "reports-ready":
            reasons.append("pipeline_incomplete")
        if report.data_quality_tier not in {"ADEQUATE", "STRONG", "COMPLETE"}:
            reasons.append("data_quality_insufficient")
        updated = _timestamp(report.updated_at.isoformat() if report.updated_at else None)
        if updated is None or not 0 <= (now - updated).total_seconds() <= 7 * 86400:
            reasons.append("report_timestamp_invalid_or_stale")
        try:
            report_date = date.fromisoformat(report.as_of_date)
            if not 0 <= (now.date() - report_date).days <= 7:
                reasons.append("report_asof_invalid_or_stale")
        except (TypeError, ValueError):
            reasons.append("report_asof_invalid_or_stale")
        verdict = _object(card.final_verdict)
        validation = _object(verdict.get("calculation_validation"))
        checks = _object(validation.get("checks"))
        if (
            validation.get("version") != VALIDATION_VERSION
            or validation.get("status") != "PASS"
            or not validation.get("input_fingerprint")
            or any(checks.get(check) is not True for check in REQUIRED_QA_CHECKS)
        ):
            reasons.append("financial_qa_unverified")
        scored = _timestamp(verdict.get("last_scored_ts"))
        if scored is None or not 0 <= (now - scored).total_seconds() <= 7 * 86400:
            reasons.append("calculation_timestamp_invalid_or_stale")
        score = verdict.get("grade_score")
        try:
            if not isinstance(score, (int, float, str)) or isinstance(score, bool):
                raise ValueError("missing numeric score")
            card_score = float(score)
            report_score = float(report.composite_score)
            if (
                not math.isfinite(card_score) or not math.isfinite(report_score)
                or not 0 <= card_score <= 100 or not 0 <= report_score <= 100
                or abs(card_score - report_score) > 0.01
            ):
                reasons.append("score_disagreement")
        except (ValueError, TypeError, OverflowError):
            reasons.append("score_unavailable")
        accepted = _timestamp(card.accepted_at.isoformat() if card.accepted_at else None)
        if accepted is None:
            reasons.append("filing_acceptance_unverified")
        elif accepted > now:
            reasons.append("filing_acceptance_in_future")
    return {
        "version": "PACKET_ACCEPTANCE_V1",
        "accepted": not reasons,
        "status": "VALIDATED" if not reasons else "UNAVAILABLE" if report is None or card is None else "UNVALIDATED",
        "reasons": reasons,
        "source_as_of": source_as_of,
        "report_as_of": report_as_of,
    }
