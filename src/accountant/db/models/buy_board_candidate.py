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
    from accountant.db.models.buy_board_snapshot import BuyBoardSnapshot
    from accountant.db.models.company import Company


class BuyBoardCandidate(Base):
    __tablename__ = "buy_board_candidates"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_buy_board_candidates_company"),
        Index("ix_buy_board_candidates_status", "status"),
        Index("ix_buy_board_candidates_ticker", "ticker"),
        Index("ix_buy_board_candidates_current_cc_valuation", "current_cc_valuation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    source_report_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source_report_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_price_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_price_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_cc_valuation: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_valuation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_cc_valuation: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_valuation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cc_valuation_growth_forecast_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    synopsis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    why_buy: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=[])
    accounting_basis: Mapped[dict[str, float | int | str | None]] = mapped_column(JSON, nullable=False, default={})
    battle_card: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default={})
    last_price_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_price_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_market_data_quality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_price_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company] = relationship(back_populates="buy_board_candidates")
    snapshots: Mapped[list[BuyBoardSnapshot]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<BuyBoardCandidate ticker={self.ticker} status={self.status}>"
