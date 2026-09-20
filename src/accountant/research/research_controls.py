"""CFO/Investment Committee controls for deterministic research outputs."""

from __future__ import annotations

from typing import Any


def build_research_controls(
    *,
    data_completeness_pct: float | None,
    canonical_facts_count: int,
    route_family: str,
    lane1_supported: bool,
    veto_triggered: bool,
    grade_score: float | None,
    valuation_available: bool,
) -> dict[str, object]:
    completeness = float(data_completeness_pct or 0.0)
    checks = {
        "score_lineage_present": True,
        "canonical_facts_present": canonical_facts_count > 0,
        "data_completeness_gate": completeness >= 60.0,
        "hard_veto_clear": not veto_triggered,
        "valuation_snapshot_present": valuation_available,
        "route_family_assigned": bool(route_family),
    }
    hard_vetoes = []
    if veto_triggered:
        hard_vetoes.append("report-card veto triggered")
    if canonical_facts_count <= 0:
        hard_vetoes.append("no canonical facts")
    if completeness < 60.0:
        hard_vetoes.append("data completeness below 60%")
    qa_failures = [name for name, passed in checks.items() if not passed and name != "valuation_snapshot_present"]
    qa_status = "PASS" if not qa_failures else "FAIL"
    approval_state = "RESEARCH_APPROVED" if qa_status == "PASS" and not veto_triggered else "REVIEW_REQUIRED"
    if not valuation_available and approval_state == "RESEARCH_APPROVED":
        approval_state = "RESEARCH_APPROVED_WITHOUT_VALUATION"
    return {
        "version": "RESEARCH_CONTROL_PLANE_V1",
        "approval_state": approval_state,
        "qa_status": qa_status,
        "hard_vetoes": hard_vetoes,
        "qa_checks": checks,
        "qa_failures": qa_failures,
        "route_family": route_family,
        "lane1_supported": lane1_supported,
        "grade_score": grade_score,
        "execution_authority": "NONE",
        "review_note": "Research approval is not execution approval; the Trading Terminal owns execution controls.",
    }


def build_valuation_range(
    *,
    scenario_values: dict[str, Any],
    cc_valuation: float | None,
    confidence_pct: float | None,
) -> dict[str, object]:
    values = {
        "bear": _number(scenario_values.get("bear")),
        "base": _number(scenario_values.get("base")),
        "bull": _number(scenario_values.get("bull")),
    }
    if all(value is None for value in values.values()) and cc_valuation is not None:
        values = {"bear": None, "base": cc_valuation, "bull": None}
    present = [value for value in values.values() if value is not None]
    return {
        **values,
        "low": min(present) if present else None,
        "high": max(present) if present else None,
        "confidence_pct": confidence_pct,
        "status": "captured" if present else "unavailable",
        "model_version": "CC_SCENARIO_RANGE_V1",
    }


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
