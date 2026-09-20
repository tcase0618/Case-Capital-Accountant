from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.company import Company


class CompanyBottleneckSnapshot(Base):
    __tablename__ = "company_bottleneck_snapshots"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_bottleneck_snapshots_company"),
        Index("ix_company_bottleneck_snapshots_ticker", "ticker"),
        Index("ix_company_bottleneck_snapshots_focus_family", "focus_family"),
        Index("ix_company_bottleneck_snapshots_model_family", "model_family"),
        Index("ix_company_bottleneck_snapshots_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    sic: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sic_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    focus_family: Mapped[str] = mapped_column(String(64), nullable=False, default="General")
    model_family: Mapped[str] = mapped_column(String(64), nullable=False, default="operating_company")
    model_family_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    stance: Mapped[str | None] = mapped_column(String(32), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_family_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_quality_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latest_filing_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bottlenecks: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    management_bottlenecks: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="BOTTLENECK_ENGINE_V1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    company: Mapped[Company] = relationship(back_populates="bottleneck_snapshots")
