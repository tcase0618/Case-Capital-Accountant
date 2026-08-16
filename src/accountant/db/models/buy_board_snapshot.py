from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.buy_board_candidate import BuyBoardCandidate


class BuyBoardSnapshot(Base):
    __tablename__ = "buy_board_snapshots"
    __table_args__ = (
        Index("ix_buy_board_snapshots_candidate_id", "candidate_id"),
        Index("ix_buy_board_snapshots_captured_at", "captured_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("buy_board_candidates.id", ondelete="CASCADE"), nullable=False
    )
    session_label: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL")
    refresh_reason: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    cc_valuation: Mapped[float | None] = mapped_column(Float, nullable=True)
    upside_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_quality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    candidate: Mapped[BuyBoardCandidate] = relationship(back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<BuyBoardSnapshot candidate_id={self.candidate_id} session={self.session_label}>"
