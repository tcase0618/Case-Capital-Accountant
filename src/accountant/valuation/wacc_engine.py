"""WACC calculation engine: cost of equity, cost of debt, capital structure."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CapitalStructureType(StrEnum):
    """Capital structure classification."""

    EQUITY_HEAVY = "EQUITY_HEAVY"  # Equity >75%
    BALANCED = "BALANCED"  # 40%-60% equity
    DEBT_HEAVY = "DEBT_HEAVY"  # Debt >60%
    NO_DEBT = "NO_DEBT"


@dataclass(frozen=True)
class CostOfEquityComponents:
    """Components of cost of equity calculation."""

    risk_free_rate: float | None  # e.g., 10Y Treasury yield
    equity_risk_premium: float | None  # Market risk premium
    beta: float | None  # Company systematic risk
    company_specific_premium: float | None  # e.g., small-cap, illiquidity
    cost_of_equity: float | None  # Re = Rf + β(Rm - Rf)
    formula_version: str


@dataclass(frozen=True)
class CostOfDebtComponents:
    """Components of cost of debt calculation."""

    debt_amount_usd: float | None
    interest_expense_usd: float | None
    tax_rate: float | None
    pre_tax_cost_of_debt: float | None  # Interest Expense / Debt
    tax_shield_rate: float | None  # (1 - Tax Rate)
    after_tax_cost_of_debt: float | None  # Pre-tax × (1 - Tax Rate)
    formula_version: str


@dataclass(frozen=True)
class CapitalStructure:
    """Capital structure composition."""

    total_debt_usd: float | None
    total_equity_usd: float | None
    total_capital_usd: float | None
    debt_weight: float | None  # D / (D + E)
    equity_weight: float | None  # E / (D + E)
    capital_structure_type: CapitalStructureType | None


@dataclass(frozen=True)
class WAACResult:
    """Complete WACC calculation result."""

    company_id: str
    fiscal_year: int
    as_of_date: str

    # Components
    cost_of_equity_components: CostOfEquityComponents
    cost_of_debt_components: CostOfDebtComponents
    capital_structure: CapitalStructure

    # WACC result
    wacc: float | None  # WACC = (E/V × Re) + (D/V × Rd × (1-Tc))

    # Sensitivities
    wacc_if_beta_increases_20pct: float | None
    wacc_if_risk_premium_increases_100bps: float | None
    wacc_if_debt_weight_to_50pct: float | None

    # Quality
    has_sufficient_data: bool
    warnings: list[str]

    formula_version: str  # WACC_V1, etc.
    calculated_at: str


class WACCEngine:
    """
    Deterministic WACC engine for discount rate calculation.

    Uses explicit assumptions:
    - Risk-free rate from 10Y Treasury (or 3Y/5Y)
    - Equity risk premium 5-7% (fixed)
    - Beta from regression (or industry average)
    - Tax rate from most recent year
    - Debt from balance sheet (explicit, no guessing)
    """

    WACC_FORMULA_VERSION = "WACC_V1"
    DEFAULT_EQUITY_RISK_PREMIUM = 0.06  # 6%
    DEFAULT_RISK_FREE_RATE = 0.045  # 4.5% (10Y Treasury)
    DEFAULT_BETA = 1.0
    DEFAULT_TAX_RATE = 0.21

    @staticmethod
    def calculate_cost_of_equity(
        risk_free_rate: float | None = None,
        beta: float | None = None,
        equity_risk_premium: float | None = None,
        company_specific_premium: float | None = None,
    ) -> CostOfEquityComponents:
        """
        Calculate cost of equity using CAPM.

        Re = Rf + β(Rm - Rf) + CSP
        """
        rf = risk_free_rate or WACCEngine.DEFAULT_RISK_FREE_RATE
        b = beta or WACCEngine.DEFAULT_BETA
        erp = equity_risk_premium or WACCEngine.DEFAULT_EQUITY_RISK_PREMIUM
        csp = company_specific_premium or 0.0

        re = rf + b * erp + csp

        return CostOfEquityComponents(
            risk_free_rate=rf,
            equity_risk_premium=erp,
            beta=b,
            company_specific_premium=csp if csp > 0 else None,
            cost_of_equity=re,
            formula_version=WACCEngine.WACC_FORMULA_VERSION,
        )

    @staticmethod
    def calculate_cost_of_debt(
        debt_amount_usd: float | None,
        interest_expense_usd: float | None,
        tax_rate: float | None = None,
    ) -> CostOfDebtComponents:
        """
        Calculate after-tax cost of debt.

        Rd_after_tax = (Interest Expense / Debt) × (1 - Tax Rate)
        """
        if not debt_amount_usd or debt_amount_usd <= 0:
            return CostOfDebtComponents(
                debt_amount_usd=None,
                interest_expense_usd=None,
                tax_rate=None,
                pre_tax_cost_of_debt=None,
                tax_shield_rate=None,
                after_tax_cost_of_debt=None,
                formula_version=WACCEngine.WACC_FORMULA_VERSION,
            )

        if not interest_expense_usd or interest_expense_usd <= 0:
            return CostOfDebtComponents(
                debt_amount_usd=debt_amount_usd,
                interest_expense_usd=interest_expense_usd,
                tax_rate=None,
                pre_tax_cost_of_debt=None,
                tax_shield_rate=None,
                after_tax_cost_of_debt=None,
                formula_version=WACCEngine.WACC_FORMULA_VERSION,
            )

        pre_tax_rd = interest_expense_usd / debt_amount_usd
        tr = tax_rate or WACCEngine.DEFAULT_TAX_RATE
        tax_shield = 1.0 - tr
        after_tax_rd = pre_tax_rd * tax_shield

        return CostOfDebtComponents(
            debt_amount_usd=debt_amount_usd,
            interest_expense_usd=interest_expense_usd,
            tax_rate=tr,
            pre_tax_cost_of_debt=pre_tax_rd,
            tax_shield_rate=tax_shield,
            after_tax_cost_of_debt=after_tax_rd,
            formula_version=WACCEngine.WACC_FORMULA_VERSION,
        )

    @staticmethod
    def classify_capital_structure(
        debt_weight: float | None,
    ) -> CapitalStructureType | None:
        """Classify capital structure based on debt weight."""
        if debt_weight is None:
            return None
        if debt_weight > 0.60:
            return CapitalStructureType.DEBT_HEAVY
        elif debt_weight >= 0.40:
            return CapitalStructureType.BALANCED
        elif debt_weight > 0.0:
            return CapitalStructureType.EQUITY_HEAVY
        else:
            return CapitalStructureType.NO_DEBT

    @staticmethod
    def calculate_wacc(
        company_id: str,
        fiscal_year: int,
        as_of_date: str,
        market_cap_usd: float | None,
        debt_amount_usd: float | None,
        interest_expense_usd: float | None,
        tax_rate: float | None = None,
        risk_free_rate: float | None = None,
        beta: float | None = None,
        equity_risk_premium: float | None = None,
    ) -> WAACResult:
        """
        Calculate full WACC.

        WACC = (E/V × Re) + (D/V × Rd × (1-Tc))
        """
        # Market cap as proxy for equity value
        equity_val = market_cap_usd or 0.0
        debt_val = debt_amount_usd or 0.0
        total_val = equity_val + debt_val

        # Calculate weights
        eq_weight = None
        debt_weight = None
        if total_val > 0:
            eq_weight = equity_val / total_val
            debt_weight = debt_val / total_val

        capital_struct = CapitalStructure(
            total_debt_usd=debt_val if debt_val > 0 else None,
            total_equity_usd=equity_val if equity_val > 0 else None,
            total_capital_usd=total_val if total_val > 0 else None,
            debt_weight=debt_weight,
            equity_weight=eq_weight,
            capital_structure_type=WACCEngine.classify_capital_structure(debt_weight),
        )

        # Cost of equity
        coe_components = WACCEngine.calculate_cost_of_equity(
            risk_free_rate=risk_free_rate,
            beta=beta,
            equity_risk_premium=equity_risk_premium,
        )

        # Cost of debt
        cod_components = WACCEngine.calculate_cost_of_debt(
            debt_amount_usd=debt_val if debt_val > 0 else None,
            interest_expense_usd=interest_expense_usd,
            tax_rate=tax_rate,
        )

        # Calculate WACC
        wacc = None
        warnings = []
        has_sufficient_data = True

        if eq_weight is None:
            warnings.append("Missing market cap; cannot calculate equity weight")
            has_sufficient_data = False
        if coe_components.cost_of_equity is None:
            warnings.append("Missing cost of equity components")
            has_sufficient_data = False
        elif total_val > 0 and coe_components.cost_of_equity > 0:
            # WACC = (E/V × Re) + (D/V × Rd_after_tax)
            equity_contribution = eq_weight * coe_components.cost_of_equity if eq_weight else 0.0
            debt_contribution = (
                debt_weight * cod_components.after_tax_cost_of_debt
                if debt_weight and cod_components.after_tax_cost_of_debt
                else 0.0
            )
            wacc = equity_contribution + debt_contribution

        # Sensitivities
        wacc_beta_20pct = None
        wacc_erp_100bps = None
        wacc_debt_50pct = None

        if wacc and coe_components.cost_of_equity:
            # Beta +20%
            adjusted_re = (
                coe_components.risk_free_rate +
                (coe_components.beta * 1.20) * (coe_components.equity_risk_premium or WACCEngine.DEFAULT_EQUITY_RISK_PREMIUM)
            )
            wacc_beta_20pct = (
                eq_weight * adjusted_re
                + debt_weight * cod_components.after_tax_cost_of_debt
                if eq_weight and debt_weight
                else wacc
            )

            # ERP +100bps
            adjusted_re_erp = (
                coe_components.risk_free_rate +
                coe_components.beta * ((coe_components.equity_risk_premium or WACCEngine.DEFAULT_EQUITY_RISK_PREMIUM) + 0.01)
            )
            wacc_erp_100bps = (
                eq_weight * adjusted_re_erp
                + debt_weight * cod_components.after_tax_cost_of_debt
                if eq_weight and debt_weight
                else wacc
            )

            # Debt weight to 50%
            if total_val > 0:
                equity_contrib_50 = 0.50 * coe_components.cost_of_equity
                debt_contrib_50 = 0.50 * cod_components.after_tax_cost_of_debt if cod_components.after_tax_cost_of_debt else 0.0
                wacc_debt_50pct = equity_contrib_50 + debt_contrib_50

        return WAACResult(
            company_id=company_id,
            fiscal_year=fiscal_year,
            as_of_date=as_of_date,
            cost_of_equity_components=coe_components,
            cost_of_debt_components=cod_components,
            capital_structure=capital_struct,
            wacc=wacc,
            wacc_if_beta_increases_20pct=wacc_beta_20pct,
            wacc_if_risk_premium_increases_100bps=wacc_erp_100bps,
            wacc_if_debt_weight_to_50pct=wacc_debt_50pct,
            has_sufficient_data=has_sufficient_data,
            warnings=warnings,
            formula_version=WACCEngine.WACC_FORMULA_VERSION,
            calculated_at=datetime.now().isoformat(),
        )
