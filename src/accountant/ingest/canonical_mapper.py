"""Canonical mapping engine for mapping raw concepts to canonical concepts.

Implements deterministic, versioned mapping rules with priority-based
conflict resolution and industry-specific customization.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from accountant.taxonomy.mappings import find_mapping_candidates as find_rules

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from accountant.db.models import RawFact

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MappingResult:
    """Result of mapping a raw fact to canonical."""

    raw_fact_id: str | None
    canonical_concept_code: str | None
    confidence: str
    mapping_rule: str | None
    mapping_version: int
    status: str = "UNMAPPED"  # MAPPED, LOW_CONFIDENCE, CONFLICT, UNMAPPED, UNMAPPED_CUSTOM_TAG
    notes: str | None = None


class CanonicalMapper:
    """Maps raw concepts to canonical concepts using versioned rules.

    Implements:
    - Priority-based mapping selection
    - Confidence scoring
    - Conflict detection and resolution
    - Industry-specific customization
    - Mapping versioning and audit trail
    """

    def __init__(self, session: Session | None = None):
        """Initialize mapper with optional database session.

        Args:
            session: Optional SQLAlchemy session for querying mapping rules
        """
        self.session = session

    def map_fact(
        self,
        raw_fact: RawFact,
        industry: str | None = None,
        mapping_version: int = 1,
    ) -> MappingResult:
        """Map a raw fact to a canonical concept.

        Args:
            raw_fact: Raw XBRL fact to map
            industry: Optional industry code for industry-specific mappings
            mapping_version: Mapping version to use (default: 1)

        Returns:
            MappingResult with canonical concept code and confidence
        """
        result = self.find_and_resolve_candidates(
            raw_fact.taxonomy,
            raw_fact.concept,
            industry=industry,
            mapping_version=mapping_version,
        )

        return MappingResult(
            raw_fact_id=str(raw_fact.id) if hasattr(raw_fact, "id") else None,
            canonical_concept_code=result.get("canonical_concept_code"),
            confidence=result.get("confidence", "LOW"),
            mapping_rule=result.get("mapping_rule"),
            mapping_version=mapping_version,
            status=result.get("status", "UNMAPPED"),
            notes=result.get("notes"),
        )

    def find_candidates(
        self,
        taxonomy: str,
        concept: str,
        industry: str | None = None,
        mapping_version: int = 1,
    ) -> list[dict]:
        """Find candidate canonical mappings for a raw concept.

        Args:
            taxonomy: Taxonomy name (e.g., "us-gaap", "ifrs-full")
            concept: Concept name
            industry: Optional industry code
            mapping_version: Mapping version

        Returns:
            List of mapping candidates sorted by priority/confidence
        """
        candidates = find_rules(taxonomy, concept, mapping_version, industry)

        result = []
        for candidate in candidates:
            result.append(
                {
                    "taxonomy": candidate.taxonomy,
                    "source_concept": candidate.source_concept,
                    "canonical_concept_code": candidate.canonical_concept_code,
                    "priority": candidate.priority,
                    "confidence": candidate.confidence,
                    "rationale": candidate.rationale,
                    "industry_applicability": candidate.industry_applicability,
                    "mapping_version": candidate.mapping_version,
                }
            )

        return result

    def detect_conflict(
        self,
        taxonomy: str,
        concept: str,
        candidates: list[dict] | None = None,
    ) -> bool:
        """Detect if multiple valid mappings exist for a concept.

        Args:
            taxonomy: Taxonomy name
            concept: Concept name
            candidates: Optional list of candidate mappings

        Returns:
            True if conflict detected (multiple high-confidence mappings)
        """
        if candidates is None:
            candidates = self.find_candidates(taxonomy, concept)

        if len(candidates) <= 1:
            return False

        high_confidence = [
            c for c in candidates if c.get("confidence") in ("HIGH", "MEDIUM")
        ]
        return len(high_confidence) > 1

    def resolve_conflict(
        self,
        taxonomy: str,
        concept: str,
        candidates: list[dict] | None = None,
        industry: str | None = None,
    ) -> dict | None:
        """Resolve conflict when multiple valid mappings exist.

        Priority order:
        1. Industry-specific mappings (if provided)
        2. Highest priority score
        3. Highest confidence level

        Args:
            taxonomy: Taxonomy name
            concept: Concept name
            candidates: Optional list of candidate mappings
            industry: Optional industry code

        Returns:
            Selected mapping candidate or None if unable to resolve
        """
        if candidates is None:
            candidates = self.find_candidates(taxonomy, concept, industry)

        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        # Filter by confidence level
        high_conf = [c for c in candidates if c.get("confidence") == "HIGH"]
        if high_conf:
            candidates = high_conf
        else:
            medium_conf = [c for c in candidates if c.get("confidence") == "MEDIUM"]
            if medium_conf:
                candidates = medium_conf

        # Sort by priority
        candidates = sorted(candidates, key=lambda c: -c.get("priority", 0))

        return candidates[0] if candidates else None

    def find_and_resolve_candidates(
        self,
        taxonomy: str,
        concept: str,
        industry: str | None = None,
        mapping_version: int = 1,
    ) -> dict:
        """Find candidates and resolve to a single mapping.

        Returns:
            Dict with keys: canonical_concept_code, confidence, mapping_rule, status, notes
        """
        candidates = self.find_candidates(taxonomy, concept, industry, mapping_version)

        if not candidates:
            # Check if custom extension (contains namespace prefix)
            if ":" in concept or taxonomy not in ("us-gaap", "ifrs-full"):
                return {
                    "canonical_concept_code": None,
                    "confidence": "NONE",
                    "mapping_rule": None,
                    "status": "UNMAPPED_CUSTOM_TAG",
                    "notes": f"Custom extension: {taxonomy}:{concept}",
                }
            else:
                return {
                    "canonical_concept_code": None,
                    "confidence": "NONE",
                    "mapping_rule": None,
                    "status": "UNMAPPED",
                    "notes": f"No mapping found for {taxonomy}:{concept}",
                }

        # Detect conflict
        has_conflict = self.detect_conflict(taxonomy, concept, candidates)

        if has_conflict:
            # Try to resolve
            resolved = self.resolve_conflict(taxonomy, concept, candidates, industry)
            if resolved:
                return {
                    "canonical_concept_code": resolved.get("canonical_concept_code"),
                    "confidence": resolved.get("confidence"),
                    "mapping_rule": f"{taxonomy}:{resolved.get('source_concept')} → {resolved.get('canonical_concept_code')}",
                    "status": "MAPPED",
                    "notes": resolved.get("rationale"),
                }
            else:
                # Unresolvable conflict
                return {
                    "canonical_concept_code": None,
                    "confidence": "NONE",
                    "mapping_rule": None,
                    "status": "CONFLICT",
                    "notes": f"Multiple conflicting mappings for {taxonomy}:{concept}",
                }

        # Single candidate
        candidate = candidates[0]
        confidence = candidate.get("confidence", "LOW")

        return {
            "canonical_concept_code": candidate.get("canonical_concept_code"),
            "confidence": confidence,
            "mapping_rule": f"{taxonomy}:{candidate.get('source_concept')} → {candidate.get('canonical_concept_code')}",
            "status": "MAPPED" if confidence in ("HIGH", "MEDIUM") else "LOW_CONFIDENCE",
            "notes": candidate.get("rationale"),
        }


__all__ = ["CanonicalMapper", "MappingResult"]
