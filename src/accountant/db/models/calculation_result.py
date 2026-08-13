"""Calculation result persistence model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.company import Company


class CalculationResult(Base):
    """Persisted result of a financial calculation.

    Stores calculation outputs with full metadata: formula, inputs, provenance,
    status, and audit trail. Idempotent: (company_id, calculation_id, fiscal_year,
    fiscal_quarter) uniqueness ensures no duplicate results.
    """

    __tablename__ = "calculation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    calculation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    formula_version: Mapped[str] = mapped_column(String(50), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    calculation_status: Mapped[str] = mapped_column(String(50), default="VALID", nullable=False)

    inputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    calc_metadata: Mapped[dict] = mapped_column(
        JSON, name="metadata", nullable=False, default=dict
    )

    source_statement_snapshot_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_statement_line_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_canonical_fact_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    calc_warnings: Mapped[list] = mapped_column(
        JSON, name="warnings", nullable=False, default=list
    )

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    company: Mapped[Company] = relationship(
        back_populates="calculation_results",
        foreign_keys=[company_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "calculation_id",
            "fiscal_year",
            "fiscal_quarter",
            name="uq_calculation_result",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CalculationResult "
            f"id={self.id} "
            f"calculation_id={self.calculation_id} "
            f"fiscal_year={self.fiscal_year} "
            f"value={self.value}>"
        )
