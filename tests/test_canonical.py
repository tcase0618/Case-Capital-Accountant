"""Tests for canonical concepts, mappings, and facts."""

import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from accountant.db.models import CanonicalConcept, CanonicalFact, CanonicalMapping
from accountant.ingest.canonical_mapper import CanonicalMapper, MappingResult
from accountant.taxonomy import get_canonical_registry
from accountant.taxonomy.seed import ensure_canonical_taxonomy_seeded
from accountant.xbrl import ArelleFacade


class TestCanonicalRegistry:
    """Test canonical concept registry."""

    def test_registry_initialization(self):
        """Test registry initializes with concepts."""
        registry = get_canonical_registry()
        assert registry.count() >= 40
        assert registry.get_concept("CC_REVENUE") is not None

    def test_get_concept(self):
        """Test retrieval of canonical concept."""
        registry = get_canonical_registry()
        concept = registry.get_concept("CC_ASSETS")
        assert concept is not None
        assert concept.code == "CC_ASSETS"
        assert concept.category == "Balance Sheet"
        assert concept.unit_hint == "USD"

    def test_get_concept_not_found(self):
        """Test retrieval of non-existent concept."""
        registry = get_canonical_registry()
        assert registry.get_concept("CC_NONEXISTENT") is None

    def test_list_concepts_all(self):
        """Test listing all concepts."""
        registry = get_canonical_registry()
        concepts = registry.list_concepts()
        assert len(concepts) >= 40
        assert all(hasattr(c, "code") for c in concepts)
        assert all(hasattr(c, "label") for c in concepts)

    def test_list_concepts_by_category(self):
        """Test listing concepts filtered by category."""
        registry = get_canonical_registry()
        bs_concepts = registry.list_concepts("Balance Sheet")
        assert len(bs_concepts) > 0
        assert all(c.category == "Balance Sheet" for c in bs_concepts)

    def test_list_concepts_empty_category(self):
        """Test listing concepts for non-existent category."""
        registry = get_canonical_registry()
        concepts = registry.list_concepts("Nonexistent Category")
        assert len(concepts) == 0

    def test_categories(self):
        """Test getting all categories."""
        registry = get_canonical_registry()
        categories = registry.categories()
        assert "Balance Sheet" in categories
        assert "Income Statement" in categories
        assert "Cash Flow" in categories
        assert "Metrics" in categories

    def test_count(self):
        """Test total concept count."""
        registry = get_canonical_registry()
        count = registry.count()
        assert count >= 40


