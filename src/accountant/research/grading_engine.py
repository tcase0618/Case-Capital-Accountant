from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GradingInputs:
    cash_oper_profitability_pctile: float | None
    capital_allocation_pctile: float | None
    margin_trajectory_pctile: float | None
    balance_sheet_strength_pctile: float | None
    accrual_quality_pctile: float | None
    beneish_severity: float | None
    dechow_severity: float | None
    altman_distress_severity: float | None
    event_flag_severity: float | None
    penalty_weight: float = 0.8
    forecasted_next_q_pqc: float | None = None
    current_pqc: float | None = None
    data_completeness_pct: float = 0.0
    forensic_score_dispersion: float = 0.0
    recency_factor: float = 1.0
    sustained_beneish_breach: bool = False
    going_concern_flag: bool = False
    big_r_restatement_flag: bool = False
    unscheduled_auditor_change_flag: bool = False
    base_unit: float = 1.0
    sector_cap_remaining: float = 1.0
    sector_target: float = 1.0
    required_sections: int = 1
    populated_sections: int = 1


@dataclass(frozen=True)
class GradingResult:
    pqc: float
    red_flag_penalty: float
    forecast_adjustment: float
    grade_score: float
    grade: str
    confidence: float
    action: str
    position_size: float
    veto_triggered: bool
    veto_reason: str | None


class ReportCardGradingEngine:
    GRADE_WEIGHTS = {
        "A": 1.0,
        "B": 0.7,
        "C": 0.3,
        "D": 0.0,
        "F": 0.0,
    }

    @classmethod
    def grade(cls, inputs: GradingInputs) -> GradingResult:
        pqc = cls._compute_pqc(inputs)
        red_flag_penalty = cls._compute_red_flag_penalty(inputs)
        forecast_adjustment = cls._compute_forecast_adjustment(inputs)
        grade_score = _clamp(pqc - red_flag_penalty + forecast_adjustment, 0.0, 100.0)
        veto_triggered, veto_reason = cls._hard_veto(inputs)
        if veto_triggered:
            grade_score = 0.0
            grade = "F"
            action = "EXIT"
        else:
            grade = cls._grade_bucket(grade_score)
            action = cls._action_for_grade(grade)
        confidence = cls._compute_confidence(inputs)
        position_size = cls._compute_position_size(inputs, grade, confidence)
        return GradingResult(
            pqc=round(pqc, 2),
            red_flag_penalty=round(red_flag_penalty, 2),
            forecast_adjustment=round(forecast_adjustment, 2),
            grade_score=round(grade_score, 2),
            grade=grade,
            confidence=round(confidence, 4),
            action=action,
            position_size=round(position_size, 4),
            veto_triggered=veto_triggered,
            veto_reason=veto_reason,
        )

    @classmethod
    def _compute_pqc(cls, inputs: GradingInputs) -> float:
        return (
            0.35 * _default_pctile(inputs.cash_oper_profitability_pctile)
            + 0.20 * _default_pctile(inputs.capital_allocation_pctile)
            + 0.15 * _default_pctile(inputs.margin_trajectory_pctile)
            + 0.15 * _default_pctile(inputs.balance_sheet_strength_pctile)
            + 0.15 * _default_pctile(inputs.accrual_quality_pctile)
        )

    @classmethod
    def _compute_red_flag_penalty(cls, inputs: GradingInputs) -> float:
        severity = max(
            _default_severity(inputs.beneish_severity),
            _default_severity(inputs.dechow_severity),
            _default_severity(inputs.altman_distress_severity),
            _default_severity(inputs.event_flag_severity),
        )
        return _clamp(severity * inputs.penalty_weight, 0.0, 100.0)

    @classmethod
    def _compute_forecast_adjustment(cls, inputs: GradingInputs) -> float:
        if inputs.forecasted_next_q_pqc is None or inputs.current_pqc is None:
            return 0.0
        return _clamp(inputs.forecasted_next_q_pqc - inputs.current_pqc, -15.0, 15.0)

    @classmethod
    def _hard_veto(cls, inputs: GradingInputs) -> tuple[bool, str | None]:
        if inputs.going_concern_flag:
            return True, "going concern"
        if inputs.big_r_restatement_flag:
            return True, "Big-R restatement"
        if inputs.unscheduled_auditor_change_flag:
            return True, "unscheduled auditor change"
        if inputs.sustained_beneish_breach:
            return True, "sustained Beneish breach"
        return False, None

    @classmethod
    def _grade_bucket(cls, grade_score: float) -> str:
        if grade_score >= 90:
            return "A"
        if grade_score >= 75:
            return "B"
        if grade_score >= 60:
            return "C"
        if grade_score >= 40:
            return "D"
        return "F"

    @classmethod
    def _action_for_grade(cls, grade: str) -> str:
        if grade in {"A", "B"}:
            return "BUY"
        if grade == "C":
            return "HOLD"
        if grade == "D":
            return "WATCH"
        return "EXIT"

    @classmethod
    def _compute_confidence(cls, inputs: GradingInputs) -> float:
        section_completeness = 1.0
        if inputs.required_sections > 0:
            section_completeness = _clamp(inputs.populated_sections / inputs.required_sections, 0.0, 1.0)
        confidence = (
            _clamp(inputs.data_completeness_pct / 100.0, 0.0, 1.0)
            * section_completeness
            * _clamp(1.0 - inputs.forensic_score_dispersion, 0.0, 1.0)
            * _clamp(inputs.recency_factor, 0.0, 1.0)
        )
        return _clamp(confidence, 0.0, 1.0)

    @classmethod
    def _compute_position_size(cls, inputs: GradingInputs, grade: str, confidence: float) -> float:
        sector_scalar = 1.0
        if inputs.sector_target > 0:
            sector_scalar = min(1.0, inputs.sector_cap_remaining / inputs.sector_target)
        return (
            inputs.base_unit
            * cls.GRADE_WEIGHTS[grade]
            * confidence
            * _clamp(sector_scalar, 0.0, 1.0)
        )


def _default_pctile(value: float | None) -> float:
    return _clamp(value if value is not None else 50.0, 0.0, 100.0)


def _default_severity(value: float | None) -> float:
    return _clamp(value if value is not None else 0.0, 0.0, 100.0)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
