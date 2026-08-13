"""Extended Dilution Engine with comprehensive share-count and buyback analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from accountant.calculations.framework import CalculationContext

if TYPE_CHECKING:
    pass


class BuybackEffectiveness(StrEnum):
    """Classification of buyback impact on shareholder value."""

    STRONG_NET_REDUCTION = "STRONG_NET_REDUCTION"  # Buyback > SBC
    MODEST_NET_REDUCTION = "MODEST_NET_REDUCTION"  # Buyback partially offsets SBC
    OFFSETTING_SBC = "OFFSETTING_SBC"  # Buyback ≈ SBC
    INEFFECTIVE_BUYBACK = "INEFFECTIVE_BUYBACK"  # Buyback < SBC
    NET_DILUTION = "NET_DILUTION"  # No buyback; pure dilution
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class DilutionMetrics:
    """Comprehensive share-count and buyback analysis."""

    company_id: str
    fiscal_year: int
    calculated_at: datetime

    # Share counts (millions)
    shares_outstanding_beginning: float | None
    shares_outstanding_ending: float | None

    # Annual dilution (shares)
    sbc_dilution_shares: float  # From SBC expense
    warrant_option_dilution: float  # From treasury stock method

    # Buyback impact (shares)
    shares_repurchased: float  # Aggregate for year
    net_dilution_after_buyback: float  # (SBC + Warrants + Options) - Repurchased

    # Growth metrics
    share_count_cagr_3y: float | None  # % annual growth, 3-year
    share_count_cagr_5y: float | None  # % annual growth, 5-year

    # Ratio analysis
    sbc_expense_millions: float | None  # For SBC/Revenue ratio context
    revenue_millions: float | None
    sbc_to_revenue_ratio: float | None  # SBC Expense / Revenue

    # Buyback efficiency
    total_repurchased_amount_millions: float | None  # Dollars spent on buyback
    avg_repurchase_price: float | None  # Dollars per share
    buyback_effectiveness: BuybackEffectiveness  # Classification
    buyback_offset_ratio: float  # Shares repurchased / (SBC + W&O) dilution

    # Warnings
    warnings: list[str]
    calculation_status: str  # VALID, INSUFFICIENT_DATA


class DilutionEngine:
    """
    Extended dilution engine tracking share-count dynamics, buyback effectiveness,
    and comprehensive per-share value metrics.

    Core principle: Distinguish between SBC dilution (recurring), W&O dilution
    (one-time), and buyback offsets (capital allocation decision).
    """

    ZERO_THRESHOLD = 0.1  # Million shares

    @staticmethod
    def calculate_sbc_dilution_extended(
        sbc_expense: float | None,
        stock_price: float | None,
        shares_outstanding: float | None,
        sbc_vesting_years: float = 3.0,
        context: CalculationContext | None = None,
    ) -> dict:
        """
        Calculate SBC dilution with full context.

        Returns dict with:
        - dilution_shares: estimated new shares from SBC
        - dilution_percent: as % of shares outstanding
        - annual_sbc_run_rate: implied annual dilution
        """
        warnings = []

        if sbc_expense is None or stock_price is None:
            warnings.append("Missing SBC expense or stock price for dilution calculation")
            return {
                "dilution_shares": None,
                "dilution_percent": None,
                "annual_sbc_run_rate": None,
                "warnings": warnings,
                "calculation_status": "INSUFFICIENT_DATA",
            }

        if stock_price <= 0:
            warnings.append(f"Invalid stock price: ${stock_price}")
            return {
                "dilution_shares": None,
                "dilution_percent": None,
                "annual_sbc_run_rate": None,
                "warnings": warnings,
                "calculation_status": "INSUFFICIENT_DATA",
            }

        dilution_shares = (sbc_expense * sbc_vesting_years) / stock_price
        dilution_percent = None
        annual_run_rate = None

        if shares_outstanding is not None and shares_outstanding > 0:
            dilution_percent = (dilution_shares / shares_outstanding) * 100
            annual_run_rate = dilution_percent / sbc_vesting_years

        return {
            "dilution_shares": dilution_shares,
            "dilution_percent": dilution_percent,
            "annual_sbc_run_rate": annual_run_rate,
            "warnings": warnings,
            "calculation_status": "VALID",
        }

    @staticmethod
    def calculate_warrants_options_dilution_extended(
        in_the_money_instruments: float | None,
        average_exercise_price: float | None,
        stock_price: float | None,
        shares_outstanding: float | None,
        context: CalculationContext | None = None,
    ) -> dict:
        """
        Calculate W&O dilution via treasury stock method.

        Returns dict with:
        - gross_shares_issued: ITM count
        - proceeds_millions: Exercise price × ITM count
        - shares_repurchased: (Proceeds / Stock Price)
        - net_dilution: Gross - Repurchased
        """
        warnings = []

        if (
            in_the_money_instruments is None
            or average_exercise_price is None
            or stock_price is None
        ):
            warnings.append("Missing ITM instruments, exercise price, or stock price")
            return {
                "gross_shares_issued": None,
                "net_dilution": None,
                "dilution_percent": None,
                "warnings": warnings,
                "calculation_status": "INSUFFICIENT_DATA",
            }

        if stock_price <= 0:
            warnings.append(f"Invalid stock price: ${stock_price}")
            return {
                "gross_shares_issued": None,
                "net_dilution": None,
                "dilution_percent": None,
                "warnings": warnings,
                "calculation_status": "INSUFFICIENT_DATA",
            }

        gross_shares = in_the_money_instruments
        proceeds = gross_shares * average_exercise_price
        shares_repurchased = proceeds / stock_price if stock_price > 0 else 0
        net_dilution = max(0, gross_shares - shares_repurchased)

        dilution_percent = None
        if shares_outstanding is not None and shares_outstanding > 0:
            dilution_percent = (net_dilution / shares_outstanding) * 100

        return {
            "gross_shares_issued": gross_shares,
            "proceeds_millions": proceeds,
            "shares_repurchased": shares_repurchased,
            "net_dilution": net_dilution,
            "dilution_percent": dilution_percent,
            "warnings": warnings,
            "calculation_status": "VALID",
        }

    @staticmethod
    def calculate_share_count_cagr(
        shares_beginning: float | None,
        shares_ending: float | None,
        years: float = 1.0,
        context: CalculationContext | None = None,
    ) -> dict:
        """
        Calculate share count CAGR.

        CAGR = (Ending / Beginning)^(1/Years) - 1
        """
        warnings = []

        if shares_beginning is None or shares_ending is None:
            warnings.append("Missing beginning or ending share counts")
            return {
                "cagr_percent": None,
                "warnings": warnings,
                "calculation_status": "INSUFFICIENT_DATA",
            }

        if shares_beginning <= 0:
            warnings.append(f"Invalid beginning share count: {shares_beginning}")
            return {
                "cagr_percent": None,
                "warnings": warnings,
                "calculation_status": "INSUFFICIENT_DATA",
            }

        if years <= 0:
            warnings.append(f"Invalid period: {years} years")
            return {
                "cagr_percent": None,
                "warnings": warnings,
                "calculation_status": "INSUFFICIENT_DATA",
            }

        cagr = ((shares_ending / shares_beginning) ** (1 / years) - 1) * 100

        return {
            "cagr_percent": cagr,
            "warnings": warnings,
            "calculation_status": "VALID",
        }

    @staticmethod
    def calculate_buyback_effectiveness(
        sbc_dilution: float,
        warrant_option_dilution: float,
        shares_repurchased: float,
        context: CalculationContext | None = None,
    ) -> dict:
        """
        Classify buyback effectiveness against dilution sources.
        """
        total_dilution = sbc_dilution + warrant_option_dilution
        net_dilution = total_dilution - shares_repurchased

        if total_dilution == 0:
            effectiveness = BuybackEffectiveness.INSUFFICIENT_DATA
            offset_ratio = 0.0
        elif shares_repurchased == 0:
            effectiveness = BuybackEffectiveness.NET_DILUTION
            offset_ratio = 0.0
        elif shares_repurchased >= total_dilution * 1.2:
            effectiveness = BuybackEffectiveness.STRONG_NET_REDUCTION
            offset_ratio = shares_repurchased / total_dilution if total_dilution > 0 else 0
        elif shares_repurchased >= total_dilution:
            effectiveness = BuybackEffectiveness.MODEST_NET_REDUCTION
            offset_ratio = shares_repurchased / total_dilution
        elif shares_repurchased >= total_dilution * 0.8:
            effectiveness = BuybackEffectiveness.OFFSETTING_SBC
            offset_ratio = shares_repurchased / total_dilution
        else:
            effectiveness = BuybackEffectiveness.INEFFECTIVE_BUYBACK
            offset_ratio = shares_repurchased / total_dilution if total_dilution > 0 else 0

        return {
            "effectiveness": effectiveness,
            "offset_ratio": offset_ratio,
            "net_dilution_after_buyback": net_dilution,
            "calculation_status": "VALID",
        }

    @staticmethod
    def calculate_comprehensive_dilution(
        shares_outstanding_beginning: float | None,
        shares_outstanding_ending: float | None,
        sbc_expense: float | None,
        stock_price: float | None,
        in_the_money_instruments: float | None,
        average_exercise_price: float | None,
        shares_repurchased: float | None,
        repurchase_amount: float | None,
        revenue: float | None,
        years_tracked: float = 1.0,
        sbc_vesting_years: float = 3.0,
        context: CalculationContext | None = None,
    ) -> DilutionMetrics:
        """
        Comprehensive dilution analysis combining all metrics.
        """
        warnings = []
        calculation_status = "VALID"

        # SBC Dilution
        sbc_result = DilutionEngine.calculate_sbc_dilution_extended(
            sbc_expense=sbc_expense,
            stock_price=stock_price,
            shares_outstanding=shares_outstanding_ending,
            sbc_vesting_years=sbc_vesting_years,
            context=context,
        )
        sbc_dilution_shares = sbc_result.get("dilution_shares") or 0.0
        warnings.extend(sbc_result.get("warnings", []))

        # W&O Dilution
        wo_result = DilutionEngine.calculate_warrants_options_dilution_extended(
            in_the_money_instruments=in_the_money_instruments,
            average_exercise_price=average_exercise_price,
            stock_price=stock_price,
            shares_outstanding=shares_outstanding_ending,
            context=context,
        )
        warrant_option_dilution = wo_result.get("net_dilution") or 0.0
        warnings.extend(wo_result.get("warnings", []))

        # Share count CAGR
        cagr_3y = None
        cagr_5y = None
        if shares_outstanding_beginning is not None and shares_outstanding_ending is not None:
            if years_tracked >= 3:
                cagr_3y_result = DilutionEngine.calculate_share_count_cagr(
                    shares_outstanding_beginning, shares_outstanding_ending, 3.0, context
                )
                cagr_3y = cagr_3y_result.get("cagr_percent")

            if years_tracked >= 5:
                cagr_5y_result = DilutionEngine.calculate_share_count_cagr(
                    shares_outstanding_beginning, shares_outstanding_ending, 5.0, context
                )
                cagr_5y = cagr_5y_result.get("cagr_percent")

        # SBC/Revenue ratio
        sbc_to_revenue = None
        if sbc_expense is not None and revenue is not None and revenue > 0:
            sbc_to_revenue = (sbc_expense / revenue) * 100

        # Buyback metrics
        repurchased = shares_repurchased or 0.0
        avg_repurchase_price = None
        if repurchase_amount is not None and repurchased > 0:
            avg_repurchase_price = repurchase_amount / repurchased

        # Buyback effectiveness
        effectiveness_result = DilutionEngine.calculate_buyback_effectiveness(
            sbc_dilution_shares, warrant_option_dilution, repurchased, context
        )
        effectiveness = effectiveness_result.get("effectiveness", BuybackEffectiveness.INSUFFICIENT_DATA)
        offset_ratio = effectiveness_result.get("offset_ratio", 0.0)
        net_dilution_after = effectiveness_result.get("net_dilution_after_buyback", 0.0)

        if sbc_result.get("calculation_status") == "INSUFFICIENT_DATA":
            calculation_status = "INSUFFICIENT_DATA"
        if wo_result.get("calculation_status") == "INSUFFICIENT_DATA":
            calculation_status = "INSUFFICIENT_DATA"

        return DilutionMetrics(
            company_id=context.company_id if context else "UNKNOWN",
            fiscal_year=context.fiscal_year if context else 0,
            calculated_at=datetime.utcnow(),
            shares_outstanding_beginning=shares_outstanding_beginning,
            shares_outstanding_ending=shares_outstanding_ending,
            sbc_dilution_shares=sbc_dilution_shares,
            warrant_option_dilution=warrant_option_dilution,
            shares_repurchased=repurchased,
            net_dilution_after_buyback=net_dilution_after,
            share_count_cagr_3y=cagr_3y,
            share_count_cagr_5y=cagr_5y,
            sbc_expense_millions=sbc_expense,
            revenue_millions=revenue,
            sbc_to_revenue_ratio=sbc_to_revenue,
            total_repurchased_amount_millions=repurchase_amount,
            avg_repurchase_price=avg_repurchase_price,
            buyback_effectiveness=effectiveness,
            buyback_offset_ratio=offset_ratio,
            warnings=warnings,
            calculation_status=calculation_status,
        )