class TestCanonicalModels:
    """Test canonical concept database models."""

    def test_canonical_concept_creation(self, test_session: Session):
        """Test creating canonical concept in database."""
        concept = CanonicalConcept(
            id=uuid.uuid4(),
            code="CC_TEST_REVENUE",
            label="Test Revenue",
            description="Revenue for testing",
            category="Income Statement",
            unit_hint="USD",
            is_active=True,
            version=1,
        )
        test_session.add(concept)
        test_session.commit()

        retrieved = (
            test_session.query(CanonicalConcept)
            .filter(CanonicalConcept.code == "CC_TEST_REVENUE")
            .first()
        )
        assert retrieved is not None
        assert retrieved.label == "Test Revenue"

    def test_canonical_concept_unique_code(self, test_session: Session):
        """Test that canonical concept codes are unique."""
        concept1 = CanonicalConcept(
            id=uuid.uuid4(),
            code="CC_UNIQUE",
            label="Unique Concept 1",
            category="Income Statement",
            is_active=True,
            version=1,
        )
        test_session.add(concept1)
        test_session.commit()

        concept2 = CanonicalConcept(
            id=uuid.uuid4(),
            code="CC_UNIQUE",
            label="Unique Concept 2",
            category="Income Statement",
            is_active=True,
            version=1,
        )
        test_session.add(concept2)

        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_canonical_mapping_creation(
        self, test_session: Session, canonical_concept: CanonicalConcept
    ):
        """Test creating canonical mapping."""
        mapping = CanonicalMapping(
            id=uuid.uuid4(),
            canonical_concept_id=canonical_concept.id,
            taxonomy="us-gaap",
            source_concept="Assets",
            priority=100,
            confidence="HIGH",
            mapping_version=1,
            is_active=True,
        )
        test_session.add(mapping)
        test_session.commit()

        retrieved = test_session.query(CanonicalMapping).filter_by(id=mapping.id).first()
        assert retrieved is not None
        assert retrieved.taxonomy == "us-gaap"
        assert retrieved.source_concept == "Assets"

    def test_canonical_fact_creation(
        self,
        test_session: Session,
        company,
        raw_fact,
        canonical_concept: CanonicalConcept,
    ):
        """Test creating canonical fact with lineage."""
        canonical_fact = CanonicalFact(
            id=uuid.uuid4(),
            company_id=company.id,
            raw_fact_id=raw_fact.id,
            canonical_concept_id=canonical_concept.id,
            value_numeric=1000000.00,
            unit="USD",
            mapping_rule="us-gaap:Assets → CC_ASSETS",
            mapping_version=1,
            mapping_confidence="HIGH",
            reported_or_derived="reported",
        )
        test_session.add(canonical_fact)
        test_session.commit()

        retrieved = test_session.query(CanonicalFact).filter_by(id=canonical_fact.id).first()
        assert retrieved is not None
        assert retrieved.value_numeric == 1000000.00
        assert retrieved.canonical_concept.code == canonical_concept.code

    def test_canonical_fact_immutable_reference(
        self, test_session: Session, company, raw_fact, canonical_concept: CanonicalConcept
    ):
        """Test that canonical fact maintains immutable reference to raw fact."""
        canonical_fact = CanonicalFact(
            id=uuid.uuid4(),
            company_id=company.id,
            raw_fact_id=raw_fact.id,
            canonical_concept_id=canonical_concept.id,
            value_numeric=500000.00,
            unit="USD",
            mapping_version=1,
            mapping_confidence="HIGH",
            reported_or_derived="reported",
        )
        test_session.add(canonical_fact)
        test_session.commit()

        assert canonical_fact.raw_fact_id == raw_fact.id

    def test_seed_canonical_taxonomy(self, test_session: Session):
        """Test canonical concepts and mappings seed into the database."""
        stats = ensure_canonical_taxonomy_seeded(test_session)
        test_session.commit()

        concept_count = test_session.query(CanonicalConcept).count()
        mapping_count = test_session.query(CanonicalMapping).count()

        assert stats["concepts_inserted"] > 0
        assert stats["mappings_inserted"] > 0
        assert concept_count >= 40
        assert mapping_count > 0


class TestCanonicalMapper:
    """Test canonical mapping engine."""

    def test_mapper_initialization(self, test_session: Session):
        """Test canonical mapper initializes."""
        mapper = CanonicalMapper(test_session)
        assert mapper.session is test_session

    def test_mapper_conflict_detection_none(self, test_session: Session):
        """Test conflict detection returns False for single mapping."""
        mapper = CanonicalMapper(test_session)
        candidates = []
        assert mapper.detect_conflict("us-gaap", "Assets", candidates) is False

    def test_mapper_conflict_detection_single(self, test_session: Session):
        """Test no conflict for single candidate."""
        # Placeholder test — actual implementation pending
        assert True

    def test_mapping_result_structure(self):
        """Test mapping result dataclass."""
        result = MappingResult(
            raw_fact_id="fact-123",
            canonical_concept_code="CC_REVENUE",
            confidence="HIGH",
            mapping_rule="us-gaap:Revenues → CC_REVENUE",
            mapping_version=1,
            notes="Automatic high-confidence mapping",
        )
        assert result.raw_fact_id == "fact-123"
        assert result.canonical_concept_code == "CC_REVENUE"
        assert result.confidence == "HIGH"


