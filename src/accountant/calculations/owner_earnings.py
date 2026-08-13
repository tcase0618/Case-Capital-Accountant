"""Owner Earnings and Maintenance CAPEX calculation engines."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from accountant.calculations.framework import (
    MAINTENANCE_CAPEX_DA_ANCHOR_V1,
    MAINTENANCE_CAPEX_GROWTH_SEPARATION_V1,
    MAINTENANCE_CAPEX_HISTORICAL_RATIO_V1,
    MAINTENANCE_CAPEX_RANGE_V1,
    OWNER_EARNINGS_CFO_V1,
    OWNER_EARNINGS_CONSERVATIVE_V1,
    OWNER_EARNINGS_MAINT_CAPEX_V1,
    CalculationContext,
    CalculationResult,
)

if TYPE_CHECKING:
    from accountant.financial.statement_builder import IncomeStatementData

logger = logging.getLogger(__name__)

ZERO_THRESHOLD = 1.0
MAX_REASONABLE_RATIO = 1000.0


class MaintenanceCapexEstimator:
    """Estimates maintenance CAPEX using multiple deterministic methods."""

    @staticmethod
    def estimate_da_anchor(
        statement: IncomeStatementData,
        context: CalculationContext,
        da_multiple_low: float = 0.9,
        da_multiple_base: float = 1.0,
        da_multiple_high: float = 1.1,
    ) -> CalculationResult:
        """Estimate maintenance CAPEX as multiple of D&A (Method A).

        Assumption: Over long periods, maintenance CAPEX ≈ D&A.
        The low/base/high multiples capture uncertainty.
        """
        result = CalculationResult(
            calculation_id="MAINTENANCE_CAPEX_DA_ANCHOR",
            formula_version=MAINTENANCE_CAPEX_DA_ANCHOR_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula="Maintenance CAPEX ≈ D&A × multiple",
        )

        da_line = statement.lines.get("CC_DEPRECIATION_AMORTIZATION")
        if not da_line or da_line.value_numeric is None or da_line.value_numeric == 0:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing or zero depreciation/amortization")
            return result

        da_value = da_line.value_numeric

        if abs(da_value) < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("D&A below zero threshold")
            return result

        result.value = da_value * da_multiple_base
        result.metadata = {
            "low": da_value * da_multiple_low,
            "base": da_value * da_multiple_base,
            "high": da_value * da_multiple_high,
            "method": "DA_ANCHOR",
            "da_value": da_value,
            "da_multiple_base": da_multiple_base,
        }
        result.inputs = {
            "depreciation_amortization": da_value,
            "da_multiple_low": da_multiple_low,
            "da_multiple_base": da_multiple_base,
            "da_multiple_high": da_multiple_high,
        }
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def estimate_historical_ratio(
        current_year_capex: float,
        current_year_ppe: float,
        context: CalculationContext,
    ) -> CalculationResult:
        """Estimate maintenance CAPEX from historical CAPEX/PPE ratio (Method B).

        Assumption: Maintenance CAPEX is relatively stable as % of PPE.
        Growth companies may have higher ratios.
        """
        result = CalculationResult(
            calculation_id="MAINTENANCE_CAPEX_HISTORICAL_RATIO",
            formula_version=MAINTENANCE_CAPEX_HISTORICAL_RATIO_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula="Maintenance CAPEX ≈ PPE × historical CAPEX/PPE ratio",
        )

        if (
            current_year_capex is None
            or current_year_ppe is None
            or abs(current_year_ppe) < ZERO_THRESHOLD
        ):
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing or zero PPE or CAPEX")
            return result

        # Conservative estimate: assume historical CAPEX represents maintenance
        # (This is conservative because growth CAPEX is typically embedded in total)
        historical_ratio = abs(current_year_capex) / abs(current_year_ppe)

        if historical_ratio > MAX_REASONABLE_RATIO:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning(f"CAPEX/PPE ratio {historical_ratio:.2f}x exceeds sanity check")
            return result

        # Use conservative 50-80% of total CAPEX as maintenance estimate
        maint_capex_low = abs(current_year_capex) * 0.50
        maint_capex_base = abs(current_year_capex) * 0.65
        maint_capex_high = abs(current_year_capex) * 0.80

        result.value = maint_capex_base
        result.metadata = {
            "low": maint_capex_low,
            "base": maint_capex_base,
            "high": maint_capex_high,
            "method": "HISTORICAL_RATIO",
            "current_year_capex": abs(current_year_capex),
            "current_year_ppe": abs(current_year_ppe),
            "capex_ppe_ratio": historical_ratio,
        }
        result.inputs = {
            "current_year_capex": abs(current_year_capex),
            "current_year_ppe": abs(current_year_ppe),
        }
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def estimate_growth_separation(
        current_year_capex: float,
        prior_year_ppe: float,
        current_year_ppe: float,
        revenue_growth_rate: float,
        context: CalculationContext,
    ) -> CalculationResult:
        """Estimate maintenance CAPEX by separating growth CAPEX (Method C).

        Δ PPE = Maintenance CAPEX - D&A + Growth CAPEX
        Therefore:
        Growth CAPEX ≈ Δ PPE + D&A - Maintenance CAPEX

        For simplification, estimate:
        Growth CAPEX ≈ (Δ PPE) × revenue_growth_rate
        Maintenance CAPEX ≈ CAPEX - Growth CAPEX
        """
        result = CalculationResult(
            calculation_id="MAINTENANCE_CAPEX_GROWTH_SEPARATION",
            formula_version=MAINTENANCE_CAPEX_GROWTH_SEPARATION_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula="Maint CAPEX = Total CAPEX - (Δ PPE × growth_rate_proxy)",
        )

        if (
            current_year_capex is None
            or prior_year_ppe is None
            or current_year_ppe is None
        ):
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing CAPEX or PPE data")
            return result

        delta_ppe = current_year_ppe - prior_year_ppe
        growth_capex_estimate = abs(delta_ppe) * max(0, revenue_growth_rate / 100.0)

        maint_capex_estimate = abs(current_year_capex) - growth_capex_estimate

        if maint_capex_estimate < 0:
            maint_capex_estimate = 0
            result.add_warning("Growth CAPEX exceeded total CAPEX; maintenance capped at zero")

        # Range: ±20% around estimate
        maint_capex_low = maint_capex_estimate * 0.80
        maint_capex_base = maint_capex_estimate
        maint_capex_high = maint_capex_estimate * 1.20

        result.value = maint_capex_base
        result.metadata = {
            "low": maint_capex_low,
            "base": maint_capex_base,
            "high": maint_capex_high,
            "method": "GROWTH_SEPARATION",
            "total_capex": abs(current_year_capex),
            "delta_ppe": delta_ppe,
            "estimated_growth_capex": growth_capex_estimate,
            "revenue_growth_rate": revenue_growth_rate,
        }
        result.inputs = {
            "current_year_capex": abs(current_year_capex),
            "prior_year_ppe": prior_year_ppe,
            "current_year_ppe": current_year_ppe,
            "revenue_growth_rate": revenue_growth_rate,
        }
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def estimate_range(
        historical_capex_list: list[float],
        historical_revenue_list: list[float],
        context: CalculationContext,
    ) -> CalculationResult:
        """Estimate maintenance CAPEX from normalized historical range (Method D).

        Uses percentile approach on CAPEX/Revenue ratios over multi-year history.
        """
        result = CalculationResult(
            calculation_id="MAINTENANCE_CAPEX_RANGE",
            formula_version=MAINTENANCE_CAPEX_RANGE_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula="Maintenance CAPEX ≈ normalized from multi-year range",
        )

        if not historical_capex_list or not historical_revenue_list:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Insufficient historical data (need at least 1 year)")
            return result

        if len(historical_capex_list) != len(historical_revenue_list):
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Mismatched CAPEX and revenue history length")
            return result

        # Filter out invalid data
        valid_ratios = []
        for capex, rev in zip(historical_capex_list, historical_revenue_list, strict=True):
            if capex is None or rev is None or abs(rev) < ZERO_THRESHOLD:
                continue
            ratio = abs(capex) / abs(rev)
            if ratio > MAX_REASONABLE_RATIO:
                continue
            valid_ratios.append(ratio)

        if not valid_ratios:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("No valid CAPEX/Revenue ratios in history")
            return result

        # Calculate percentiles
        valid_ratios.sort()
        low_ratio = valid_ratios[0]
        base_ratio = sum(valid_ratios) / len(valid_ratios)
        high_ratio = valid_ratios[-1]

        current_revenue = historical_revenue_list[-1]
        if current_revenue is None or abs(current_revenue) < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Current year revenue invalid")
            return result

        maint_capex_low = abs(current_revenue) * low_ratio
        maint_capex_base = abs(current_revenue) * base_ratio
        maint_capex_high = abs(current_revenue) * high_ratio

        result.value = maint_capex_base
        result.metadata = {
            "low": maint_capex_low,
            "base": maint_capex_base,
            "high": maint_capex_high,
            "method": "HISTORICAL_RANGE",
            "low_ratio": low_ratio,
            "base_ratio": base_ratio,
            "high_ratio": high_ratio,
            "current_revenue": abs(current_revenue),
            "history_length": len(valid_ratios),
        }
        result.inputs = {
            "historical_capex_list": historical_capex_list,
            "historical_revenue_list": historical_revenue_list,
        }
        result.calculated_at = datetime.utcnow()
        return result


class OwnerEarningsCalculator:
    """Calculates Owner Earnings using three explicit models."""

    @staticmethod
    def calculate_conservative(
        net_income: float,
        noncash_charges: float,
        total_capex: float,
        required_working_capital_investment: float,
        context: CalculationContext,
        recurring_economic_adjustments: float = 0.0,
    ) -> CalculationResult:
        """Conservative model: NI + noncash - total CAPEX - WC investment.

        Conservative approach: Use full CAPEX (no maintenance/growth separation).
        """
        result = CalculationResult(
            calculation_id="OWNER_EARNINGS",
            formula_version=OWNER_EARNINGS_CONSERVATIVE_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula=(
                "OE = NI + noncash_charges - total_CAPEX "
                "- required_WC_investment - recurring_adjustments"
            ),
        )

        if net_income is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing net income")
            return result

        owner_earnings = (
            net_income
            + (noncash_charges or 0.0)
            - (total_capex or 0.0)
            - (required_working_capital_investment or 0.0)
            - (recurring_economic_adjustments or 0.0)
        )

        result.value = owner_earnings
        result.metadata = {
            "model": "CONSERVATIVE",
            "net_income": net_income,
            "noncash_charges": noncash_charges or 0.0,
            "total_capex": total_capex or 0.0,
            "required_wc_investment": required_working_capital_investment or 0.0,
            "recurring_economic_adjustments": recurring_economic_adjustments or 0.0,
        }
        result.inputs = {
            "net_income": net_income,
            "noncash_charges": noncash_charges or 0.0,
            "total_capex": total_capex or 0.0,
            "required_working_capital_investment": (
                required_working_capital_investment or 0.0
            ),
            "recurring_economic_adjustments": recurring_economic_adjustments or 0.0,
        }
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def calculate_maintenance_capex_model(
        net_income: float,
        noncash_charges: float,
        maintenance_capex: float,
        required_working_capital_investment: float,
        context: CalculationContext,
        recurring_economic_adjustments: float = 0.0,
    ) -> CalculationResult:
        """Maintenance CAPEX model: NI + noncash - maintenance CAPEX - WC investment.

        More realistic approach: Uses estimated maintenance CAPEX,
        allowing growth CAPEX to flow through to shareholder returns.
        """
        result = CalculationResult(
            calculation_id="OWNER_EARNINGS",
            formula_version=OWNER_EARNINGS_MAINT_CAPEX_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula=(
                "OE = NI + noncash_charges - maintenance_CAPEX "
                "- required_WC_investment - recurring_adjustments"
            ),
        )

        if net_income is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing net income")
            return result

        owner_earnings = (
            net_income
            + (noncash_charges or 0.0)
            - (maintenance_capex or 0.0)
            - (required_working_capital_investment or 0.0)
            - (recurring_economic_adjustments or 0.0)
        )

        result.value = owner_earnings
        result.metadata = {
            "model": "MAINTENANCE_CAPEX",
            "net_income": net_income,
            "noncash_charges": noncash_charges or 0.0,
            "maintenance_capex": maintenance_capex or 0.0,
            "required_wc_investment": required_working_capital_investment or 0.0,
            "recurring_economic_adjustments": recurring_economic_adjustments or 0.0,
        }
        result.inputs = {
            "net_income": net_income,
            "noncash_charges": noncash_charges or 0.0,
            "maintenance_capex": maintenance_capex or 0.0,
            "required_working_capital_investment": (
                required_working_capital_investment or 0.0
            ),
            "recurring_economic_adjustments": recurring_economic_adjustments or 0.0,
        }
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def calculate_cfo_model(
        operating_cash_flow: float,
        maintenance_capex: float,
        context: CalculationContext,
        recurring_economic_adjustments: float = 0.0,
    ) -> CalculationResult:
        """CFO model: Operating Cash Flow - maintenance CAPEX - adjustments.

        Most direct approach using actual cash generation.
        """
        result = CalculationResult(
            calculation_id="OWNER_EARNINGS",
            formula_version=OWNER_EARNINGS_CFO_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula="OE = CFO - maintenance_CAPEX - recurring_adjustments",
        )

        if operating_cash_flow is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing operating cash flow")
            return result

        owner_earnings = (
            operating_cash_flow
            - (maintenance_capex or 0.0)
            - (recurring_economic_adjustments or 0.0)
        )

        result.value = owner_earnings
        result.metadata = {
            "model": "CFO",
            "operating_cash_flow": operating_cash_flow,
            "maintenance_capex": maintenance_capex or 0.0,
            "recurring_economic_adjustments": recurring_economic_adjustments or 0.0,
        }
        result.inputs = {
            "operating_cash_flow": operating_cash_flow,
            "maintenance_capex": maintenance_capex or 0.0,
            "recurring_economic_adjustments": recurring_economic_adjustments or 0.0,
        }
        result.calculated_at = datetime.utcnow()
        return result
