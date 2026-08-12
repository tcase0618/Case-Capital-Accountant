from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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
    from accountant.db.models.filing import Filing


class RawFact(Base):
    """
    Immutable XBRL/source fact. Designed for later XBRL ingestion.

    Never UPDATE these rows. Corrections are new facts from a later filing
    or a new insert with distinct provenance.
    """

    __tablename__ = "raw_facts"
    __table_args__ = (
        UniqueConstraint("fact_hash", name="uq_raw_facts_fact_hash"),
        Index("ix_raw_facts_company_concept_period", "company_id", "concept", "period_end"),
        Index("ix_raw_facts_filing_concept", "filing_id", "concept"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("filings.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    concept: Mapped[str] = mapped_column(String(255), nullable=False)
    taxonomy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    instant_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    decimals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value_numeric: Mapped[float | None] = mapped_column(Numeric(38, 10), nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimensions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    context_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_document: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    accession_number: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    frame: Mapped[str | None] = mapped_column(String(32), nullable=True)
    form: Mapped[str | None] = mapped_column(String(32), nullable=True)
    filed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    label: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="xbrl")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    filing: Mapped[Filing] = relationship(back_populates="raw_facts")
    company: Mapped[Company] = relationship(back_populates="raw_facts")

    def __repr__(self) -> str:
        return f"<RawFact concept={self.concept} hash={self.fact_hash[:8]}>"


@event.listens_for(RawFact, "before_update")
def _deny_raw_fact_update(_mapper, _connection, _target: RawFact) -> None:
    raise RuntimeError("raw_facts are immutable and must never be overwritten")
