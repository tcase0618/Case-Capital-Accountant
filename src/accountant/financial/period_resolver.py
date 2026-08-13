"""Financial period resolver for XBRL/SEC fact classification."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

RESOLVER_VERSION = "FINANCIAL_PERIOD_RESOLVER_V1"


@dataclass(frozen=True)
class ResolvedPeriod:
    """Result of period resolution."""

    period_type: str  # INSTANT, Q1-Q4, FY, YTD_Q1-YTD_Q3, TTM, UNKNOWN
    fiscal_year: int | None
    fiscal_quarter: int | None
    start_date: date | None
    end_date: date | None
    instant_date: date | None
    duration_days: int | None
    fiscal_year_end: str | None
    is_ytd: bool
    is_derived: bool
    confidence: str  # HIGH, MEDIUM, LOW, UNKNOWN
    warnings: list[str] | None = None
    notes: str | None = None


class FinancialPeriodResolver:
    """Deterministic resolver for financial periods from XBRL facts."""

    def __init__(self, session: Session | None = None):
        """Initialize resolver.

        Args:
            session: Optional SQLAlchemy session for company metadata queries.
        """
        self.session = session

    def resolve_period(
        self,
        company_cik: str,
        instant_date: date | None,
        start_date: date | None,
        end_date: date | None,
        fiscal_year: int | None,
        fiscal_period: str | None,
        frame: str | None,
        form: str | None,
        decimals: int | None,
    ) -> ResolvedPeriod:
        """Resolve a financial period from raw XBRL context.

        Args:
            company_cik: Company CIK for fiscal year lookup
            instant_date: Instant date (for balance sheet facts)
            start_date: Period start date (for duration facts)
            end_date: Period end date (for duration facts)
            fiscal_year: SEC fiscal year field (metadata, not trusted blindly)
            fiscal_period: SEC fiscal period field (Q1-Q4, FY) (metadata, not trusted blindly)
            frame: SEC frame field (CY2024Q1, etc.) (metadata, not trusted blindly)
            form: Form type (10-K, 10-Q, etc.)
            decimals: Decimal places (affects precision/confidence)

        Returns:
            ResolvedPeriod with classification and confidence.
        """
        warnings: list[str] = []

        # Classify instant facts
        if instant_date:
            return self._resolve_instant_fact(
                instant_date, fiscal_year, form, warnings
            )

        # Classify duration facts
        if start_date and end_date:
            return self._resolve_duration_fact(
                company_cik, start_date, end_date, fiscal_year, fiscal_period, frame,
                form, warnings
            )

        # Insufficient data
        return ResolvedPeriod(
            period_type="UNKNOWN",
            fiscal_year=fiscal_year,
            fiscal_quarter=None,
            start_date=None,
            end_date=None,
            instant_date=None,
            duration_days=None,
            fiscal_year_end=None,
            is_ytd=False,
            is_derived=False,
            confidence="LOW",
            warnings=["No instant_date or period dates provided"],
        )

    def _resolve_instant_fact(
        self,
        instant_date: date,
        fiscal_year: int | None,
        form: str | None,
        warnings: list[str],
    ) -> ResolvedPeriod:
        """Resolve instant facts (balance sheet items)."""
        # Instant facts get HIGH confidence
        return ResolvedPeriod(
            period_type="INSTANT",
            fiscal_year=fiscal_year,
            fiscal_quarter=None,
            start_date=None,
            end_date=None,
            instant_date=instant_date,
            duration_days=None,
            fiscal_year_end=self._extract_fiscal_year_end(instant_date),
            is_ytd=False,
            is_derived=False,
            confidence="HIGH",
            warnings=warnings or None,
        )

    def _resolve_duration_fact(
        self,
        company_cik: str,
        start_date: date,
        end_date: date,
        fiscal_year: int | None,
        fiscal_period: str | None,
        frame: str | None,
        form: str | None,
        warnings: list[str],
    ) -> ResolvedPeriod:
        """Resolve duration facts (income statement, cash flow)."""
        duration_days = (end_date - start_date).days + 1

        # Determine fiscal year end (MMDD format)
        fiscal_year_end = self._extract_fiscal_year_end(end_date)

        # Classify period based on duration
        is_ytd = self._is_ytd_period(duration_days)
        period_type, period_q, confidence = self._classify_duration(
            start_date, end_date, duration_days, form, is_ytd, warnings
        )

        # Derive fiscal year if not provided
        if not fiscal_year:
            fiscal_year = self._derive_fiscal_year(end_date, fiscal_year_end)

        return ResolvedPeriod(
            period_type=period_type,
            fiscal_year=fiscal_year,
            fiscal_quarter=period_q,
            start_date=start_date,
            end_date=end_date,
            instant_date=None,
            duration_days=duration_days,
            fiscal_year_end=fiscal_year_end,
            is_ytd=is_ytd,
            is_derived=False,
            confidence=confidence,
            warnings=warnings or None,
        )

    def _classify_duration(
        self,
        start_date: date,
        end_date: date,
        duration_days: int,
        form: str | None,
        is_ytd: bool,
        warnings: list[str],
    ) -> tuple[str, int | None, str]:
        """Classify duration by actual days.

        Duration tolerance:
        - 3-month quarter: 88-95 days
        - 6-month YTD: 181-188 days
        - 9-month YTD: 273-283 days
        - 52-week year: 364-366 days
        - 53-week year: 371-374 days
        """
        # Determine if Q1, Q2, Q3, Q4 based on calendar
        start_month = start_date.month
        end_month = end_date.month

        # Year-long periods
        if 364 <= duration_days <= 366:
            return ("FY", None, "HIGH")
        if 371 <= duration_days <= 374:
            # 53-week year
            return ("FY", None, "MEDIUM")
            warnings.append("53-week fiscal year detected")

        # Quarter-like periods (~90 days)
        if 88 <= duration_days <= 95:
            quarter = self._infer_quarter_from_dates(start_month, end_month)
            return (f"Q{quarter}", quarter, "HIGH")

        # 26-week YTD (~6 months)
        if 181 <= duration_days <= 188:
            if is_ytd:
                return ("YTD_Q2", 2, "MEDIUM")
            else:
                return ("Q1", 1, "MEDIUM")

        # 39-week YTD (~9 months)
        if 273 <= duration_days <= 283:
            if is_ytd:
                return ("YTD_Q3", 3, "MEDIUM")
            else:
                # Could be Q3, depends on start date
                quarter = self._infer_quarter_from_dates(start_month, end_month)
                return (f"Q{quarter}", quarter, "MEDIUM")

        # 13-week period (typical quarter for 52/53-week retailers)
        if 91 <= duration_days <= 96:
            quarter = self._infer_quarter_from_dates(start_month, end_month)
            return (f"Q{quarter}", quarter, "MEDIUM")

        # Ambiguous or unusual duration
        if duration_days > 366:
            return ("UNKNOWN", None, "LOW")

        return ("UNKNOWN", None, "LOW")

    def _infer_quarter_from_dates(self, start_month: int, end_month: int) -> int:
        """Infer quarter from start/end month."""
        # Simple heuristic: quarter is determined by end month
        if end_month <= 3:
            return 1
        elif end_month <= 6:
            return 2
        elif end_month <= 9:
            return 3
        else:
            return 4

    def _is_ytd_period(self, duration_days: int) -> bool:
        """Determine if period appears to be YTD based on duration."""
        # YTD periods are longer than a quarter (~90 days) but less than full year
        return 181 <= duration_days < 365

    def _extract_fiscal_year_end(self, date_obj: date) -> str:
        """Extract fiscal year end as MMDD (e.g., '1231' for Dec 31)."""
        return date_obj.strftime("%m%d")

    def _derive_fiscal_year(self, end_date: date, fiscal_year_end: str) -> int:
        """Derive fiscal year from end date and fiscal year end (MMDD).

        Fiscal years are named by the calendar year in which they end.
        For example, with a Sept 30 FYE, Jan 31, 2024 is in FY 2024 (which ends Sept 30, 2024),
        but Oct 1, 2024 is in FY 2025 (which ends Sept 30, 2025).
        """
        end_month_day = end_date.strftime("%m%d")

        # Compare MMDD strings to determine fiscal year
        # If we haven't reached the FYE yet (or are at it), we're in the fiscal year
        # ending in the current calendar year.
        if end_month_day <= fiscal_year_end:
            return end_date.year
        else:
            # We've passed the FYE, so we're in the fiscal year ending next calendar year
            return end_date.year + 1

    def derive_standalone_quarter(
        self,
        ytd_q2_value: float | None,
        q1_value: float | None,
        ytd_q3_value: float | None,
        ytd_q2_for_q3: float | None,
        fy_value: float | None,
        ytd_q3_for_q4: float | None,
        unit: str | None,
        fiscal_year: int | None,
        decimals: int | None,
    ) -> tuple[dict | None, str | None]:
        """Derive standalone quarterly values from YTD facts.

        Returns:
            Tuple of (derived_quarter_dict, derivation_method) or (None, error_message)
        """
        # Q2 = 6M YTD - Q1
        if ytd_q2_value is not None and q1_value is not None:
            if unit is None:
                return None, "unit_missing"
            q2_derived = ytd_q2_value - q1_value
            return {
                "quarter": 2,
                "value": q2_derived,
                "unit": unit,
                "fiscal_year": fiscal_year,
                "decimals": decimals,
            }, "YTD_MINUS_Q1"

        # Q3 = 9M YTD - 6M YTD
        if ytd_q3_value is not None and ytd_q2_for_q3 is not None:
            if unit is None:
                return None, "unit_missing"
            q3_derived = ytd_q3_value - ytd_q2_for_q3
            return {
                "quarter": 3,
                "value": q3_derived,
                "unit": unit,
                "fiscal_year": fiscal_year,
                "decimals": decimals,
            }, "YTD_MINUS_YTD"

        # Q4 = FY - 9M YTD
        if fy_value is not None and ytd_q3_for_q4 is not None:
            if unit is None:
                return None, "unit_missing"
            q4_derived = fy_value - ytd_q3_for_q4
            return {
                "quarter": 4,
                "value": q4_derived,
                "unit": unit,
                "fiscal_year": fiscal_year,
                "decimals": decimals,
            }, "FY_MINUS_YTD"

        return None, "insufficient_data"


__all__ = ["FinancialPeriodResolver", "ResolvedPeriod", "RESOLVER_VERSION"]
