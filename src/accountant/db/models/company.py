from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.buy_board_candidate import BuyBoardCandidate
    from accountant.db.models.calculation_result import CalculationResult
    from accountant.db.models.company_report import CompanyReport
    from accountant.db.models.filing import Filing
    from accountant.db.models.financial_period import FinancialPeriod
    from accountant.db.models.raw_fact import RawFact
    from accountant.db.models.report_card import ReportCard
    from accountant.db.models.research_record import ResearchRecord
    from accountant.db.models.security import Security


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    cik: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sic: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sic_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ein: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fiscal_year_end: Mapped[str | None] = mapped_column(String(8), nullable=True)
    state_of_incorporation: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    securities: Mapped[list[Security]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    filings: Mapped[list[Filing]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    raw_facts: Mapped[list[RawFact]] = relationship(back_populates="company")
    financial_periods: Mapped[list[FinancialPeriod]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    calculation_results: Mapped[list[CalculationResult]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    research_records: Mapped[list[ResearchRecord]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    reports: Mapped[list[CompanyReport]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    report_cards: Mapped[list[ReportCard]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    buy_board_candidates: Mapped[list[BuyBoardCandidate]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Company cik={self.cik} name={self.name!r}>"
