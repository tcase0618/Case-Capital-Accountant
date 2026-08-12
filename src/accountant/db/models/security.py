from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.company import Company


class Security(Base):
    __tablename__ = "securities"
    __table_args__ = (UniqueConstraint("ticker", name="uq_securities_ticker"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cusip: Mapped[str | None] = mapped_column(String(16), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(16), nullable=True)
    security_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    company: Mapped[Company] = relationship(back_populates="securities")

    def __repr__(self) -> str:
        return f"<Security ticker={self.ticker} exchange={self.exchange!r}>"
