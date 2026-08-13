"""Canonical fact ingestion with XBRL validation and mapping.

Validates XBRL instances, maps facts to canonical concepts, and stores
canonical facts with full lineage back to raw facts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import and_, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from accountant.db.models import Company, Filing
    from accountant.xbrl.arelle_adapter import ArelleFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CanonicalIngestionResult:
    """Result of canonical fact ingestion."""

    cik: str
    ticker: str | None
    company_name: str
    filing_accession: str
    raw_facts_examined: int
    canonical_facts_inserted: int
    canonical_facts_existing: int
    facts_mapped: int
    facts_low_confidence: int
    facts_conflicts: int
    facts_unmapped: int
    facts_custom_tags: int
    validation_passed: bool
    validation_errors: list[str]
    errors: list[str]


class CanonicalFactIngestion:
    """Ingest raw facts as canonical facts with XBRL validation.

    Process:
    1. Validate XBRL instance via Arelle (optional)
    2. Query raw facts for filing
    3. Map each fact to canonical concept
    4. Store canonical facts with lineage to raw facts
    5. Track unmapped facts for future mapping improvements
    """

    def __init__(self, session: Session, arelle: ArelleFacade | None = None):
        """Initialize ingestion engine.

        Args:
            session: SQLAlchemy session
            arelle: Optional Arelle facade for XBRL validation
        """
        self.session = session
        self.arelle = arelle

    def ingest_filing(
        self,
        filing: Filing,
        company: Company,
        instance_url: str | None = None,
        mapping_version: int = 1,
    ) -> CanonicalIngestionResult:
        """Ingest canonical facts from XBRL filing.

        Args:
            filing: Filing record from database
            company: Company record from database
            instance_url: Optional URL to XBRL instance for validation
            mapping_version: Version of mapping rules to use

        Returns:
            CanonicalIngestionResult with ingestion summary
        """
        from accountant.db.models import CanonicalConcept, CanonicalFact, RawFact
        from accountant.ingest.canonical_mapper import CanonicalMapper

        errors: list[str] = []
        validation_passed = True
        validation_errors: list[str] = []
        mapper = CanonicalMapper(self.session)

        # Optionally validate filing
        if instance_url and self.arelle:
            try:
                validation_passed, validation_errors = self.validate_filing(
                    instance_url
                )
            except Exception as e:
                logger.warning(f"Validation error: {e}")
                validation_errors.append(str(e))

        # Query raw facts for this filing
        stmt = select(RawFact).where(RawFact.filing_id == filing.id)
        raw_facts = self.session.execute(stmt).scalars().all()

        stats = {
            "examined": len(raw_facts),
            "mapped": 0,
            "low_confidence": 0,
            "conflicts": 0,
            "unmapped": 0,
            "custom_tags": 0,
            "inserted": 0,
            "existing": 0,
        }

        # Map and store canonical facts
        for raw_fact in raw_facts:
            try:
                # Find mapping
                mapping_result = mapper.find_and_resolve_candidates(
                    raw_fact.taxonomy,
                    raw_fact.concept,
                    mapping_version=mapping_version,
                )

                canonical_code = mapping_result.get("canonical_concept_code")
                if not canonical_code:
                    if mapping_result.get("status") == "UNMAPPED_CUSTOM_TAG":
                        stats["custom_tags"] += 1
                    else:
                        stats["unmapped"] += 1
                    continue

                # Look up canonical concept ID
                stmt_concept = select(CanonicalConcept).where(
                    CanonicalConcept.code == canonical_code
                )
                canonical_concept = self.session.execute(stmt_concept).scalar()

                if not canonical_concept:
                    logger.warning(f"Canonical concept {canonical_code} not found")
                    stats["unmapped"] += 1
                    continue

                # Check if canonical fact already exists
                stmt_existing = select(CanonicalFact).where(
                    and_(
                        CanonicalFact.raw_fact_id == raw_fact.id,
                        CanonicalFact.mapping_version == mapping_version,
                    )
                )
                existing = self.session.execute(stmt_existing).scalar()

                if existing:
                    stats["existing"] += 1
                    continue

                # Create canonical fact
                canonical_fact = CanonicalFact(
                    company_id=company.id,
                    raw_fact_id=raw_fact.id,
                    canonical_concept_id=canonical_concept.id,
                    value=raw_fact.value_text,
                    value_numeric=raw_fact.value_numeric,
                    unit=raw_fact.unit,
                    mapping_rule=mapping_result.get("mapping_rule"),
                    mapping_version=mapping_version,
                    mapping_confidence=mapping_result.get("confidence", "LOW"),
                    reported_or_derived="reported",
                )

                self.session.add(canonical_fact)

                # Update statistics
                stats["inserted"] += 1
                confidence = mapping_result.get("confidence", "")
                if confidence == "HIGH":
                    stats["mapped"] += 1
                elif confidence == "MEDIUM":
                    stats["low_confidence"] += 1
                elif mapping_result.get("status") == "CONFLICT":
                    stats["conflicts"] += 1
                else:
                    stats["unmapped"] += 1

            except Exception as e:
                logger.warning(f"Error mapping fact {raw_fact.id}: {e}")
                errors.append(f"Fact {raw_fact.id}: {str(e)}")

        # Commit all changes
        try:
            self.session.commit()
        except Exception as e:
            logger.error(f"Error committing canonical facts: {e}")
            self.session.rollback()
            errors.append(f"Commit error: {str(e)}")

        return CanonicalIngestionResult(
            cik=company.cik,
            ticker=None,
            company_name=company.name,
            filing_accession=filing.accession_number,
            raw_facts_examined=stats["examined"],
            canonical_facts_inserted=stats["inserted"],
            canonical_facts_existing=stats["existing"],
            facts_mapped=stats["mapped"],
            facts_low_confidence=stats["low_confidence"],
            facts_conflicts=stats["conflicts"],
            facts_unmapped=stats["unmapped"],
            facts_custom_tags=stats["custom_tags"],
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            errors=errors,
        )

    def validate_filing(
        self, instance_url: str
    ) -> tuple[bool, list[str]]:
        """Validate XBRL instance document.

        Args:
            instance_url: URL to XBRL instance document

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        if not self.arelle:
            raise RuntimeError("Arelle not configured for validation")

        result = self.arelle.validate_instance(instance_url)
        errors = [f"{e.level}: {e.message}" for e in result.errors]

        return result.is_valid, errors


def query_canonical_facts(
    session: Session,
    company_id: str,
    concept_code: str | None = None,
    form: str | None = None,
    limit: int = 100,
) -> list:
    """Query canonical facts with optional filters.

    Args:
        session: SQLAlchemy session
        company_id: Company UUID
        concept_code: Optional canonical concept code filter
        form: Optional form type filter
        limit: Maximum results to return

    Returns:
        List of canonical facts ordered by creation date DESC
    """
    from accountant.db.models import CanonicalConcept, CanonicalFact, Filing, RawFact

    stmt = select(CanonicalFact).where(CanonicalFact.company_id == company_id)

    if concept_code:
        stmt = stmt.join(CanonicalConcept).where(
            CanonicalConcept.code == concept_code
        )

    if form:
        stmt = (
            stmt.join(RawFact)
            .join(Filing)
            .where(Filing.form_type == form)
        )

    stmt = stmt.order_by(CanonicalFact.created_at.desc()).limit(limit)

    return session.execute(stmt).scalars().all()


__all__ = ["CanonicalFactIngestion", "CanonicalIngestionResult", "query_canonical_facts"]
