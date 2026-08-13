"""Financial period classification and resolution."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.company import Company


class FinancialPeriod(Base):
    """Resolved financial period with classification and lineage."""

    __tablename__ = "financial_periods"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "period_type", "fiscal_year", "fiscal_quarter", "instant_date",
            name="uq_financial_periods_unique_period"
        ),
        Index("ix_financial_periods_company_fiscal", "company_id", "fiscal_year", "fiscal_quarter"),
        Index("ix_financial_periods_company_dates", "company_id", "start_date", "end_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Period classification
    period_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="INSTANT, Q1-Q4, FY, YTD_Q1-YTD_Q3, TTM, UNKNOWN"
    )
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Period dates
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    instant_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Company fiscal year end (MMDD format, e.g., '1231' for Dec 31)
    fiscal_year_end: Mapped[str | None] = mapped_column(String(4), nullable=True)

    # Indicators
    is_ytd: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_derived: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Source tracking
    source_form: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_accession: Mapped[str | None] = mapped_column(String(24), nullable=True)
    source_fact_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Derivation
    derivation_method: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="e.g., YTD_MINUS_YTD, FY_MINUS_YTD, DIRECT_REPORT"
    )
    derivation_formula: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Human-readable derivation, e.g., '6M YTD - Q1 = Q2'"
    )

    # Resolution
    resolver_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="FINANCIAL_PERIOD_RESOLVER_V1"
    )
    confidence: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN",
        comment="HIGH, MEDIUM, LOW, UNKNOWN"
    )
    warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Amendment tracking
    originally_reported: Mapped[bool] = mapped_column(nullable=False, default=True)
    restated_by_accession: Mapped[str | None] = mapped_column(String(24), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    company: Mapped[Company] = relationship(back_populates="financial_periods")

    def __repr__(self) -> str:
        if self.period_type == "INSTANT":
            period_str = f"instant {self.instant_date}"
        elif self.start_date and self.end_date:
            period_str = f"{self.start_date} to {self.end_date}"
        else:
            period_str = self.period_type
        return f"<FinancialPeriod {self.period_type} FY{self.fiscal_year} {period_str}>"
