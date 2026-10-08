"""Discovery progress independent of individual company filing dates."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from accountant.db.base import Base


class SecIndexCheckpoint(Base):
    __tablename__ = "sec_index_checkpoints"

    index_date: Mapped[date] = mapped_column(Date, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    matched_rows: Mapped[int | None] = mapped_column(Integer)
