"""Canonical facts with lineage tracking to raw facts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.canonical_concept import CanonicalConcept
    from accountant.db.models.company import Company
    from accountant.db.models.raw_fact import RawFact


class CanonicalFact(Base):
    """Canonical fact with lineage to raw facts."""

    __tablename__ = "canonical_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("raw_facts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    canonical_concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("canonical_concepts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    value: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    value_numeric: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mapping_rule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mapping_version: Mapped[int] = mapped_column(nullable=False, default=1)
    mapping_confidence: Mapped[str] = mapped_column(String(32), nullable=False, default="HIGH")
    reported_or_derived: Mapped[str] = mapped_column(String(32), nullable=False, default="reported")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_fact_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_accession_number: Mapped[str | None] = mapped_column(String(24), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_filed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_concept: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_taxonomy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_filing_form: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_fact_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    company: Mapped[Company] = relationship()
    raw_fact: Mapped[RawFact] = relationship()
    canonical_concept: Mapped[CanonicalConcept] = relationship()

    def __repr__(self) -> str:
        return (
            f"<CanonicalFact {self.canonical_concept.code}: "
            f"{self.value_numeric or self.value} {self.unit}>"
        )
