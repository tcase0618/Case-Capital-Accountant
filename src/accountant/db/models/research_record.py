"""Persistent research classification records."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
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


class ResearchRecord(Base):
    """Immutable research classification record at a point in time."""

    __tablename__ = "research_records"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "as_of_date", name="uq_research_records_company_date"
        ),
        Index("ix_research_records_company_date", "company_id", "as_of_date"),
        Index("ix_research_records_classification", "classification"),
        Index("ix_research_records_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    as_of_date: Mapped[str] = mapped_column(String(10), nullable=False)

    # Classification
    classification: Mapped[str] = mapped_column(String(64), nullable=False)
    classification_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    # Metrics
    accounting_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    owner_earnings_yield_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    owner_earnings_growth_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    roic_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    incremental_roic_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    capital_allocation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    credit_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    bear_case_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    forensic_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Valuation
    valuation_range_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    valuation_range_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin_of_safety_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Peer rankings
    peer_rank_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    peer_rank_growth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    peer_rank_valuation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    peer_rank_safety: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Rules and metadata
    rules_triggered: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=[])
    rules_failed: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=[])
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=[])
    classification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Versioning
    rule_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="FUNDAMENTAL_RESEARCH_CLASSIFICATION_V1"
    )
    feature_versions: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)

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

    company: Mapped[Company] = relationship(back_populates="research_records")

    def __repr__(self) -> str:
        return f"<ResearchRecord company={self.company_id} date={self.as_of_date} class={self.classification}>"
