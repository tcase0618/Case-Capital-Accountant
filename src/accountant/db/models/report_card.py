from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.company import Company


class ReportCard(Base):
    """Immutable per-filing compact report card snapshot."""

    __tablename__ = "report_cards"
    __table_args__ = (
        UniqueConstraint("report_card_id", name="uq_report_cards_report_card_id"),
        Index("ix_report_cards_company_filed_date", "company_id", "filed_date"),
        Index("ix_report_cards_cik_filed_date", "cik", "filed_date"),
        Index("ix_report_cards_ticker_filed_date", "ticker", "filed_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_card_id: Mapped[str] = mapped_column(String(96), nullable=False)
    cik: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    sic_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    gics_sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gics_industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)

    filing_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_of_report: Mapped[date | None] = mapped_column(Date, nullable=True)
    filed_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accession_number: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_filing_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_restatement: Mapped[bool] = mapped_column(nullable=False, default=False)
    restates_report_card_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    tag_map_version: Mapped[str] = mapped_column(String(64), nullable=False, default="CANONICAL_MAPPING_V1")
    prior_report_card_id: Mapped[str | None] = mapped_column(String(96), nullable=True)

    standardized_financials: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    growth_trend_deltas: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    accrual_cash_quality: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    forensic_scores: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    positive_quality: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    event_red_flags: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    textual_signals: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    non_gaap_forensics: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    governance_ownership: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    market_data_linkage: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    universe_tradability: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    final_verdict: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    company: Mapped[Company] = relationship(back_populates="report_cards")

    def __repr__(self) -> str:
        return f"<ReportCard ticker={self.ticker} filing={self.filing_type} filed={self.filed_date}>"


@event.listens_for(ReportCard, "before_update")
def _deny_report_card_update(_mapper, _connection, _target: ReportCard) -> None:
    raise RuntimeError("report_cards are immutable and must never be overwritten")
