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


class CompanyReport(Base):
    __tablename__ = "company_reports"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_reports_company"),
        Index("ix_company_reports_composite_score", "composite_score"),
        Index("ix_company_reports_stance", "stance"),
        Index("ix_company_reports_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    as_of_date: Mapped[str] = mapped_column(String(10), nullable=False)
    stance: Mapped[str] = mapped_column(String(32), nullable=False)
    bullish_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bearish_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    data_quality_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pipeline_stage: Mapped[str] = mapped_column(String(32), nullable=False, default="seeded")
    latest_filing_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    key_stats: Mapped[dict[str, float | int | str | None]] = mapped_column(JSON, nullable=False, default={})
    highlights: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=[])
    report_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_versions: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default={})
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    company: Mapped[Company] = relationship(back_populates="reports")

    def __repr__(self) -> str:
        return f"<CompanyReport ticker={self.ticker} stance={self.stance} score={self.composite_score:.1f}>"
