from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.company import Company
    from accountant.db.models.filing_document import FilingDocument
    from accountant.db.models.raw_fact import RawFact


class Filing(Base):
    """SEC filing metadata. Natural key is accession_number; inserts are idempotent."""

    __tablename__ = "filings"
    __table_args__ = (
        UniqueConstraint("accession_number", name="uq_filings_accession_number"),
        Index("ix_filings_company_form_date", "company_id", "form_type", "filing_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    accession_number: Mapped[str] = mapped_column(String(24), nullable=False)
    form_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    primary_document: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_doc_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_amendment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    file_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    film_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    act: Mapped[str | None] = mapped_column(String(8), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_xbrl: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_inline_xbrl: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_system: Mapped[str] = mapped_column(String(32), nullable=False, default="sec_submissions")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    company: Mapped[Company] = relationship(back_populates="filings")
    documents: Mapped[list[FilingDocument]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )
    raw_facts: Mapped[list[RawFact]] = relationship(back_populates="filing")

    def __repr__(self) -> str:
        return f"<Filing accession={self.accession_number} form={self.form_type}>"
