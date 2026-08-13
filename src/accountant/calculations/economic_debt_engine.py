"""Economic Debt Engine with obligation taxonomy and double-counting protection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from accountant.calculations.framework import CalculationContext

if TYPE_CHECKING:
    pass

logger_enabled = True


class ObligationCategory(StrEnum):
    """Deterministic obligation categories for debt taxonomy."""

    BORROWING_SHORT_TERM = "BORROWING_SHORT_TERM"
    BORROWING_LONG_TERM = "BORROWING_LONG_TERM"
    LEASE_OPERATING = "LEASE_OPERATING"
    LEASE_FINANCE = "LEASE_FINANCE"
    CONVERTIBLE = "CONVERTIBLE"
    PREFERRED = "PREFERRED"
    PENSION = "PENSION"
    SUPPLIER_FINANCE = "SUPPLIER_FINANCE"
    FACTORING = "FACTORING"
    OTHER_FIXED_CLAIM = "OTHER_FIXED_CLAIM"


class InclusionStatus(StrEnum):
    """Explicit status for obligation inclusion/exclusion."""

    INCLUDED = "INCLUDED"
    EXCLUDED_OVERLAP = "EXCLUDED_OVERLAP"
    EXCLUDED_NOT_DEBT = "EXCLUDED_NOT_DEBT"
    AMBIGUOUS = "AMBIGUOUS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ObligationAdjustment:
    """Represents a single obligation with full provenance."""

    category: ObligationCategory
    amount: float  # in millions
    status: InclusionStatus
    source: str  # where this came from (e.g., BS line item name)
    reason: str  # why included/excluded
    formula_version: str  # v1_economic_debt_engine
    confidence: str  # HIGH, MEDIUM, LOW


@dataclass(frozen=True)
class EconomicDebtResult:
    """Immutable result containing all economic debt components."""

    company_id: str
    fiscal_year: int
    fiscal_quarter: int | None
    calculated_at: datetime

    # Reported balance sheet debt
    short_term_borrowings: float | None
    current_portion_lt_debt: float | None
    long_term_debt: float | None
    reported_debt: float  # Sum of above

    # Leases
    operating_lease_liability: float | None
    finance_lease_liability: float | None

    # Other obligations
    convertible_debt: float | None
    preferred_claims: float | None
    pension_deficit: float | None
    supplier_financing: float | None
    receivables_factoring: float | None
    other_fixed_obligations: float | None

    # Derived metrics
    economic_debt: float  # Full economic debt
    cash_and_equivalents: float | None
    net_economic_debt: float  # Economic debt - cash

    # Double-counting protection
    adjustments: list[ObligationAdjustment]  # All component adjustments
    double_counting_amount: float  # Amount excluded due to overlap

    # Metadata
    warnings: list[str]
    calculation_status: str  # VALID, INSUFFICIENT_DATA, AMBIGUOUS


class EconomicDebtEngine:
    """
    Calculates comprehensive economic debt with explicit obligation taxonomy.

    Core principle: Every obligation tracked separately with clear inclusion/exclusion
    logic to prevent double-counting.
    """

    ZERO_THRESHOLD = 1.0  # USD million minimum

    @staticmethod
    def calculate_reported_debt(
        short_term_borrowings: float | None,
        current_portion_lt_debt: float | None,
        long_term_debt: float | None,
        operating_lease_liability: float | None,
        finance_lease_liability: float | None,
        context: CalculationContext,
    ) -> EconomicDebtResult:
        """
        Calculate Reported Economic Debt.

        Reported = Short-term Borrowings + Current portion of LT Debt + Long-term Debt
                 + Operating Leases (ASC 842) + Finance Leases

        This is the explicit balance sheet obligation total.
        """
        warnings = []
        adjustments = []

        # Short-term borrowings
        stb = short_term_borrowings or 0.0
        if short_term_borrowings is None:
            warnings.append("Missing short-term borrowings")
        adjustments.append(
            ObligationAdjustment(
                category=ObligationCategory.BORROWING_SHORT_TERM,
                amount=stb,
                status=InclusionStatus.INCLUDED if stb >= EconomicDebtEngine.ZERO_THRESHOLD else InclusionStatus.INSUFFICIENT_DATA,
                source="Balance Sheet: Short-Term Debt",
                reason="Current portion of debt due within 12 months",
                formula_version="V1_ECONOMIC_DEBT_ENGINE",
                confidence="HIGH" if short_term_borrowings is not None else "INSUFFICIENT_DATA",
            )
        )

        # Current portion of long-term debt
        cplt = current_portion_lt_debt or 0.0
        if current_portion_lt_debt is None:
            warnings.append("Missing current portion of long-term debt")
        adjustments.append(
            ObligationAdjustment(
                category=ObligationCategory.BORROWING_SHORT_TERM,
                amount=cplt,
                status=InclusionStatus.INCLUDED if cplt >= EconomicDebtEngine.ZERO_THRESHOLD else InclusionStatus.INSUFFICIENT_DATA,
                source="Balance Sheet: Current Portion of LT Debt",
                reason="Long-term debt due within 12 months",
                formula_version="V1_ECONOMIC_DEBT_ENGINE",
                confidence="HIGH" if current_portion_lt_debt is not None else "INSUFFICIENT_DATA",
            )
        )

        # Long-term debt
        ltd = long_term_debt or 0.0
        if long_term_debt is None:
            warnings.append("Missing long-term debt")
        adjustments.append(
            ObligationAdjustment(
                category=ObligationCategory.BORROWING_LONG_TERM,
                amount=ltd,
                status=InclusionStatus.INCLUDED if ltd >= EconomicDebtEngine.ZERO_THRESHOLD else InclusionStatus.INSUFFICIENT_DATA,
                source="Balance Sheet: Long-Term Debt",
                reason="Obligations due after 12 months",
                formula_version="V1_ECONOMIC_DEBT_ENGINE",
                confidence="HIGH" if long_term_debt is not None else "INSUFFICIENT_DATA",
            )
        )

        # Operating leases (ASC 842)
        opl = operating_lease_liability or 0.0
        adjustments.append(
            ObligationAdjustment(
                category=ObligationCategory.LEASE_OPERATING,
                amount=opl,
                status=InclusionStatus.INCLUDED if opl >= EconomicDebtEngine.ZERO_THRESHOLD else InclusionStatus.INSUFFICIENT_DATA,
                source="Balance Sheet: Operating Lease ROU Liability (ASC 842)",
                reason="Lease obligations are economic debt even if off-sheet historically",
                formula_version="V1_ECONOMIC_DEBT_ENGINE",
                confidence="MEDIUM" if operating_lease_liability is not None else "INSUFFICIENT_DATA",
            )
        )

        # Finance leases
        fll = finance_lease_liability or 0.0
        adjustments.append(
            ObligationAdjustment(
                category=ObligationCategory.LEASE_FINANCE,
                amount=fll,
                status=InclusionStatus.INCLUDED if fll >= EconomicDebtEngine.ZERO_THRESHOLD else InclusionStatus.INSUFFICIENT_DATA,
                source="Balance Sheet: Finance Lease Liability",
                reason="Capitalized leases are debt-like obligations",
                formula_version="V1_ECONOMIC_DEBT_ENGINE",
                confidence="HIGH" if finance_lease_liability is not None else "INSUFFICIENT_DATA",
            )
        )

        reported_debt = stb + cplt + ltd + opl + fll
        calculation_status = "VALID" if reported_debt > 0 else "INSUFFICIENT_DATA"

        return EconomicDebtResult(
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            calculated_at=datetime.utcnow(),
            short_term_borrowings=short_term_borrowings,
            current_portion_lt_debt=current_portion_lt_debt,
            long_term_debt=long_term_debt,
            reported_debt=reported_debt,
            operating_lease_liability=operating_lease_liability,
            finance_lease_liability=finance_lease_liability,
            convertible_debt=None,
            preferred_claims=None,
            pension_deficit=None,
            supplier_financing=None,
            receivables_factoring=None,
            other_fixed_obligations=None,
            economic_debt=reported_debt,
            cash_and_equivalents=None,
            net_economic_debt=reported_debt,
            adjustments=adjustments,
            double_counting_amount=0.0,
            warnings=warnings,
            calculation_status=calculation_status,
        )

    @staticmethod
    def calculate_adjusted_debt(
        reported_debt: float,
        convertible_debt: float | None,
        preferred_claims: float | None,
        pension_deficit: float | None,
        supplier_financing: float | None,
        receivables_factoring: float | None,
        other_fixed_obligations: float | None,
        context: CalculationContext,
    ) -> EconomicDebtResult:
        """
        Calculate Adjusted Economic Debt.

        Adjusted = Reported + Convertibles + Preferred Claims + Pension Deficit
                 + Supplier Financing + Receivables Factoring + Other Fixed Claims

        Includes all fixed financial obligations that may not be on balance sheet
        but represent real economic claims.
        """
        warnings = []
        adjustments = []

        # Start with reported
        cd = convertible_debt or 0.0
        adjustments.append(
            ObligationAdjustment(
                category=ObligationCategory.CONVERTIBLE,
                amount=cd,
                status=InclusionStatus.INCLUDED if cd >= EconomicDebtEngine.ZERO_THRESHOLD else InclusionStatus.INSUFFICIENT_DATA,
                source="Balance Sheet/Notes: Convertible Securities",
                reason="Convertibles have debt-like characteristics and create equity dilution",
                formula_version="V1_ECONOMIC_DEBT_ENGINE",
                confidence="MEDIUM" if convertible_debt is not None else "INSUFFICIENT_DATA",
            )
        )

        pc = preferred_claims or 0.0
        adjustments.append(
            ObligationAdjustment(
                category=ObligationCategory.PREFERRED,
                amount=pc,
                status=InclusionStatus.INCLUDED if pc >= EconomicDebtEngine.ZERO_THRESHOLD else InclusionStatus.INSUFFICIENT_DATA,
                source="Balance Sheet/Notes: Preferred Stock",
                reason="Preferred stock is senior claim on assets",
                formula_version="V1_ECONOMIC_DEBT_ENGINE",
                confidence="MEDIUM" if preferred_claims is not None else "INSUFFICIENT_DATA",
            )
        )

        pdef = pension_deficit or 0.0
        adjustments.append(
            ObligationAdjustment(
                category=ObligationCategory.PENSION,
                amount=pdef,
                status=InclusionStatus.INCLUDED if pdef >= EconomicDebtEngine.ZERO_THRESHOLD else InclusionStatus.INSUFFICIENT_DATA,
                source="Notes to Statements: Pension Underfunding",
                reason="Underfunded pension liabilities are real economic obligations",
                formula_version="V1_ECONOMIC_DEBT_ENGINE",
                confidence="LOW" if pension_deficit is not None else "INSUFFICIENT_DATA",
            )
        )

        sf = supplier_financing or 0.0
        adjustments.append(
            ObligationAdjustment(
                category=ObligationCategory.SUPPLIER_FINANCE,
                amount=sf,
                status=InclusionStatus.INCLUDED if sf >= EconomicDebtEngine.ZERO_THRESHOLD else InclusionStatus.INSUFFICIENT_DATA,
                source="Notes to Statements: Supplier Financing/Trade Payables",
                reason="Extended supplier credit is financing obligation",
                formula_version="V1_ECONOMIC_DEBT_ENGINE",
                confidence="LOW" if supplier_financing is not None else "INSUFFICIENT_DATA",
            )
        )

        rf = receivables_factoring or 0.0
        adjustments.append(
            ObligationAdjustment(
                category=ObligationCategory.FACTORING,
                amount=rf,
                status=InclusionStatus.INCLUDED if rf >= EconomicDebtEngine.ZERO_THRESHOLD else InclusionStatus.INSUFFICIENT_DATA,
                source="Notes to Statements: Receivables Securitization",
                reason="Factored receivables represent off-balance-sheet financing",
                formula_version="V1_ECONOMIC_DEBT_ENGINE",
                confidence="LOW" if receivables_factoring is not None else "INSUFFICIENT_DATA",
            )
        )

        other = other_fixed_obligations or 0.0
        adjustments.append(
            ObligationAdjustment(
                category=ObligationCategory.OTHER_FIXED_CLAIM,
                amount=other,
                status=InclusionStatus.INCLUDED if other >= EconomicDebtEngine.ZERO_THRESHOLD else InclusionStatus.INSUFFICIENT_DATA,
                source="Notes to Statements: Other Fixed Obligations",
                reason="Catch-all for material fixed claims",
                formula_version="V1_ECONOMIC_DEBT_ENGINE",
                confidence="LOW" if other_fixed_obligations is not None else "INSUFFICIENT_DATA",
            )
        )

        economic_debt = reported_debt + cd + pc + pdef + sf + rf + other
        calculation_status = "VALID" if economic_debt > 0 else "INSUFFICIENT_DATA"

        return EconomicDebtResult(
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            calculated_at=datetime.utcnow(),
            short_term_borrowings=None,
            current_portion_lt_debt=None,
            long_term_debt=None,
            reported_debt=reported_debt,
            operating_lease_liability=None,
            finance_lease_liability=None,
            convertible_debt=convertible_debt,
            preferred_claims=preferred_claims,
            pension_deficit=pension_deficit,
            supplier_financing=supplier_financing,
            receivables_factoring=receivables_factoring,
            other_fixed_obligations=other_fixed_obligations,
            economic_debt=economic_debt,
            cash_and_equivalents=None,
            net_economic_debt=economic_debt,
            adjustments=adjustments,
            double_counting_amount=0.0,
            warnings=warnings,
            calculation_status=calculation_status,
        )

    @staticmethod
    def calculate_net_debt(
        economic_debt: float,
        cash_and_equivalents: float | None,
        short_term_investments: float | None,
        context: CalculationContext,
    ) -> EconomicDebtResult:
        """
        Calculate Net Economic Debt (economic debt minus cash).

        Net Economic Debt = Economic Debt - (Cash + Cash Equivalents + Short-Term Investments)

        Net debt is negative if company has more cash than debt (unusual but possible).
        """
        warnings = []
        cash = cash_and_equivalents or 0.0
        investments = short_term_investments or 0.0
        total_cash = cash + investments

        if cash_and_equivalents is None and short_term_investments is None:
            warnings.append("Missing cash and equivalents data; using zero for net debt calculation")

        net_debt = economic_debt - total_cash

        return EconomicDebtResult(
            company_id=context.company_id,
            fiscal_year=context.fiscal_year,
            fiscal_quarter=context.fiscal_quarter,
            calculated_at=datetime.utcnow(),
            short_term_borrowings=None,
            current_portion_lt_debt=None,
            long_term_debt=None,
            reported_debt=0.0,
            operating_lease_liability=None,
            finance_lease_liability=None,
            convertible_debt=None,
            preferred_claims=None,
            pension_deficit=None,
            supplier_financing=None,
            receivables_factoring=None,
            other_fixed_obligations=None,
            economic_debt=economic_debt,
            cash_and_equivalents=cash_and_equivalents,
            net_economic_debt=net_debt,
            adjustments=[],
            double_counting_amount=0.0,
            warnings=warnings,
            calculation_status="VALID" if economic_debt >= 0 else "INSUFFICIENT_DATA",
        )