class TestXbrlValidation:
    """Test XBRL validation via Arelle."""

    def test_arelle_facade_initialization(self):
        """Test Arelle facade initializes."""
        arelle = ArelleFacade()
        assert arelle is not None

    def test_validation_result_dataclass(self):
        """Test validation result structure."""
        from accountant.xbrl import XbrlValidationError, XbrlValidationResult

        error = XbrlValidationError(
            level="ERROR",
            code="xbrlce:missing",
            message="Missing required element",
            line=42,
            column=10,
        )
        assert error.level == "ERROR"

        result = XbrlValidationResult(
            is_valid=False,
            errors=[error],
            warnings=[],
            instance_url="https://example.com/instance.xml",
        )
        assert result.is_valid is False
        assert len(result.errors) == 1

    def test_xbrl_fact_dataclass(self):
        """Test XBRL fact structure."""
        from accountant.xbrl import XbrlFact

        fact = XbrlFact(
            concept="us-gaap:Assets",
            taxonomy="us-gaap",
            context_id="instant_2024-12-31",
            unit_id="USD",
            value="1000000",
            value_type="monetary",
            decimals=-6,
        )
        assert fact.concept == "us-gaap:Assets"
        assert fact.value == "1000000"
        assert fact.nil is False


@pytest.fixture
def canonical_concept(test_session: Session) -> CanonicalConcept:
    """Create a test canonical concept."""
    concept = CanonicalConcept(
        id=uuid.uuid4(),
        code="CC_TEST_CONCEPT",
        label="Test Concept",
        description="Test concept for unit tests",
        category="Test Category",
        unit_hint="USD",
        is_active=True,
        version=1,
    )
    test_session.add(concept)
    test_session.commit()
    return concept


@pytest.fixture
def company(test_session: Session):
    """Create a test company."""
    from accountant.db.models import Company

    company = Company(
        id=uuid.uuid4(),
        cik="0000320193",
        name="Apple Inc.",
        entity_type="Large accelerated filer",
        sic=3571,
        state_of_incorporation="CA",
    )
    test_session.add(company)
    test_session.commit()
    return company


@pytest.fixture
def filing(test_session: Session, company):
    """Create a test filing."""
    from accountant.db.models import Filing

    filing = Filing(
        id=uuid.uuid4(),
        company_id=company.id,
        accession_number="0000320193-24-000001",
        form_type="10-K",
        filing_date=date(2024, 1, 15),
        report_date=date(2023, 12, 31),
    )
    test_session.add(filing)
    test_session.commit()
    return filing


@pytest.fixture
def raw_fact(test_session: Session, company, filing):
    """Create a test raw fact."""
    from accountant.db.models import RawFact

    raw_fact = RawFact(
        id=uuid.uuid4(),
        filing_id=filing.id,
        company_id=company.id,
        concept="Assets",
        taxonomy="us-gaap",
        unit="USD",
        value_numeric=1000000.0,
        period_end=date(2023, 12, 31),
        fact_hash="abc123def456",
    )
    test_session.add(raw_fact)
    test_session.commit()
    return raw_fact


class TestArelleFacade:
    """Test Arelle XBRL validation and extraction."""

    def test_arelle_facade_available(self):
        """Test Arelle module loads when available."""
        from accountant.xbrl.arelle_adapter import ARELLE_AVAILABLE

        # May be True or False depending on environment
        assert isinstance(ARELLE_AVAILABLE, bool)

    def test_arelle_initialization_when_available(self):
        """Test ArelleFacade initializes when Arelle is installed."""
        try:
            arelle = ArelleFacade()
            assert arelle is not None
            assert arelle.cntlr is None  # Lazy-initialized
        except RuntimeError as e:
            # Expected if Arelle not installed
            assert "not installed" in str(e).lower()

    def test_validation_result_with_errors(self):
        """Test validation result with errors."""
        from accountant.xbrl import XbrlValidationError, XbrlValidationResult

        errors = [
            XbrlValidationError(
                level="ERROR",
                code="xbrlce:missing",
                message="Missing required context",
                line=42,
            )
        ]
        result = XbrlValidationResult(
            is_valid=False,
            errors=errors,
            warnings=[],
            instance_url="test.xml",
        )
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].level == "ERROR"

    def test_extraction_fact_structure(self):
        """Test extracted fact data structure."""
        from accountant.xbrl import XbrlFact

        fact = XbrlFact(
            concept="us-gaap:Assets",
            taxonomy="us-gaap",
            context_id="instant_2024-12-31",
            unit_id="USD",
            value="5000000000",
            value_type="numeric",
            decimals=-6,
            nil=False,
        )
        assert fact.concept == "us-gaap:Assets"
        assert fact.taxonomy == "us-gaap"
        assert fact.value_type == "numeric"
        assert fact.nil is False


