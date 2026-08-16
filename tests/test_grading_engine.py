from __future__ import annotations

from accountant.research.grading_engine import GradingInputs, ReportCardGradingEngine


def test_grading_engine_assigns_a_grade_for_strong_quality_profile() -> None:
    result = ReportCardGradingEngine.grade(
        GradingInputs(
            cash_oper_profitability_pctile=92,
            capital_allocation_pctile=85,
            margin_trajectory_pctile=80,
            balance_sheet_strength_pctile=88,
            accrual_quality_pctile=84,
            beneish_severity=10,
            dechow_severity=5,
            altman_distress_severity=8,
            event_flag_severity=0,
            forecasted_next_q_pqc=90,
            current_pqc=84,
            data_completeness_pct=93,
            forensic_score_dispersion=0.08,
            recency_factor=1.0,
        )
    )

    assert result.grade in {"A", "B"}
    assert result.grade_score > 75
    assert result.action == "BUY"
    assert result.position_size > 0
    assert result.veto_triggered is False


def test_grading_engine_vetoes_hard_failure() -> None:
    result = ReportCardGradingEngine.grade(
        GradingInputs(
            cash_oper_profitability_pctile=95,
            capital_allocation_pctile=90,
            margin_trajectory_pctile=90,
            balance_sheet_strength_pctile=90,
            accrual_quality_pctile=90,
            beneish_severity=0,
            dechow_severity=0,
            altman_distress_severity=0,
            event_flag_severity=0,
            data_completeness_pct=100,
            going_concern_flag=True,
        )
    )

    assert result.grade == "F"
    assert result.action == "EXIT"
    assert result.veto_triggered is True
    assert result.veto_reason == "going concern"
    assert result.position_size == 0


def test_grading_engine_confidence_penalizes_missing_sections() -> None:
    result = ReportCardGradingEngine.grade(
        GradingInputs(
            cash_oper_profitability_pctile=80,
            capital_allocation_pctile=80,
            margin_trajectory_pctile=80,
            balance_sheet_strength_pctile=80,
            accrual_quality_pctile=80,
            beneish_severity=10,
            dechow_severity=10,
            altman_distress_severity=10,
            event_flag_severity=0,
            data_completeness_pct=90,
            forensic_score_dispersion=0.05,
            recency_factor=1.0,
            required_sections=10,
            populated_sections=5,
        )
    )

    assert result.confidence < 0.5
