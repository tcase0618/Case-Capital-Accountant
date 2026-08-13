"""Statement snapshots and line items for reconstructed financial statements."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.company import Company


class StatementSnapshot(Base):
    """Snapshot of a reconstructed financial statement."""

    __tablename__ = "statement_snapshots"
    __table_args__ = (
        Index("ix_statement_snapshots_company_type", "company_id", "statement_type"),
        Index(
            "ix_statement_snapshots_company_period",
            "company_id",
            "fiscal_year",
            "fiscal_quarter",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Statement classification
    statement_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="income, balance, cashflow"
    )

    # Period
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Q1-Q4, FY, INSTANT"
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    instant_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Source filings
    source_accessions: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, comment="Array of accession numbers used"
    )
    primary_accession: Mapped[str | None] = mapped_column(String(24), nullable=True)

    # Reconstruction metadata
    builder_version: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="e.g., INCOME_STATEMENT_BUILDER_V1"
    )
    mapping_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    resolver_version: Mapped[str] = mapped_column(String(64), nullable=False)

    # Quality
    quality_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", comment="PASS, WARNING, FAIL, INSUFFICIENT_DATA"
    )
    completeness: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="0.0-1.0, % of required concepts"
    )
    warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    quality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Restatement tracking
    is_restated: Mapped[bool] = mapped_column(nullable=False, default=False)
    restated_by_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), nullable=True)
    originally_reported: Mapped[bool] = mapped_column(nullable=False, default=True)

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

    company: Mapped[Company] = relationship()
    lines: Mapped[list[StatementLine]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        period_str = f"FY{self.fiscal_year}"
        if self.fiscal_quarter:
            period_str += f"Q{self.fiscal_quarter}"
        return f"<StatementSnapshot {self.statement_type} {period_str}>"


class StatementLine(Base):
    """Single line item in a financial statement."""

    __tablename__ = "statement_lines"
    __table_args__ = (
        Index("ix_statement_lines_snapshot_concept", "snapshot_id", "canonical_concept"),
        Index("ix_statement_lines_company_concept", "company_id", "canonical_concept"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("statement_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Concept mapping
    canonical_concept: Mapped[str] = mapped_column(String(64), nullable=False, comment="e.g., CC_REVENUE")
    canonical_concept_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), nullable=True)

    # Value
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Provenance
    canonical_fact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), nullable=True)
    raw_fact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), nullable=True)
    filing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), nullable=True)
    accession_number: Mapped[str | None] = mapped_column(String(24), nullable=True)

    # Source data
    raw_taxonomy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_concept: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Versioning
    mapping_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    resolver_version: Mapped[str] = mapped_column(String(64), nullable=False)

    # Classification
    reported_or_derived: Mapped[str] = mapped_column(
        String(32), nullable=False, default="reported", comment="reported or derived"
    )
    derivation_formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    derivation_method: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Quality
    mapping_confidence: Mapped[str] = mapped_column(
        String(32), nullable=False, default="HIGH", comment="HIGH, MEDIUM, LOW, UNKNOWN"
    )
    selection_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="SELECTED",
        comment="SELECTED, MULTIPLE_EQUIVALENT, CONFLICT, AMBIGUOUS, MISSING",
    )

    # Audit trail
    warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    snapshot: Mapped[StatementSnapshot] = relationship(back_populates="lines")
    company: Mapped[Company] = relationship()

    def __repr__(self) -> str:
        val_str = f"{self.value_numeric}" if self.value_numeric is not None else self.value_text or "?"
        return f"<StatementLine {self.canonical_concept}: {val_str} {self.unit}>"