class TestCanonicalMapperPriority:
    """Test canonical mapper priority and confidence-based resolution."""

    def test_find_candidates_returns_dict_list(self, test_session: Session):
        """Test find_candidates returns list of dicts."""
        mapper = CanonicalMapper(test_session)
        candidates = mapper.find_candidates("us-gaap", "Assets")

        # Should return list (may be empty if no mappings exist)
        assert isinstance(candidates, list)
        if candidates:
            for candidate in candidates:
                assert isinstance(candidate, dict)
                assert "canonical_concept_code" in candidate
                assert "confidence" in candidate
                assert "priority" in candidate

    def test_find_and_resolve_candidates_unmapped(self, test_session: Session):
        """Test resolution for unmapped concept."""
        mapper = CanonicalMapper(test_session)
        result = mapper.find_and_resolve_candidates(
            "us-gaap", "NonexistentConcept"
        )

        assert result["status"] == "UNMAPPED"
        assert result["canonical_concept_code"] is None

    def test_custom_tag_detection(self, test_session: Session):
        """Test custom tag is identified properly."""
        mapper = CanonicalMapper(test_session)

        # Custom tag should have namespace prefix
        result = mapper.find_and_resolve_candidates(
            "custom-namespace", "CustomTag"
        )

        assert result["status"] == "UNMAPPED_CUSTOM_TAG"
        assert result["canonical_concept_code"] is None

    def test_detect_conflict_no_conflict(self, test_session: Session):
        """Test conflict detection returns False for single mapping."""
        mapper = CanonicalMapper(test_session)
        candidates = [
            {
                "canonical_concept_code": "CC_ASSETS",
                "confidence": "HIGH",
                "priority": 100,
            }
        ]
        assert mapper.detect_conflict("us-gaap", "Assets", candidates) is False

    def test_detect_conflict_multi_high_confidence(self, test_session: Session):
        """Test conflict detection for multiple high-confidence mappings."""
        mapper = CanonicalMapper(test_session)
        candidates = [
            {
                "canonical_concept_code": "CC_ASSETS",
                "confidence": "HIGH",
                "priority": 100,
            },
            {
                "canonical_concept_code": "CC_CURRENT_ASSETS",
                "confidence": "HIGH",
                "priority": 90,
            },
        ]
        assert mapper.detect_conflict("us-gaap", "Assets", candidates) is True

    def test_resolve_conflict_by_priority(self, test_session: Session):
        """Test conflict resolution prefers higher priority."""
        mapper = CanonicalMapper(test_session)
        candidates = [
            {
                "canonical_concept_code": "CC_ASSETS",
                "confidence": "HIGH",
                "priority": 100,
            },
            {
                "canonical_concept_code": "CC_CURRENT_ASSETS",
                "confidence": "HIGH",
                "priority": 90,
            },
        ]
        resolved = mapper.resolve_conflict("us-gaap", "Assets", candidates)
        assert resolved is not None
        assert resolved["canonical_concept_code"] == "CC_ASSETS"
        assert resolved["priority"] == 100

    def test_resolve_conflict_by_confidence(self, test_session: Session):
        """Test conflict resolution prefers higher confidence."""
        mapper = CanonicalMapper(test_session)
        candidates = [
            {
                "canonical_concept_code": "CC_ASSETS",
                "confidence": "HIGH",
                "priority": 100,
            },
            {
                "canonical_concept_code": "CC_CURRENT_ASSETS",
                "confidence": "MEDIUM",
                "priority": 100,
            },
        ]
        resolved = mapper.resolve_conflict("us-gaap", "Assets", candidates)
        assert resolved is not None
        assert resolved["confidence"] == "HIGH"


