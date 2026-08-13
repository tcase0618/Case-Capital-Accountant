"""Metric calculators for financial statements."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from accountant.calculations.framework import (
    FCF_MARGIN_V1,
    FCF_V1,
    GROSS_MARGIN_V1,
    INCREMENTAL_ROIC_1Y_V1,
    INCREMENTAL_ROIC_3Y_V1,
    INCREMENTAL_ROIC_5Y_V1,
    INVESTED_CAPITAL_OPERATING_V1,
    NET_MARGIN_V1,
    NOPAT_V1,
    OPERATING_MARGIN_V1,
    REVENUE_GROWTH_V1,
    ROE_AVG_EQUITY_V1,
    ROIC_V1,
    CalculationContext,
    CalculationResult,
)

if TYPE_CHECKING:
    from accountant.financial.statement_builder import (
        BalanceSheetData,
        CashFlowStatementData,
        IncomeStatementData,
    )

logger = logging.getLogger(__name__)

# Thresholds for avoiding divide-by-zero and detecting anomalies
ZERO_THRESHOLD = 1.0  # Minimum denominator value (USD or metric units)
MAX_REASONABLE_RATIO = 1000.0  # Unreasonable ratios get flagged


class ProfitabilityCalculator:
    """Calculates profitability metrics."""

    @staticmethod
    def revenue_growth_yoy(
        current_year: IncomeStatementData,
        prior_year: IncomeStatementData | None,
        context: CalculationContext,
    ) -> CalculationResult:
        """Calculate YoY revenue growth."""
        result = CalculationResult(
            calculation_id="REVENUE_GROWTH_YOY",
            formula_version=REVENUE_GROWTH_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="%",
            formula="(Revenue_Current - Revenue_Prior) / Revenue_Prior",
        )

        current_rev = current_year.lines.get("CC_REVENUE")
        if not current_rev or current_rev.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing current year revenue")
            return result

        if prior_year is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("No prior year data")
            return result

        prior_rev = prior_year.lines.get("CC_REVENUE")
        if not prior_rev or prior_rev.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing prior year revenue")
            return result

        current_val = current_rev.value_numeric
        prior_val = prior_rev.value_numeric

        if abs(prior_val) < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Prior year revenue near zero")
            return result

        result.value = ((current_val - prior_val) / prior_val) * 100
        result.inputs = {"current_revenue": current_val, "prior_revenue": prior_val}
        result.source_statement_line_ids = [
            str(current_rev.canonical_fact_id) if current_rev.canonical_fact_id else "",
            str(prior_rev.canonical_fact_id) if prior_rev.canonical_fact_id else "",
        ]
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def gross_margin(
        statement: IncomeStatementData,
        context: CalculationContext,
    ) -> CalculationResult:
        """Calculate gross profit margin."""
        result = CalculationResult(
            calculation_id="GROSS_MARGIN",
            formula_version=GROSS_MARGIN_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="%",
            formula="Gross Profit / Revenue",
        )

        gross = statement.lines.get("CC_GROSS_PROFIT")
        revenue = statement.lines.get("CC_REVENUE")

        if not gross or gross.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing gross profit")
            return result

        if not revenue or revenue.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing revenue")
            return result

        rev_val = revenue.value_numeric
        if abs(rev_val) < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Revenue near zero")
            return result

        result.value = (gross.value_numeric / rev_val) * 100
        result.inputs = {"gross_profit": gross.value_numeric, "revenue": rev_val}
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def operating_margin(
        statement: IncomeStatementData,
        context: CalculationContext,
    ) -> CalculationResult:
        """Calculate operating margin."""
        result = CalculationResult(
            calculation_id="OPERATING_MARGIN",
            formula_version=OPERATING_MARGIN_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="%",
            formula="Operating Income / Revenue",
        )

        oi = statement.lines.get("CC_OPERATING_INCOME")
        revenue = statement.lines.get("CC_REVENUE")

        if not oi or oi.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing operating income")
            return result

        if not revenue or revenue.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing revenue")
            return result

        rev_val = revenue.value_numeric
        if abs(rev_val) < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Revenue near zero")
            return result

        result.value = (oi.value_numeric / rev_val) * 100
        result.inputs = {"operating_income": oi.value_numeric, "revenue": rev_val}
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def net_margin(
        statement: IncomeStatementData,
        context: CalculationContext,
    ) -> CalculationResult:
        """Calculate net profit margin."""
        result = CalculationResult(
            calculation_id="NET_MARGIN",
            formula_version=NET_MARGIN_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="%",
            formula="Net Income / Revenue",
        )

        ni = statement.lines.get("CC_NET_INCOME")
        revenue = statement.lines.get("CC_REVENUE")

        if not ni or ni.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing net income")
            return result

        if not revenue or revenue.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing revenue")
            return result

        rev_val = revenue.value_numeric
        if abs(rev_val) < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Revenue near zero")
            return result

        result.value = (ni.value_numeric / rev_val) * 100
        result.inputs = {"net_income": ni.value_numeric, "revenue": rev_val}
        result.calculated_at = datetime.utcnow()
        return result


class CashFlowCalculator:
    """Calculates cash flow metrics."""

    @staticmethod
    def free_cash_flow(
        statement: CashFlowStatementData,
        context: CalculationContext,
    ) -> CalculationResult:
        """Calculate free cash flow: CFO - CapEx."""
        result = CalculationResult(
            calculation_id="FCF",
            formula_version=FCF_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula="Operating Cash Flow - CapEx",
        )

        cfo = statement.lines.get("CC_OPERATING_CASH_FLOW")
        capex = statement.lines.get("CC_CAPEX")

        if not cfo or cfo.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing operating cash flow")
            return result

        if not capex or capex.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing CapEx")
            return result

        cfo_val = cfo.value_numeric
        capex_val = capex.value_numeric

        # Note: CAPEX is typically reported negative, so we normalize
        if capex_val < 0:
            capex_val = abs(capex_val)
        else:
            result.add_warning("CapEx reported as positive; typically negative")

        result.value = cfo_val - capex_val
        result.inputs = {"cfo": cfo.value_numeric, "capex": capex.value_numeric}
        result.calculated_at = datetime.utcnow()
        return result

    @staticmethod
    def fcf_margin(
        income_stmt: IncomeStatementData,
        cf_stmt: CashFlowStatementData,
        context: CalculationContext,
    ) -> CalculationResult:
        """Calculate FCF margin: FCF / Revenue."""
        result = CalculationResult(
            calculation_id="FCF_MARGIN",
            formula_version=FCF_MARGIN_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="%",
            formula="Free Cash Flow / Revenue",
        )

        revenue = income_stmt.lines.get("CC_REVENUE")
        cfo = cf_stmt.lines.get("CC_OPERATING_CASH_FLOW")
        capex = cf_stmt.lines.get("CC_CAPEX")

        if not revenue or revenue.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing revenue")
            return result

        if not cfo or cfo.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing operating cash flow")
            return result

        if not capex or capex.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing CapEx")
            return result

        rev_val = revenue.value_numeric
        if abs(rev_val) < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Revenue near zero")
            return result

        capex_val = abs(capex.value_numeric)
        fcf = cfo.value_numeric - capex_val
        result.value = (fcf / rev_val) * 100
        result.inputs = {"fcf": fcf, "revenue": rev_val}
        result.calculated_at = datetime.utcnow()
        return result


class ReturnsCalculator:
    """Calculates return metrics."""

    @staticmethod
    def roe_avg_equity(
        income_stmt: IncomeStatementData,
        bs_current: BalanceSheetData,
        bs_prior: BalanceSheetData | None,
        context: CalculationContext,
    ) -> CalculationResult:
        """Calculate ROE using average equity."""
        result = CalculationResult(
            calculation_id="ROE",
            formula_version=ROE_AVG_EQUITY_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="%",
            formula="Net Income / Average Equity",
        )

        ni = income_stmt.lines.get("CC_NET_INCOME")
        if not ni or ni.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing net income")
            return result

        equity_current = bs_current.lines.get("CC_EQUITY")
        if not equity_current or equity_current.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing current year equity")
            return result

        if bs_prior is None:
            result.add_warning("Using period-end equity instead of average")
            avg_equity = equity_current.value_numeric
        else:
            equity_prior = bs_prior.lines.get("CC_EQUITY")
            if not equity_prior or equity_prior.value_numeric is None:
                result.add_warning("Missing prior year equity; using current only")
                avg_equity = equity_current.value_numeric
            else:
                avg_equity = (equity_current.value_numeric + equity_prior.value_numeric) / 2

        if abs(avg_equity) < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Average equity near zero")
            return result

        result.value = (ni.value_numeric / avg_equity) * 100
        result.inputs = {"net_income": ni.value_numeric, "avg_equity": avg_equity}
        result.calculated_at = datetime.utcnow()
        return result


class NOPATCalculator:
    """Calculates NOPAT (Net Operating Profit After Tax)."""

    @staticmethod
    def calculate_nopat(
        statement: IncomeStatementData,
        context: CalculationContext,
        tax_rate_override: float | None = None,
    ) -> CalculationResult:
        """Calculate NOPAT: Operating Income × (1 - Tax Rate)."""
        result = CalculationResult(
            calculation_id="NOPAT",
            formula_version=NOPAT_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula="Operating Income × (1 - Tax Rate)",
        )

        oi = statement.lines.get("CC_OPERATING_INCOME")
        if not oi or oi.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing operating income")
            return result

        # Determine tax rate
        if tax_rate_override is not None:
            tax_rate = tax_rate_override
            result.add_warning(f"Using override tax rate: {tax_rate * 100:.1f}%")
        else:
            tax_rate = _infer_tax_rate(statement, result)

        result.value = oi.value_numeric * (1 - tax_rate)
        result.inputs = {
            "operating_income": oi.value_numeric,
            "tax_rate": tax_rate,
        }
        result.calculated_at = datetime.utcnow()
        return result


class InvestedCapitalCalculator:
    """Calculates invested capital."""

    @staticmethod
    def calculate_operating_method(
        bs_current: BalanceSheetData,
        bs_prior: BalanceSheetData | None,
        context: CalculationContext,
    ) -> CalculationResult:
        """Calculate invested capital: Operating Assets - Operating Liabilities."""
        result = CalculationResult(
            calculation_id="INVESTED_CAPITAL_OPERATING",
            formula_version=INVESTED_CAPITAL_OPERATING_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="USD",
            formula="Operating Assets - Operating Liabilities",
        )

        # Operating assets: TA - Excess Cash
        total_assets = bs_current.lines.get("CC_TOTAL_ASSETS")
        if not total_assets or total_assets.value_numeric is None:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Missing total assets")
            return result

        cash = bs_current.lines.get("CC_CASH")
        operating_assets = total_assets.value_numeric
        if cash and cash.value_numeric:
            operating_assets -= cash.value_numeric
            result.add_warning("Deducted all cash as excess cash (simplified)")

        # Operating liabilities: AP + Accrued expenses (simplified)
        ap = bs_current.lines.get("CC_ACCOUNTS_PAYABLE")
        operating_liab = 0.0
        if ap and ap.value_numeric:
            operating_liab = ap.value_numeric

        invested_capital = operating_assets - operating_liab

        if bs_prior:
            prior_assets = bs_prior.lines.get("CC_TOTAL_ASSETS")
            prior_cash = bs_prior.lines.get("CC_CASH")
            prior_ap = bs_prior.lines.get("CC_ACCOUNTS_PAYABLE")

            prior_op_assets = prior_assets.value_numeric if prior_assets else 0
            if prior_cash and prior_cash.value_numeric:
                prior_op_assets -= prior_cash.value_numeric
            prior_op_liab = prior_ap.value_numeric if prior_ap else 0

            prior_ic = prior_op_assets - prior_op_liab
            result.metadata["beginning_invested_capital"] = prior_ic
            result.metadata["ending_invested_capital"] = invested_capital
            result.metadata["average_invested_capital"] = (invested_capital + prior_ic) / 2

        result.value = invested_capital
        result.inputs = {"operating_assets": operating_assets, "operating_liabilities": operating_liab}
        result.calculated_at = datetime.utcnow()
        return result


class ROICCalculator:
    """Calculates ROIC (Return on Invested Capital)."""

    @staticmethod
    def calculate_roic(
        income_stmt: IncomeStatementData,
        bs_current: BalanceSheetData,
        bs_prior: BalanceSheetData | None,
        context: CalculationContext,
        tax_rate_override: float | None = None,
    ) -> CalculationResult:
        """Calculate ROIC: NOPAT / Average Invested Capital."""
        result = CalculationResult(
            calculation_id="ROIC",
            formula_version=ROIC_V1,
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="%",
            formula="NOPAT / Average Invested Capital",
        )

        # Calculate NOPAT
        nopat_calc = NOPATCalculator.calculate_nopat(income_stmt, context, tax_rate_override)
        if nopat_calc.calculation_status != "VALID":
            result.calculation_status = nopat_calc.calculation_status
            result.warnings.extend(nopat_calc.warnings)
            return result

        nopat = nopat_calc.value

        # Calculate invested capital
        ic_calc = InvestedCapitalCalculator.calculate_operating_method(bs_current, bs_prior, context)
        if ic_calc.calculation_status != "VALID":
            result.calculation_status = ic_calc.calculation_status
            result.warnings.extend(ic_calc.warnings)
            return result

        avg_ic = ic_calc.metadata.get("average_invested_capital", ic_calc.value)
        if abs(avg_ic) < ZERO_THRESHOLD:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Average invested capital near zero")
            return result

        result.value = (nopat / avg_ic) * 100
        result.inputs = {
            "nopat": nopat,
            "average_invested_capital": avg_ic,
        }
        result.metadata = {
            "nopat": nopat,
            "beginning_ic": ic_calc.metadata.get("beginning_invested_capital"),
            "ending_ic": ic_calc.metadata.get("ending_invested_capital"),
            "average_ic": avg_ic,
        }
        result.calculated_at = datetime.utcnow()
        return result


class IncrementalROICCalculator:
    """Calculates incremental ROIC over rolling windows."""

    @staticmethod
    def calculate_incremental_roic(
        years: list[tuple[IncomeStatementData, BalanceSheetData]],
        context: CalculationContext,
        window: int = 1,
        tax_rate_override: float | None = None,
    ) -> CalculationResult:
        """Calculate incremental ROIC: Change in NOPAT / Change in IC."""
        calc_id_map = {
            1: "INCREMENTAL_ROIC_1Y",
            3: "INCREMENTAL_ROIC_3Y",
            5: "INCREMENTAL_ROIC_5Y",
        }
        version_map = {
            1: INCREMENTAL_ROIC_1Y_V1,
            3: INCREMENTAL_ROIC_3Y_V1,
            5: INCREMENTAL_ROIC_5Y_V1,
        }

        result = CalculationResult(
            calculation_id=calc_id_map.get(window, f"INCREMENTAL_ROIC_{window}Y"),
            formula_version=version_map.get(window, INCREMENTAL_ROIC_1Y_V1),
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            value=None,
            unit="%",
            formula="Change in NOPAT / Change in Invested Capital",
        )

        if len(years) < window + 1:
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning(f"Need {window + 1} years of data; got {len(years)}")
            return result

        # Get start and end year
        start_income, start_bs = years[0]
        end_income, end_bs = years[window]

        # Calculate NOPAT at both ends
        nopat_start = NOPATCalculator.calculate_nopat(start_income, context, tax_rate_override)
        nopat_end = NOPATCalculator.calculate_nopat(end_income, context, tax_rate_override)

        if nopat_start.calculation_status != "VALID" or nopat_end.calculation_status != "VALID":
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Could not calculate NOPAT for period endpoints")
            return result

        # Calculate invested capital at both ends
        ic_start = InvestedCapitalCalculator.calculate_operating_method(start_bs, None, context)
        ic_end = InvestedCapitalCalculator.calculate_operating_method(end_bs, start_bs, context)

        if ic_start.calculation_status != "VALID" or ic_end.calculation_status != "VALID":
            result.calculation_status = "INSUFFICIENT_DATA"
            result.add_warning("Could not calculate invested capital for period endpoints")
            return result

        nopat_delta = nopat_end.value - nopat_start.value
        ic_delta = ic_end.value - ic_start.value

        if abs(ic_delta) < ZERO_THRESHOLD:
            result.calculation_status = "UNSTABLE_DENOMINATOR"
            result.add_warning(f"Change in IC near zero: {ic_delta:.2f}")
            return result

        if ic_delta < 0:
            result.calculation_status = "NEGATIVE_INCREMENTAL_CAPITAL"
            result.add_warning("Negative change in invested capital (capital reduction)")

        result.value = (nopat_delta / ic_delta) * 100
        result.inputs = {
            "nopat_start": nopat_start.value,
            "nopat_end": nopat_end.value,
            "nopat_delta": nopat_delta,
            "ic_start": ic_start.value,
            "ic_end": ic_end.value,
            "ic_delta": ic_delta,
        }
        result.metadata = {
            "window_years": window,
            "start_year": context.fiscal_year - window,
            "end_year": context.fiscal_year,
        }
        result.calculated_at = datetime.utcnow()
        return result


def _infer_tax_rate(statement: IncomeStatementData, result: CalculationResult) -> float:
    """Infer tax rate from statement using hierarchy."""
    # Try: effective tax rate = income tax / pretax income
    pretax = statement.lines.get("CC_PRETAX_INCOME")
    tax = statement.lines.get("CC_INCOME_TAX")

    if pretax and pretax.value_numeric and tax and tax.value_numeric and abs(pretax.value_numeric) > ZERO_THRESHOLD:
        etr = tax.value_numeric / pretax.value_numeric
        # Clamp to reasonable range [0, 0.5]
        if 0 <= etr <= 0.5:
            result.add_warning(f"Using reported effective tax rate: {etr * 100:.1f}%")
            return etr
        result.add_warning(f"Reported ETR {etr * 100:.1f}% out of range; using 0.21")

    # Fallback: 21% (US statutory)
    result.add_warning("Using statutory fallback tax rate: 21.0%")
    return 0.21


__all__ = [
    "ProfitabilityCalculator",
    "CashFlowCalculator",
    "ReturnsCalculator",
    "NOPATCalculator",
    "InvestedCapitalCalculator",
    "ROICCalculator",
    "IncrementalROICCalculator",
]
