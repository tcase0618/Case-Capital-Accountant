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


class PaperBookPosition(Base):
    __tablename__ = "paper_book_positions"
    __table_args__ = (
        UniqueConstraint("book_name", "ticker", name="uq_paper_book_positions_book_ticker"),
        Index("ix_paper_book_positions_book_name", "book_name"),
        Index("ix_paper_book_positions_launch_date", "launch_date"),
        Index("ix_paper_book_positions_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_name: Mapped[str] = mapped_column(String(96), nullable=False)
    launch_date: Mapped[date] = mapped_column(Date, nullable=False)
    lane: Mapped[str] = mapped_column(String(32), nullable=False, default="BUY")
    route_family: Mapped[str] = mapped_column(String(48), nullable=False)
    route_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    report_card_id: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_weight: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    thesis_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    company: Mapped[Company] = relationship(back_populates="paper_book_positions")

    def __repr__(self) -> str:
        return f"<PaperBookPosition book={self.book_name} ticker={self.ticker} lane={self.lane}>"