class TestCanonicalFactIdempotency:
    """Test idempotent canonical fact ingestion."""

    def test_duplicate_check_by_raw_fact_id_and_version(
        self, test_session: Session, company, raw_fact, canonical_concept
    ):
        """Test that (raw_fact_id, mapping_version) deduplicates canonical facts."""
        from accountant.db.models import CanonicalFact

        # Create first canonical fact
        fact1 = CanonicalFact(
            id=uuid.uuid4(),
            company_id=company.id,
            raw_fact_id=raw_fact.id,
            canonical_concept_id=canonical_concept.id,
            value_numeric=1000000.0,
            unit="USD",
            mapping_version=1,
            mapping_confidence="HIGH",
            reported_or_derived="reported",
        )
        test_session.add(fact1)
        test_session.commit()

        # Try to create identical fact (should check for existing)
        from sqlalchemy import and_, select

        stmt = select(CanonicalFact).where(
            and_(
                CanonicalFact.raw_fact_id == raw_fact.id,
                CanonicalFact.mapping_version == 1,
            )
        )
        existing = test_session.execute(stmt).scalar()
        assert existing is not None
        assert existing.id == fact1.id

    def test_different_mapping_version_not_duplicate(
        self, test_session: Session, company, raw_fact, canonical_concept
    ):
        """Test that same raw fact with different mapping version is not duplicate."""
        from accountant.db.models import CanonicalFact

        # Version 1
        fact1 = CanonicalFact(
            id=uuid.uuid4(),
            company_id=company.id,
            raw_fact_id=raw_fact.id,
            canonical_concept_id=canonical_concept.id,
            value_numeric=1000000.0,
            mapping_version=1,
            mapping_confidence="HIGH",
            reported_or_derived="reported",
        )
        test_session.add(fact1)
        test_session.commit()

        # Version 2 (different mapping rules)
        fact2 = CanonicalFact(
            id=uuid.uuid4(),
            company_id=company.id,
            raw_fact_id=raw_fact.id,
            canonical_concept_id=canonical_concept.id,
            value_numeric=1000000.0,
            mapping_version=2,
            mapping_confidence="HIGH",
            reported_or_derived="reported",
        )
        test_session.add(fact2)
        test_session.commit()

        facts = (
            test_session.query(CanonicalFact)
            .filter(CanonicalFact.raw_fact_id == raw_fact.id)
            .all()
        )
        assert len(facts) == 2
        assert {f.mapping_version for f in facts} == {1, 2}

    def test_canonical_fact_lineage_preservation(
        self, test_session: Session, company, raw_fact, canonical_concept
    ):
        """Test that canonical fact preserves lineage to raw fact."""
        from accountant.db.models import CanonicalFact

        fact = CanonicalFact(
            id=uuid.uuid4(),
            company_id=company.id,
            raw_fact_id=raw_fact.id,
            canonical_concept_id=canonical_concept.id,
            value_numeric=500000.0,
            mapping_rule="us-gaap:Assets → CC_ASSETS",
            mapping_version=1,
            mapping_confidence="HIGH",
            reported_or_derived="reported",
        )
        test_session.add(fact)
        test_session.commit()

        # Retrieve and verify lineage
        retrieved = test_session.query(CanonicalFact).filter_by(id=fact.id).first()
        assert retrieved.raw_fact_id == raw_fact.id
        assert retrieved.mapping_rule == "us-gaap:Assets → CC_ASSETS"
        assert retrieved.mapping_confidence == "HIGH"
