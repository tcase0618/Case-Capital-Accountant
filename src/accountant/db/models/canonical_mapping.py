"""Mapping rules from SEC concepts to canonical concepts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from accountant.db.base import Base
from accountant.db.types import UUID

if TYPE_CHECKING:
    from accountant.db.models.canonical_concept import CanonicalConcept


class CanonicalMapping(Base):
    """Mapping rule from SEC concept to canonical concept."""

    __tablename__ = "canonical_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    canonical_concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("canonical_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    taxonomy: Mapped[str] = mapped_column(String(64), nullable=False)
    source_concept: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(nullable=False, default=100)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False, default="HIGH")
    industry_applicability: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    mapping_version: Mapped[int] = mapped_column(nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    canonical_concept: Mapped[CanonicalConcept] = relationship(back_populates="mappings")

    def __repr__(self) -> str:
        return f"<CanonicalMapping {self.taxonomy}:{self.source_concept} → {self.canonical_concept.code}>"
