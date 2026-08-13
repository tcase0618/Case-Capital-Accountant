"""Capital Allocation Ledger with 5Y/10Y/15Y historical tracking and efficiency scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from accountant.calculations.framework import CalculationContext

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class CapitalAllocationEntry:
    """Single year's capital allocation breakdown."""

    fiscal_year: int
    currency: str  # USD, typically

    # Capital deployed (millions)
    capex: float | None  # Capital expenditures (investing)
    acquisitions: float | None  # M&A spending
    dividends_paid: float | None  # Shareholder distributions
    share_buybacks: float | None  # Repurchases
    debt_repaid: float | None  # Debt reduction
    debt_issued: float | None  # Debt increase

    # Operational capital generation
    owner_earnings: float | None  # Operating cash flow minus maintenance capex
    free_cash_flow: float | None  # Operating CF - Total Capex

    # Returns metrics
    roic: float | None  # Return on Invested Capital (%)
    wacc: float | None  # Weighted average cost of capital (%)
    roic_spread: float | None  # ROIC - WACC (basis points above cost)

    # Per-share metrics
    fcf_per_share: float | None
    eps: float | None
    book_value_per_share: float | None

    # Metadata
    warnings: list[str]
    calculation_status: str  # VALID, INSUFFICIENT_DATA


@dataclass(frozen=True)
class CapitalAllocationPeriod:
    """Multi-year aggregated capital allocation."""

    company_id: str
    period_label: str  # "FY2020-FY2024" or "5Y Avg"
    start_fiscal_year: int
    end_fiscal_year: int
    years_count: int

    # Aggregated capital deployment (millions)
    total_capex: float
    total_acquisitions: float
    total_dividends: float
    total_buybacks: float
    total_debt_repaid: float
    total_debt_issued: float

    # Capital allocation mix (% of total capital deployed)
    capex_pct: float  # Capex / Total
    acquisitions_pct: float
    dividends_pct: float
    buybacks_pct: float
    debt_management_pct: float

    # Average annual metrics
    avg_roic: float | None
    avg_wacc: float | None
    avg_roic_spread: float | None
    avg_fcf_per_share: float | None
    avg_eps: float | None
    cagr_fcf_per_share: float | None  # Compound annual growth rate

    # Quality of allocation assessment
    roic_consistently_above_wacc: bool  # True if ROIC > WACC in majority of years
    capital_allocation_score: float  # 0-100 scale (higher = better allocation)

    # Insights
    primary_allocation_strategy: str  # "GROWTH", "INCOME", "BUYBACK", "DELEVERAGING", "BALANCED"
    secondary_allocation: str | None  # Secondary strategy if applicable
    capital_efficiency_comment: str  # Text summary

    # Metadata
    warnings: list[str]
    calculation_status: str


