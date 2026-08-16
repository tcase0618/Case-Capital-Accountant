from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from accountant.db.models import CanonicalConcept, CanonicalMapping
from accountant.taxonomy.canonical_registry import get_canonical_registry
from accountant.taxonomy.mappings import get_mapping_rules


def ensure_canonical_taxonomy_seeded(session: Session, mapping_version: int = 1) -> dict[str, int]:
    registry = get_canonical_registry()
    concept_defs = registry.list_concepts()
    mapping_defs = get_mapping_rules(mapping_version=mapping_version)

    existing_concepts = {
        concept.code: concept
        for concept in session.execute(select(CanonicalConcept)).scalars().all()
    }
    concepts_inserted = 0
    concepts_updated = 0
    for concept_def in concept_defs:
        concept = existing_concepts.get(concept_def.code)
        if concept is None:
            concept = CanonicalConcept(
                code=concept_def.code,
                label=concept_def.label,
                description=concept_def.description,
                category=concept_def.category,
                unit_hint=concept_def.unit_hint,
                is_active=True,
                version=concept_def.version,
            )
            session.add(concept)
            existing_concepts[concept_def.code] = concept
            concepts_inserted += 1
            continue
        changed = False
        if concept.label != concept_def.label:
            concept.label = concept_def.label
            changed = True
        if concept.description != concept_def.description:
            concept.description = concept_def.description
            changed = True
        if concept.category != concept_def.category:
            concept.category = concept_def.category
            changed = True
        if concept.unit_hint != concept_def.unit_hint:
            concept.unit_hint = concept_def.unit_hint
            changed = True
        if concept.version != concept_def.version:
            concept.version = concept_def.version
            changed = True
        if not concept.is_active:
            concept.is_active = True
            changed = True
        if changed:
            concepts_updated += 1

    session.flush()

    existing_mappings = {
        (
            row.taxonomy,
            row.source_concept,
            row.canonical_concept_id,
            row.mapping_version,
        ): row
        for row in session.execute(select(CanonicalMapping)).scalars().all()
    }
    mappings_inserted = 0
    mappings_updated = 0
    for mapping_def in mapping_defs:
        concept = existing_concepts.get(mapping_def.canonical_concept_code)
        if concept is None:
            continue
        key = (
            mapping_def.taxonomy,
            mapping_def.source_concept,
            concept.id,
            mapping_def.mapping_version,
        )
        mapping = existing_mappings.get(key)
        if mapping is None:
            session.add(
                CanonicalMapping(
                    canonical_concept_id=concept.id,
                    taxonomy=mapping_def.taxonomy,
                    source_concept=mapping_def.source_concept,
                    priority=mapping_def.priority,
                    confidence=mapping_def.confidence,
                    industry_applicability=mapping_def.industry_applicability,
                    rationale=mapping_def.rationale,
                    mapping_version=mapping_def.mapping_version,
                    is_active=True,
                )
            )
            mappings_inserted += 1
            continue
        changed = False
        if mapping.priority != mapping_def.priority:
            mapping.priority = mapping_def.priority
            changed = True
        if mapping.confidence != mapping_def.confidence:
            mapping.confidence = mapping_def.confidence
            changed = True
        if mapping.industry_applicability != mapping_def.industry_applicability:
            mapping.industry_applicability = mapping_def.industry_applicability
            changed = True
        if mapping.rationale != mapping_def.rationale:
            mapping.rationale = mapping_def.rationale
            changed = True
        if not mapping.is_active:
            mapping.is_active = True
            changed = True
        if changed:
            mappings_updated += 1

    return {
        "concepts_inserted": concepts_inserted,
        "concepts_updated": concepts_updated,
        "mappings_inserted": mappings_inserted,
        "mappings_updated": mappings_updated,
    }
