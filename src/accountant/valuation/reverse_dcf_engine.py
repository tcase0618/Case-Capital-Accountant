"""Reverse DCF engine: solve for market-implied assumptions given current price."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class SolveVariable(StrEnum):
    """Variable to solve for in reverse DCF."""

    REVENUE_GROWTH = "REVENUE_GROWTH"
    OPERATING_MARGIN = "OPERATING_MARGIN"
    FCF_MARGIN = "FCF_MARGIN"
    REINVESTMENT_RATE = "REINVESTMENT_RATE"
    ROIC = "ROIC"
    TERMINAL_GROWTH_RATE = "TERMINAL_GROWTH_RATE"
    DISCOUNT_RATE = "DISCOUNT_RATE"


class SolveStatus(StrEnum):
    """Status of reverse DCF solve."""

    SOLVED = "SOLVED"
    FAILED_NO_SOLUTION = "FAILED_NO_SOLUTION"
    FAILED_MULTIPLE_SOLUTIONS = "FAILED_MULTIPLE_SOLUTIONS"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ReverseAssumption:
    """Single market-implied assumption."""

    variable: SolveVariable
    market_implied_value: float | None
    reasonable: bool  # True if within normal historical ranges
    reasonableness_note: str  # Why/why not reasonable


@dataclass(frozen=True)
class ReverseDCFResult:
    """Reverse DCF result: given price, what assumptions justify it."""

    company_id: str
    fiscal_year: int
    as_of_date: str

    # Market input
    market_price_per_share: float | None
    shares_outstanding: float | None
    market_cap_usd: float | None

    # Solving parameters
    solve_variable: SolveVariable
    base_assumptions: dict[str, float | None]  # Known assumptions

    # Result
    solve_status: SolveStatus
    market_implied_assumption: ReverseAssumption | None

    # Interpretation
    consensus_assumption: float | None  # E.g., analyst consensus growth
    upside_to_consensus: float | None  # %-points difference
    implied_vs_consensus_assessment: str

    # Full set (solve for multiple variables)
    all_implied_assumptions: list[ReverseAssumption]

    # Quality
    warnings: list[str]

    formula_version: str  # REVERSE_DCF_V1, etc.
    calculated_at: str


class ReverseDCFEngine:
    """
    Reverse DCF solver: given market price, determine which assumptions justify it.

    Example: Market price is $100. Company FCF this year is $10/share.
    Solve: What terminal growth rate, discount rate, or margin assumes $100 fair value?

    Methodology:
    1. Build DCF with known inputs (historical FCF, WACC, forecast period)
    2. For each variable, solve numerically for the value that produces market price
    3. Assess if solved value is reasonable (within 2σ of historical/peer range)
    4. Compare to consensus/guidance
    """

    REVERSE_DCF_FORMULA_VERSION = "REVERSE_DCF_V1"

    # Reasonableness bounds (historical/peer-derived)
    TERMINAL_GROWTH_MIN = -0.01  # -1%
    TERMINAL_GROWTH_MAX = 0.04  # 4% (long-term GDP+inflation)
    OPERATING_MARGIN_MIN = 0.00  # 0%
    OPERATING_MARGIN_MAX = 0.50  # 50%
    REVENUE_GROWTH_MIN = -0.20  # -20% (severe decline)
    REVENUE_GROWTH_MAX = 0.40  # 40% (high growth)
    DISCOUNT_RATE_MIN = 0.05  # 5% (very low risk)
    DISCOUNT_RATE_MAX = 0.25  # 25% (high risk)
    ROIC_MIN = 0.00  # 0%
    ROIC_MAX = 0.50  # 50% (extremely high)

    @staticmethod
    def solve_for_terminal_growth(
        fcf_per_share: float,
        market_price_per_share: float,
        discount_rate: float,
        forecast_horizon: int = 10,
    ) -> tuple[float | None, bool]:
        """
        Solve for terminal growth rate.

        Given: FCF, market price, discount rate
        Find: terminal growth that produces market price

        Solve: Price = (FCF × PV annuity) + (Terminal Value / (1+r)^n)
        Terminal Value = FCF_final × (1+g) / (r - g)
        """
        if not fcf_per_share or fcf_per_share <= 0 or not market_price_per_share:
            return (None, False)

        # Binary search for terminal growth
        g_low = ReverseDCFEngine.TERMINAL_GROWTH_MIN
        g_high = ReverseDCFEngine.TERMINAL_GROWTH_MAX

        # Iterative solve
        for _ in range(20):  # 20 iterations for convergence
            g_mid = (g_low + g_high) / 2.0
            if discount_rate <= g_mid:  # Prevent negative denominator
                g_high = g_mid
                continue

            # Calculate implied price with g_mid
            pv_fcf = 0.0
            for i in range(forecast_horizon):
                pv_fcf += fcf_per_share / ((1.0 + discount_rate) ** (i + 1))

            terminal_fcf = fcf_per_share * ((1.0 + g_mid) ** forecast_horizon)
            terminal_value = terminal_fcf * (1.0 + g_mid) / (discount_rate - g_mid)
            pv_terminal = terminal_value / ((1.0 + discount_rate) ** forecast_horizon)
            implied_price = pv_fcf + pv_terminal

            # Adjust search based on difference
            if implied_price < market_price_per_share:
                g_low = g_mid  # Need higher growth
            else:
                g_high = g_mid  # Need lower growth

            # Convergence check
            if abs(implied_price - market_price_per_share) < 0.01:
                break

        solved_g = g_mid
        reasonable = ReverseDCFEngine.TERMINAL_GROWTH_MIN <= solved_g <= ReverseDCFEngine.TERMINAL_GROWTH_MAX
        return (solved_g, reasonable)

    @staticmethod
    def solve_for_discount_rate(
        fcf_per_share: float,
        market_price_per_share: float,
        terminal_growth: float,
        forecast_horizon: int = 10,
    ) -> tuple[float | None, bool]:
        """
        Solve for discount rate (WACC).

        Given: FCF, market price, terminal growth
        Find: discount rate that produces market price
        """
        if not fcf_per_share or fcf_per_share <= 0 or not market_price_per_share:
            return (None, False)

        # Binary search for discount rate
        r_low = 0.01
        r_high = 0.30

        for _ in range(20):
            r_mid = (r_low + r_high) / 2.0
            if r_mid <= terminal_growth:  # Must have r > g
                r_low = r_mid
                continue

            # Calculate implied price with r_mid
            pv_fcf = 0.0
            for i in range(forecast_horizon):
                pv_fcf += fcf_per_share / ((1.0 + r_mid) ** (i + 1))

            terminal_fcf = fcf_per_share * ((1.0 + terminal_growth) ** forecast_horizon)
            terminal_value = terminal_fcf * (1.0 + terminal_growth) / (r_mid - terminal_growth)
            pv_terminal = terminal_value / ((1.0 + r_mid) ** forecast_horizon)
            implied_price = pv_fcf + pv_terminal

            # Adjust search
            if implied_price > market_price_per_share:
                r_low = r_mid  # Need higher discount rate
            else:
                r_high = r_mid  # Need lower discount rate

            # Convergence
            if abs(implied_price - market_price_per_share) < 0.01:
                break

        solved_r = r_mid
        reasonable = ReverseDCFEngine.DISCOUNT_RATE_MIN <= solved_r <= ReverseDCFEngine.DISCOUNT_RATE_MAX
        return (solved_r, reasonable)

    @staticmethod
    def solve_for_operating_margin(
        revenue_growth_rate: float,
        fcf_conversion: float,
        market_price_per_share: float,
        discount_rate: float,
        current_fcf_per_share: float,
        forecast_horizon: int = 10,
    ) -> tuple[float | None, bool]:
        """
        Solve for target operating margin.

        Given: revenue growth, FCF conversion, market price, discount rate
        Find: operating margin that justifies price

        Simplified: FCF grows at revenue growth rate until convergence to target margin
        """
        if not market_price_per_share or not current_fcf_per_share or current_fcf_per_share <= 0:
            return (None, False)

        # Binary search for margin
        margin_low = ReverseDCFEngine.OPERATING_MARGIN_MIN
        margin_high = ReverseDCFEngine.OPERATING_MARGIN_MAX

        for _ in range(20):
            margin_mid = (margin_low + margin_high) / 2.0

            # Project FCF with converging margin
            pv = 0.0
            fcf = current_fcf_per_share
            for i in range(forecast_horizon):
                fcf = current_fcf_per_share * ((1.0 + revenue_growth_rate) ** (i + 1))
                pv += fcf / ((1.0 + discount_rate) ** (i + 1))

            # Terminal value
            terminal_fcf = current_fcf_per_share * ((1.0 + revenue_growth_rate) ** forecast_horizon)
            terminal_value = terminal_fcf * 1.025 / (discount_rate - 0.025)  # Default TG
            pv_terminal = terminal_value / ((1.0 + discount_rate) ** forecast_horizon)
            implied_price = pv + pv_terminal

            # Adjust
            if implied_price < market_price_per_share:
                margin_high = margin_mid
            else:
                margin_low = margin_mid

            if abs(implied_price - market_price_per_share) < 0.01:
                break

        solved_margin = margin_mid
        reasonable = ReverseDCFEngine.OPERATING_MARGIN_MIN <= solved_margin <= ReverseDCFEngine.OPERATING_MARGIN_MAX
        return (solved_margin, reasonable)

    @staticmethod
    def calculate_reverse_dcf(
        company_id: str,
        fiscal_year: int,
        as_of_date: str,
        market_price_per_share: float | None,
        shares_outstanding: float | None,
        current_fcf_per_share: float | None,
        solve_variable: SolveVariable = SolveVariable.TERMINAL_GROWTH_RATE,
        discount_rate: float | None = None,
        terminal_growth: float | None = None,
        consensus_assumption: float | None = None,
    ) -> ReverseDCFResult:
        """
        Run reverse DCF: given price, solve for assumptions.
        """
        market_cap = None
        if market_price_per_share and shares_outstanding and shares_outstanding > 0:
            market_cap = market_price_per_share * shares_outstanding

        warnings = []
        status = SolveStatus.INSUFFICIENT_DATA
        solved_assumption = None
        all_assumptions = []

        if not market_price_per_share or not current_fcf_per_share or current_fcf_per_share <= 0:
            warnings.append("Missing market price or current FCF")
        else:
            # Solve for requested variable
            if solve_variable == SolveVariable.TERMINAL_GROWTH_RATE:
                if not discount_rate:
                    discount_rate = 0.10  # Default
                solved_g, reasonable = ReverseDCFEngine.solve_for_terminal_growth(
                    fcf_per_share=current_fcf_per_share,
                    market_price_per_share=market_price_per_share,
                    discount_rate=discount_rate,
                )
                if solved_g is not None:
                    solved_assumption = ReverseAssumption(
                        variable=SolveVariable.TERMINAL_GROWTH_RATE,
                        market_implied_value=solved_g,
                        reasonable=reasonable,
                        reasonableness_note="Within 2.5%-4.0% GDP range" if reasonable else "Outside historical bounds",
                    )
                    status = SolveStatus.SOLVED if reasonable else SolveStatus.OUT_OF_BOUNDS
                else:
                    status = SolveStatus.FAILED_NO_SOLUTION

            elif solve_variable == SolveVariable.DISCOUNT_RATE:
                if not terminal_growth:
                    terminal_growth = 0.025  # Default
                solved_r, reasonable = ReverseDCFEngine.solve_for_discount_rate(
                    fcf_per_share=current_fcf_per_share,
                    market_price_per_share=market_price_per_share,
                    terminal_growth=terminal_growth,
                )
                if solved_r is not None:
                    solved_assumption = ReverseAssumption(
                        variable=SolveVariable.DISCOUNT_RATE,
                        market_implied_value=solved_r,
                        reasonable=reasonable,
                        reasonableness_note="Within 5%-25% range" if reasonable else "Outside historical bounds",
                    )
                    status = SolveStatus.SOLVED if reasonable else SolveStatus.OUT_OF_BOUNDS
                else:
                    status = SolveStatus.FAILED_NO_SOLUTION

            all_assumptions.append(solved_assumption) if solved_assumption else None

        # Compare to consensus
        upside = None
        assessment = ""
        if solved_assumption and consensus_assumption:
            upside = (solved_assumption.market_implied_value - consensus_assumption) * 100
            if upside > 5:
                assessment = "Market pricing in lower returns than consensus"
            elif upside < -5:
                assessment = "Market pricing in higher returns than consensus"
            else:
                assessment = "Market aligned with consensus"

        return ReverseDCFResult(
            company_id=company_id,
            fiscal_year=fiscal_year,
            as_of_date=as_of_date,
            market_price_per_share=market_price_per_share,
            shares_outstanding=shares_outstanding,
            market_cap_usd=market_cap,
            solve_variable=solve_variable,
            base_assumptions={
                "discount_rate": discount_rate,
                "terminal_growth": terminal_growth,
                "current_fcf_per_share": current_fcf_per_share,
            },
            solve_status=status,
            market_implied_assumption=solved_assumption,
            consensus_assumption=consensus_assumption,
            upside_to_consensus=upside,
            implied_vs_consensus_assessment=assessment,
            all_implied_assumptions=all_assumptions,
            warnings=warnings,
            formula_version=ReverseDCFEngine.REVERSE_DCF_FORMULA_VERSION,
            calculated_at=datetime.now().isoformat(),
        )