class CapitalAllocationLedger:
    """
    Tracks capital allocation decisions over time with efficiency assessment.

    Core principle: Separate discretionary capital deployment (capex, M&A, dividends,
    buybacks) from financial leverage decisions (debt issued/repaid). Score allocation
    quality based on ROIC vs. WACC spread.
    """

    ROIC_SPREAD_THRESHOLD_BP = 200  # 200 bps = 2% above WACC (value-creating)

    @staticmethod
    def create_entry(
        fiscal_year: int,
        capex: float | None = None,
        acquisitions: float | None = None,
        dividends_paid: float | None = None,
        share_buybacks: float | None = None,
        debt_repaid: float | None = None,
        debt_issued: float | None = None,
        owner_earnings: float | None = None,
        free_cash_flow: float | None = None,
        roic: float | None = None,
        wacc: float | None = None,
        fcf_per_share: float | None = None,
        eps: float | None = None,
        bvps: float | None = None,
        context: CalculationContext | None = None,
    ) -> CapitalAllocationEntry:
        """
        Create single-year capital allocation entry.
        """
        warnings = []
        calculation_status = "VALID"

        # Calculate ROIC spread if both available
        roic_spread = None
        if roic is not None and wacc is not None:
            roic_spread = (roic - wacc) * 100  # Convert to basis points

        # Validate input
        if (
            capex is None
            and acquisitions is None
            and dividends_paid is None
            and share_buybacks is None
        ):
            calculation_status = "INSUFFICIENT_DATA"
            warnings.append("No capital allocation data provided")

        return CapitalAllocationEntry(
            fiscal_year=fiscal_year,
            currency="USD",
            capex=capex,
            acquisitions=acquisitions,
            dividends_paid=dividends_paid,
            share_buybacks=share_buybacks,
            debt_repaid=debt_repaid,
            debt_issued=debt_issued,
            owner_earnings=owner_earnings,
            free_cash_flow=free_cash_flow,
            roic=roic,
            wacc=wacc,
            roic_spread=roic_spread,
            fcf_per_share=fcf_per_share,
            eps=eps,
            book_value_per_share=bvps,
            warnings=warnings,
            calculation_status=calculation_status,
        )

    @staticmethod
    def aggregate_period(
        entries: list[CapitalAllocationEntry],
        company_id: str,
        context: CalculationContext | None = None,
    ) -> CapitalAllocationPeriod:
        """
        Aggregate multiple years into period-level analysis.
        """
        warnings = []
        calculation_status = "VALID"

        if not entries:
            return CapitalAllocationPeriod(
                company_id=company_id,
                period_label="EMPTY",
                start_fiscal_year=0,
                end_fiscal_year=0,
                years_count=0,
                total_capex=0.0,
                total_acquisitions=0.0,
                total_dividends=0.0,
                total_buybacks=0.0,
                total_debt_repaid=0.0,
                total_debt_issued=0.0,
                capex_pct=0.0,
                acquisitions_pct=0.0,
                dividends_pct=0.0,
                buybacks_pct=0.0,
                debt_management_pct=0.0,
                avg_roic=None,
                avg_wacc=None,
                avg_roic_spread=None,
                avg_fcf_per_share=None,
                avg_eps=None,
                cagr_fcf_per_share=None,
                roic_consistently_above_wacc=False,
                capital_allocation_score=0.0,
                primary_allocation_strategy="UNKNOWN",
                secondary_allocation=None,
                capital_efficiency_comment="Insufficient data",
                warnings=["No entries provided"],
                calculation_status="INSUFFICIENT_DATA",
            )

        # Sort by year
        sorted_entries = sorted(entries, key=lambda e: e.fiscal_year)
        start_year = sorted_entries[0].fiscal_year
        end_year = sorted_entries[-1].fiscal_year
        years_count = len(sorted_entries)

        # Aggregate totals
        total_capex = sum(e.capex or 0.0 for e in sorted_entries)
        total_acquisitions = sum(e.acquisitions or 0.0 for e in sorted_entries)
        total_dividends = sum(e.dividends_paid or 0.0 for e in sorted_entries)
        total_buybacks = sum(e.share_buybacks or 0.0 for e in sorted_entries)
        total_debt_repaid = sum(e.debt_repaid or 0.0 for e in sorted_entries)
        total_debt_issued = sum(e.debt_issued or 0.0 for e in sorted_entries)

        # Capital allocation mix
        total_deployed = (
            total_capex + total_acquisitions + total_dividends + total_buybacks
        )
        capex_pct = (total_capex / total_deployed * 100) if total_deployed > 0 else 0
        acquisitions_pct = (total_acquisitions / total_deployed * 100) if total_deployed > 0 else 0
        dividends_pct = (total_dividends / total_deployed * 100) if total_deployed > 0 else 0
        buybacks_pct = (total_buybacks / total_deployed * 100) if total_deployed > 0 else 0
        debt_management = total_debt_repaid - total_debt_issued
        debt_management_pct = (
            (debt_management / total_deployed * 100) if total_deployed > 0 else 0
        )

        # Average annual metrics
        roic_values = [e.roic for e in sorted_entries if e.roic is not None]
        avg_roic = sum(roic_values) / len(roic_values) if roic_values else None

        wacc_values = [e.wacc for e in sorted_entries if e.wacc is not None]
        avg_wacc = sum(wacc_values) / len(wacc_values) if wacc_values else None

        spread_values = [e.roic_spread for e in sorted_entries if e.roic_spread is not None]
        avg_roic_spread = sum(spread_values) / len(spread_values) if spread_values else None

        fcf_ps_values = [e.fcf_per_share for e in sorted_entries if e.fcf_per_share is not None]
        avg_fcf_per_share = sum(fcf_ps_values) / len(fcf_ps_values) if fcf_ps_values else None

        eps_values = [e.eps for e in sorted_entries if e.eps is not None]
        avg_eps = sum(eps_values) / len(eps_values) if eps_values else None

        # CAGR of FCF per share
        cagr_fcf_ps = None
        if len(fcf_ps_values) >= 2 and fcf_ps_values[0] > 0:
            cagr_fcf_ps = (
                ((fcf_ps_values[-1] / fcf_ps_values[0]) ** (1 / (len(fcf_ps_values) - 1)) - 1) * 100
            )

        # ROIC > WACC analysis
        roic_above_wacc_count = 0
        for e in sorted_entries:
            if e.roic is not None and e.wacc is not None and e.roic > e.wacc:
                roic_above_wacc_count += 1

        roic_consistently_above = roic_above_wacc_count >= (years_count * 0.66)

        # Capital allocation score (0-100)
        score = 0.0
        if avg_roic_spread is not None and avg_roic_spread > CapitalAllocationLedger.ROIC_SPREAD_THRESHOLD_BP:
            score += 50  # Strong ROIC spread
        elif avg_roic_spread is not None and avg_roic_spread > 0:
            score += 30  # Positive ROIC spread
        elif avg_roic_spread is not None:
            score += 0  # Negative ROIC spread

        if roic_consistently_above:
            score += 30  # Consistent outperformance
        elif roic_above_wacc_count > 0:
            score += 15  # Some years above WACC

        if cagr_fcf_ps is not None and cagr_fcf_ps > 10:
            score += 20  # Strong FCF growth
        elif cagr_fcf_ps is not None and cagr_fcf_ps > 0:
            score += 10  # Positive FCF growth

        score = min(100, max(0, score))

        # Determine primary strategy
        if capex_pct > 40:
            primary_strategy = "GROWTH"
            secondary = None
        elif acquisitions_pct > 30:
            primary_strategy = "M&A"
            secondary = None
        elif buybacks_pct > 30:
            primary_strategy = "BUYBACK"
            secondary = "DELEVERAGING" if debt_management < 0 else None
        elif dividends_pct > 30:
            primary_strategy = "INCOME"
            secondary = "DELEVERAGING" if debt_management < 0 else None
        elif debt_management < -total_deployed * 0.2:
            primary_strategy = "DELEVERAGING"
            secondary = None
        else:
            primary_strategy = "BALANCED"
            secondary = None

        # Efficiency comment
        if score >= 70:
            efficiency_comment = "Strong capital allocation with consistent value creation above WACC"
        elif score >= 50:
            efficiency_comment = "Moderate capital allocation; some years exceed cost of capital"
        elif score >= 30:
            efficiency_comment = "Mixed capital allocation results; periodic value destruction"
        else:
            efficiency_comment = "Weak capital allocation with returns below cost of capital"

        period_label = f"FY{start_year}-FY{end_year}"

        return CapitalAllocationPeriod(
            company_id=company_id,
            period_label=period_label,
            start_fiscal_year=start_year,
            end_fiscal_year=end_year,
            years_count=years_count,
            total_capex=total_capex,
            total_acquisitions=total_acquisitions,
            total_dividends=total_dividends,
            total_buybacks=total_buybacks,
            total_debt_repaid=total_debt_repaid,
            total_debt_issued=total_debt_issued,
            capex_pct=capex_pct,
            acquisitions_pct=acquisitions_pct,
            dividends_pct=dividends_pct,
            buybacks_pct=buybacks_pct,
            debt_management_pct=debt_management_pct,
            avg_roic=avg_roic,
            avg_wacc=avg_wacc,
            avg_roic_spread=avg_roic_spread,
            avg_fcf_per_share=avg_fcf_per_share,
            avg_eps=avg_eps,
            cagr_fcf_per_share=cagr_fcf_ps,
            roic_consistently_above_wacc=roic_consistently_above,
            capital_allocation_score=score,
            primary_allocation_strategy=primary_strategy,
            secondary_allocation=secondary,
            capital_efficiency_comment=efficiency_comment,
            warnings=warnings,
            calculation_status=calculation_status,
        )
