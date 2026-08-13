"""Economic Debt, Dilution, and Capital Allocation calculation engines."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from accountant.calculations.framework import (
    CAPITAL_ALLOCATION_THRESHOLD_V1,
    DILUTION_SBC_V1,
    DILUTION_WARRANTS_OPTIONS_V1,
    ECONOMIC_DEBT_ADJUSTED_V1,
    ECONOMIC_DEBT_IMPLIED_V1,
    ECONOMIC_DEBT_REPORTED_V1,
    CalculationContext,
    CalculationResult,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

ZERO_THRESHOLD = 1.0
SHARES_ZERO_THRESHOLD = 0.001


class EconomicDebtCalculator:
    """Calculates Economic Debt using three explicit models."""

    @staticmethod
    def calculate_reported(
        total_debt: float | None,
        operating_lease_liability: float | None,
        finance_lease_liability: float | None,
        pension_underfunding: float | None,
        other_obligations: float | None,
        context: CalculationContext,
    ) -> CalculationResult:
        """Reported Economic Debt model: Explicit balance sheet obligations.

        Reported = Total Debt + Operating Leases (ASC 842) + Finance Leases
                   + Pension Underfunding + Other Long-term Obligations
        """
        result = CalculationResult(
            calculation_id="ECONOMIC_DEBT",
            formula_version=ECONOMIC_DEBT_REPORTED_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula=(
                "Economic Debt (Reported) = Total Debt + Operating Leases "
                "+ Finance Leases + Pension Underfunding + Other Obligations"
            ),
        )

        if total_debt is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing total debt")
            return result

        economic_debt = total_debt + (operating_lease_liability or 0.0)
        economic_debt += finance_lease_liability or 0.0
        economic_debt += pension_underfunding or 0.0
        economic_debt += other_obligations or 0.0

        result.value = economic_debt
        result.metadata = {
            "model": "REPORTED",
            "total_debt": total_debt,
            "operating_lease_liability": operating_lease_liability or 0.0,
            "finance_lease_liability": finance_lease_liability or 0.0,
            "pension_underfunding": pension_underfunding or 0.0,
            "other_obligations": other_obligations or 0.0,
        }
        result.inputs = {
            "total_debt": total_debt,
            "operating_lease_liability": operating_lease_liability or 0.0,
            "finance_lease_liability": finance_lease_liability or 0.0,
            "pension_underfunding": pension_underfunding or 0.0,
            "other_obligations": other_obligations or 0.0,
        }
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def calculate_adjusted(
        total_debt: float | None,
        operating_lease_liability: float | None,
        finance_lease_liability: float | None,
        pension_underfunding: float | None,
        other_obligations: float | None,
        capitalized_intangibles: float | None,
        environment_liabilities: float | None,
        context: CalculationContext,
    ) -> CalculationResult:
        """Adjusted Economic Debt model: Includes non-balance sheet obligations.

        Adjusted = Reported + Capitalized Intangibles + Environmental Liabilities
                   + Contingent Liabilities
        """
        result = CalculationResult(
            calculation_id="ECONOMIC_DEBT",
            formula_version=ECONOMIC_DEBT_ADJUSTED_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula=(
                "Economic Debt (Adjusted) = Reported + Capitalized Intangibles "
                "+ Environmental Liabilities + Contingencies"
            ),
        )

        if total_debt is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing total debt")
            return result

        economic_debt = total_debt + (operating_lease_liability or 0.0)
        economic_debt += finance_lease_liability or 0.0
        economic_debt += pension_underfunding or 0.0
        economic_debt += other_obligations or 0.0
        economic_debt += capitalized_intangibles or 0.0
        economic_debt += environment_liabilities or 0.0

        result.value = economic_debt
        result.metadata = {
            "model": "ADJUSTED",
            "total_debt": total_debt,
            "operating_lease_liability": operating_lease_liability or 0.0,
            "finance_lease_liability": finance_lease_liability or 0.0,
            "pension_underfunding": pension_underfunding or 0.0,
            "other_obligations": other_obligations or 0.0,
            "capitalized_intangibles": capitalized_intangibles or 0.0,
            "environment_liabilities": environment_liabilities or 0.0,
        }
        result.inputs = {
            "total_debt": total_debt,
            "operating_lease_liability": operating_lease_liability or 0.0,
            "finance_lease_liability": finance_lease_liability or 0.0,
            "pension_underfunding": pension_underfunding or 0.0,
            "other_obligations": other_obligations or 0.0,
            "capitalized_intangibles": capitalized_intangibles or 0.0,
            "environment_liabilities": environment_liabilities or 0.0,
        }
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def calculate_implied(
        total_debt: float | None,
        market_cap: float | None,
        net_cash: float | None,
        context: CalculationContext,
        leverage_target: float = 2.5,
    ) -> CalculationResult:
        """Implied Economic Debt model: Derived from market cap and leverage target.

        Implied = (Market Cap × Target Leverage) - Net Cash
        Represents "optimal" or "normalized" debt level for the company.
        """
        result = CalculationResult(
            calculation_id="ECONOMIC_DEBT",
            formula_version=ECONOMIC_DEBT_IMPLIED_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula=(
                "Economic Debt (Implied) = (Market Cap × Target Leverage) - Net Cash"
            ),
        )

        if market_cap is None or market_cap < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing or invalid market capitalization")
            return result

        implied_debt = (market_cap * leverage_target) - (net_cash or 0.0)
        implied_debt = max(0.0, implied_debt)

        result.value = implied_debt
        result.metadata = {
            "model": "IMPLIED",
            "market_cap": market_cap,
            "target_leverage": leverage_target,
            "net_cash": net_cash or 0.0,
            "implied_debt_at_target": implied_debt,
            "current_debt": total_debt or 0.0,
            "vs_target": "above" if (total_debt or 0.0) > implied_debt else "below",
        }
        result.inputs = {
            "market_cap": market_cap,
            "target_leverage": leverage_target,
            "net_cash": net_cash or 0.0,
            "current_debt": total_debt or 0.0,
        }
        result.calculated_at = datetime.utcnow()
        return result


class DilutionCalculator:
    """Calculates dilution from stock-based compensation and equity instruments."""

    @staticmethod
    def calculate_sbc_dilution(
        shares_outstanding: float | None,
        sbc_expense: float | None,
        stock_price: float | None,
        sbc_vesting_years: float = 3.0,
        context: CalculationContext = None,
    ) -> CalculationResult:
        """SBC dilution: Estimated shares from current-year stock-based compensation.

        SBC Shares = (SBC Expense × Vesting Years) / Stock Price
        Represents annual dilution assuming SBC vests over N years.
        """
        if context is None:
            context = CalculationContext(company_id="UNKNOWN", fiscal_year=0)

        result = CalculationResult(
            calculation_id="DILUTION",
            formula_version=DILUTION_SBC_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="shares",
            formula="Dilution (SBC) = (SBC Expense × Vesting Years) / Stock Price",
        )

        if not shares_outstanding or shares_outstanding < SHARES_ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing or invalid shares outstanding")
            return result

        if not sbc_expense or sbc_expense < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing or invalid SBC expense")
            return result

        if not stock_price or stock_price < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing or invalid stock price")
            return result

        sbc_shares = (sbc_expense * sbc_vesting_years) / stock_price
        dilution_percent = (sbc_shares / shares_outstanding) * 100.0

        result.value = sbc_shares
        result.metadata = {
            "method": "SBC",
            "shares_outstanding": shares_outstanding,
            "sbc_expense": sbc_expense,
            "stock_price": stock_price,
            "vesting_years": sbc_vesting_years,
            "sbc_shares": sbc_shares,
            "dilution_percent": dilution_percent,
        }
        result.inputs = {
            "shares_outstanding": shares_outstanding,
            "sbc_expense": sbc_expense,
            "stock_price": stock_price,
            "sbc_vesting_years": sbc_vesting_years,
        }
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def calculate_warrants_options_dilution(
        shares_outstanding: float | None,
        in_the_money_warrants: float | None,
        in_the_money_options: float | None,
        stock_price: float | None,
        avg_exercise_price: float | None,
        context: CalculationContext = None,
    ) -> CalculationResult:
        """Warrants & Options dilution: Treasury stock method.

        Net Dilution = (In-the-Money Shares) - Proceeds / Stock Price
        Represents dilutive effect using proceeds from exercise.
        """
        if context is None:
            context = CalculationContext(company_id="UNKNOWN", fiscal_year=0)

        result = CalculationResult(
            calculation_id="DILUTION",
            formula_version=DILUTION_WARRANTS_OPTIONS_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="shares",
            formula=(
                "Dilution (W&O) = ITM Shares - (Proceeds / Stock Price) "
                "[Treasury Stock Method]"
            ),
        )

        if not shares_outstanding or shares_outstanding < SHARES_ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing or invalid shares outstanding")
            return result

        if not stock_price or stock_price < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing or invalid stock price")
            return result

        total_itm = (in_the_money_warrants or 0.0) + (in_the_money_options or 0.0)

        if total_itm < SHARES_ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("No in-the-money warrants or options")
            return result

        proceeds = total_itm * (avg_exercise_price or stock_price)
        shares_repurchased = proceeds / stock_price
        net_dilution = total_itm - shares_repurchased
        net_dilution = max(0.0, net_dilution)
        dilution_percent = (net_dilution / shares_outstanding) * 100.0

        result.value = net_dilution
        result.metadata = {
            "method": "TREASURY_STOCK",
            "shares_outstanding": shares_outstanding,
            "in_the_money_warrants": in_the_money_warrants or 0.0,
            "in_the_money_options": in_the_money_options or 0.0,
            "total_itm": total_itm,
            "stock_price": stock_price,
            "avg_exercise_price": avg_exercise_price or stock_price,
            "proceeds": proceeds,
            "shares_repurchased": shares_repurchased,
            "net_dilution": net_dilution,
            "dilution_percent": dilution_percent,
        }
        result.inputs = {
            "shares_outstanding": shares_outstanding,
            "in_the_money_warrants": in_the_money_warrants or 0.0,
            "in_the_money_options": in_the_money_options or 0.0,
            "stock_price": stock_price,
            "avg_exercise_price": avg_exercise_price or stock_price,
        }
        result.calculated_at = datetime.utcnow()
        return result


class CapitalAllocationCalculator:
    """Evaluates capital allocation efficiency against ROIC hurdle rates."""

    @staticmethod
    def evaluate_allocation(
        owner_earnings: float | None,
        incremental_invested_capital: float | None,
        incremental_roic: float | None,
        wacc: float | None,
        capital_expenditure: float | None,
        share_repurchases: float | None,
        dividends: float | None,
        debt_reduction: float | None,
        context: CalculationContext = None,
    ) -> CalculationResult:
        """Evaluate capital allocation decisions against ROIC > WACC threshold.

        Uses Incremental ROIC vs WACC to score allocation efficiency.
        Allocations with ROIC > WACC are value-creating.
        Allocations with ROIC < WACC are value-destroying.
        """
        if context is None:
            context = CalculationContext(company_id="UNKNOWN", fiscal_year=0)

        result = CalculationResult(
            calculation_id="CAPITAL_ALLOCATION",
            formula_version=CAPITAL_ALLOCATION_THRESHOLD_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="assessment",
            formula="Allocation Score = ROIC vs WACC threshold",
        )

        if owner_earnings is None or owner_earnings < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing or invalid owner earnings")
            return result

        total_allocated = (
            (capital_expenditure or 0.0)
            + (share_repurchases or 0.0)
            + (dividends or 0.0)
            + (debt_reduction or 0.0)
        )

        if total_allocated < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("No capital allocation detected")
            return result

        allocation_pct = (total_allocated / owner_earnings) * 100.0
        unallocated = owner_earnings - total_allocated

        allocation_score = "UNKNOWN"
        if wacc and incremental_roic:
            if incremental_roic > wacc:
                allocation_score = "VALUE_CREATING" if capital_expenditure else "APPROPRIATE"
            elif incremental_roic < wacc:
                allocation_score = "VALUE_DESTROYING" if capital_expenditure else "NEUTRAL"

        result.value = allocation_score
        result.metadata = {
            "owner_earnings": owner_earnings,
            "total_allocated": total_allocated,
            "allocation_pct": allocation_pct,
            "unallocated": max(0.0, unallocated),
            "capex": capital_expenditure or 0.0,
            "repurchases": share_repurchases or 0.0,
            "dividends": dividends or 0.0,
            "debt_reduction": debt_reduction or 0.0,
            "incremental_roic": incremental_roic,
            "wacc": wacc,
            "roic_spread": (incremental_roic or 0.0) - (wacc or 0.0),
            "allocation_score": allocation_score,
        }
        result.inputs = {
            "owner_earnings": owner_earnings,
            "capital_expenditure": capital_expenditure or 0.0,
            "share_repurchases": share_repurchases or 0.0,
            "dividends": dividends or 0.0,
            "debt_reduction": debt_reduction or 0.0,
            "incremental_roic": incremental_roic or 0.0,
            "wacc": wacc or 0.0,
        }
        result.calculated_at = datetime.utcnow()
        return result
