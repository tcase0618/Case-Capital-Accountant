from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.filing import Filing


class FilingDocument(Base):
    __tablename__ = "filing_documents"
    __table_args__ = (
        UniqueConstraint("filing_id", "document_name", name="uq_filing_documents_filing_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    filing: Mapped[Filing] = relationship(back_populates="documents")

    def __repr__(self) -> str:
        return f"<FilingDocument name={self.document_name}>"
