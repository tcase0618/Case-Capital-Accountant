# Canonical Taxonomy & XBRL Validation

## Overview

THE ACCOUNTANT Prompt 3 adds:
- XBRL instance validation via Arelle
- Canonical accounting taxonomy (40+ standardized concepts)
- Deterministic mapping rules from SEC XBRL to canonical concepts
- Canonical fact storage with lineage to raw facts
- Statement reconstruction foundation

This layer normalizes the chaos of XBRL filing variations into a consistent, auditable, versioned canonical model suitable for research and valuation.

## Architecture

### Problem: XBRL Filing Variability

SEC XBRL filings have evolved over time and vary by company:
- Multiple taxonomy versions (us-gaap evolves annually)
- Concept aliases and deprecated labels
- Alternative context/unit combinations for same economic fact
- Segment/dimension variants
- Custom/extension concepts per filing
- Validator divergence (some facts fail validation but are filed anyway)

**Solution:** Canonical taxonomy as abstraction layer.

### Canonical Taxonomy

Case Capital canonical taxonomy defines ~40 standardized concepts:
- **Balance Sheet**: Assets, Current Assets, Cash, AR, Inventory, PPE, etc.
- **Income Statement**: Revenue, COGS, Gross Profit, OpEx, R&D, SG&A, Operating Income, Interest, Taxes, Net Income
- **Cash Flow**: Operating, Investing, Financing CF, CapEx
- **Metrics**: Shares Outstanding, EPS, Book Value/Share, Ratios (D/E, Current, Quick, ROE, ROA, Margins, etc.)

Each canonical concept is:
- **Versioned**: Rules evolve as accounting standards change
- **Documented**: Label, description, category, unit hint
- **Mapped**: Links to one or more XBRL concepts (us-gaap, ifrs-full, etc.)
- **Auditable**: Mapping rules stored with confidence scores and rationale

### Mapping Engine

Deterministic mapping from raw (taxonomy, concept) → canonical concept.

**Mapping rules include:**
- Source taxonomy (us-gaap, ifrs-full, etc.)
- Source concept name
- Target canonical concept ID
- Priority (100 = highest, used to break ties)
- Confidence (HIGH, MEDIUM, LOW)
- Industry applicability (nullable)
- Rationale (why this mapping)
- Version (for backwards compatibility)

**Conflict resolution:**
1. Filter by industry if provided
2. Select highest priority
3. Select highest confidence
4. Warn/skip if still ambiguous

### Canonical Facts

Once a raw fact maps to a canonical concept, it becomes a canonical fact:

```python
class CanonicalFact(Base):
    id: UUID                          # Unique identifier
    company_id: UUID                  # FK to company
    raw_fact_id: UUID                 # FK to raw fact (immutable lineage)
    canonical_concept_id: UUID        # FK to canonical concept
    value: str | None                 # Text value
    value_numeric: float | None       # Numeric value
    unit: str | None                  # Unit (USD, shares, etc.)
    mapping_rule: str | None          # Human description of mapping
    mapping_version: int              # Version of mapping rules used
    mapping_confidence: str           # HIGH/MEDIUM/LOW
    reported_or_derived: str          # reported = from filing; derived = calculated
    notes: str | None                 # Additional context
    created_at: datetime              # Ingestion timestamp
```

**Lineage:** Every canonical fact links back to exactly one raw fact, preserving full audit trail.

**Confidence tiers:**
- `HIGH`: Definitive mapping (e.g., us-gaap:Assets → CC_ASSETS)
- `MEDIUM`: Probable mapping with caveats (e.g., non-US company using adapted taxonomy)
- `LOW`: Speculative/guessed mapping (store but flag for review)

**Reported vs. Derived:**
- `reported`: Fact came directly from XBRL instance
- `derived`: Fact calculated from other facts (future formulas)

## XBRL Validation

### Arelle Integration

[Arelle](https://arelle.org/) is the standard open-source XBRL validator. THE ACCOUNTANT includes:

**`ArelleFacade`** — wrapper for Arelle operations:
- `validate_instance(instance_url, plugins)` → XbrlValidationResult
- `extract_facts(instance_url)` → list[XbrlFact]
- `validate_and_extract(instance_url, plugins)` → (result, facts)

**Validation levels:**
- `is_valid=True`: Instance passes all validity checks
- `is_valid=False`: Instance has errors (facts may still be extractable)
- Errors collected separately from warnings

### Validation Workflow

```
Filing Instance (XML)
        ↓
  [Arelle Validation]
        ↓
   is_valid? ──Yes──→ Extract Facts
        ↓
       No → Log Errors, Continue
        ↓
   Fact Extraction (all contexts)
        ↓
   For each fact:
     - Resolve context (entity, period)
     - Resolve unit
     - Parse value (numeric/text/boolean)
     - Store as XbrlFact
        ↓
   Persist to raw_facts (if accession linked)
```

### Known Validation Issues

1. **Deprecated concepts** — Earlier SEC filings use deprecated taxonomy versions. Validator may flag these, but facts are still economically valid.
2. **Custom extensions** — Companies extend taxonomy with custom concepts. Validator flags but doesn't reject.
3. **Amendment conflicts** — Amended filings sometimes have validation issues not present in original. Stored as separate facts.

**Approach:** Validate but don't reject. Log all errors, capture all facts extractable, allow researcher to assess validity.

## CLI Commands

### List Canonical Concepts

```bash
accountant taxonomy

# Filter by category
accountant taxonomy --category "Balance Sheet"
accountant taxonomy --category "Metrics"
```

Output: Table of canonical concepts with code, label, category, unit hint.

### Explain a Concept

```bash
accountant explain CC_REVENUE
accountant explain CC_DEBT_TO_EQUITY
```

Output: Full definition with description, category, unit hint, version.

### Find Mapping Candidates

```bash
accountant candidates us-gaap Assets
accountant candidates ifrs-full CurrentAssets
```

Output: Candidate canonical concepts ranked by priority and confidence, with rationale.

### (Future) Map a Filing

```bash
accountant normalize --filing 0000320193-24-000001 --version 1
```

Output: Summary of facts mapped, unmapped, ambiguous.

## Database Schema

### canonical_concepts

```sql
CREATE TABLE canonical_concepts (
  id UUID PRIMARY KEY,
  code VARCHAR(64) UNIQUE NOT NULL,
  label VARCHAR(255) NOT NULL,
  description TEXT,
  category VARCHAR(64),
  unit_hint VARCHAR(32),
  is_active BOOLEAN DEFAULT TRUE,
  version INTEGER DEFAULT 1,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_canonical_concepts_code ON canonical_concepts(code);
```

### canonical_mappings

```sql
CREATE TABLE canonical_mappings (
  id UUID PRIMARY KEY,
  canonical_concept_id UUID NOT NULL FK,
  taxonomy VARCHAR(64) NOT NULL,
  source_concept VARCHAR(255) NOT NULL,
  priority INTEGER DEFAULT 100,
  confidence VARCHAR(32) DEFAULT 'HIGH',
  industry_applicability VARCHAR(64),
  rationale TEXT,
  mapping_version INTEGER DEFAULT 1,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_canonical_mappings_canonical_concept_id
  ON canonical_mappings(canonical_concept_id);
```

### canonical_facts

```sql
CREATE TABLE canonical_facts (
  id UUID PRIMARY KEY,
  company_id UUID NOT NULL FK,
  raw_fact_id UUID NOT NULL FK,
  canonical_concept_id UUID NOT NULL FK,
  value VARCHAR(1024),
  value_numeric NUMERIC(20, 4),
  unit VARCHAR(32),
  mapping_rule VARCHAR(255),
  mapping_version INTEGER DEFAULT 1,
  mapping_confidence VARCHAR(32) DEFAULT 'HIGH',
  reported_or_derived VARCHAR(32) DEFAULT 'reported',
  notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_canonical_facts_company_id ON canonical_facts(company_id);
CREATE INDEX ix_canonical_facts_raw_fact_id ON canonical_facts(raw_fact_id);
CREATE INDEX ix_canonical_facts_canonical_concept_id 
  ON canonical_facts(canonical_concept_id);
```

## API

### Canonical Registry

```python
from accountant.taxonomy import get_canonical_registry

registry = get_canonical_registry()

# Get single concept
concept = registry.get_concept("CC_REVENUE")
# → CanonicalConceptDef(code, label, description, category, unit_hint)

# List all concepts
all_concepts = registry.list_concepts()

# Filter by category
bs_concepts = registry.list_concepts("Balance Sheet")

# Get categories
categories = registry.categories()
# → {"Balance Sheet", "Income Statement", "Cash Flow", "Metrics"}

# Count
total = registry.count()  # → 40+
```

### Canonical Mapper

```python
from accountant.ingest.canonical_mapper import CanonicalMapper

mapper = CanonicalMapper(session)

# Map single fact to canonical
result = mapper.map_fact(
    raw_fact,
    industry="Technology",  # Optional
    mapping_version=1
)
# → MappingResult(canonical_concept_code, confidence, mapping_rule, notes)

# Find candidates for a concept pair
candidates = mapper.find_candidates("us-gaap", "Assets")
# → [CanonicalMapping, ...]  sorted by priority

# Detect conflicts
has_conflict = mapper.detect_conflict("us-gaap", "Assets", candidates)

# Resolve conflict
selected = mapper.resolve_conflict("us-gaap", "Assets", candidates)
```

### Canonical Ingestion

```python
from accountant.ingest.canonical_ingestion import CanonicalFactIngestion

ingester = CanonicalFactIngestion(session, arelle_facade)

# Ingest a filing
result = ingester.ingest_filing(
    filing,
    company,
    instance_url="https://...instance.xml",
    mapping_version=1
)
# → CanonicalIngestionResult(
#     raw_facts_processed: int,
#     canonical_facts_inserted: int,
#     facts_unmapped: int,
#     validation_passed: bool,
#     validation_errors: [str],
#     errors: [str]
#   )
```

## Testing

Test suite covers:

- **Registry tests**: Concept retrieval, listing, filtering, categories
- **Model tests**: CanonicalConcept, CanonicalMapping, CanonicalFact creation and relationships
- **Mapper tests**: Mapping, conflict detection, candidate finding
- **Validation tests**: Arelle dataclass structures, validation results
- **Integration tests**: Full ingestion workflow (pending)

Run:
```bash
uv run pytest tests/test_canonical.py -v
```

## Known Limitations

1. **Arelle integration stubbed** — Methods raise NotImplementedError pending full implementation
2. **Mapping rules hardcoded initially** — Will be database-driven in future
3. **No industry branching** — All companies use same rules currently
4. **No formula validation** — Consistency checks across facts not yet implemented
5. **No segment parsing** — Dimensions/members not extracted
6. **No period reconciliation** — Frame/instant/duration not canonicalized

## Future Work (Prompt 4+)

1. **Period resolver** — Map frame/instant/duration to canonical periods
2. **Arelle live validation** — Implement actual validation via Python Arelle bindings
3. **Statement reconstruction** — Build GL, IS, BS from canonical facts
4. **Formula engine** — Validate fact relationships and compute derived facts
5. **Industry-specific rules** — Banking, Insurance, Pharma custom mappings
6. **Amendment reconciliation** — Track fact changes across amendments
7. **Segment extraction** — Parse and normalize dimension facts
8. **Metric derivation** — Calculate ratios, growth rates, etc. from facts

## What's NOT in Prompt 3 (Out of Scope)

- Live Arelle validation (framework only)
- Period reconciliation
- Statement reconstruction
- Formula validation
- Metric calculation
- Valuation models
- Forensic accounting
- Segment analysis
- Amendment handling

---

## Example: Mapping Assets

**Scenario:** AAPL 10-K with us-gaap:Assets in 2024 filing.

1. **Raw Fact:** us-gaap:Assets = 352,755,000 (USD, instant 2024-09-28)
2. **Lookup:** Find canonical mappings for (us-gaap, Assets)
   - Match: CC_ASSETS (priority 100, confidence HIGH)
   - Result: Single, high-confidence candidate
3. **Resolve:** Select CC_ASSETS
4. **Store CanonicalFact:**
   - company_id = AAPL's UUID
   - raw_fact_id = original fact's UUID
   - canonical_concept_id = CC_ASSETS's UUID
   - value_numeric = 352755000.00
   - unit = USD
   - mapping_rule = "us-gaap:Assets → CC_ASSETS"
   - mapping_confidence = HIGH
   - reported_or_derived = reported

Result: Auditable mapping from raw to canonical, full lineage preserved.

---

## Summary

Canonical taxonomy is THE ACCOUNTANT's abstraction layer over XBRL chaos:
- ✅ 40+ standardized concepts covering BS, IS, CF, metrics
- ✅ Versioned, deterministic mapping rules
- ✅ Full lineage via raw_fact_id → canonical_fact_id
- ✅ Confidence scores for validation
- ✅ Database-driven for auditability
- ✅ CLI tools for exploration and debugging

**Ready for Prompt 4:** Statement reconstruction using canonical facts as building blocks.

---

## Files

- `src/accountant/db/models/canonical_concept.py` — Model
- `src/accountant/db/models/canonical_mapping.py` — Model
- `src/accountant/db/models/canonical_fact.py` — Model
- `src/accountant/xbrl/arelle_adapter.py` — Arelle wrapper
- `src/accountant/taxonomy/canonical_registry.py` — Concept registry
- `src/accountant/ingest/canonical_mapper.py` — Mapping engine
- `src/accountant/ingest/canonical_ingestion.py` — Ingestion workflow
- `alembic/versions/003_canonical_schema.py` — Database migration
- `tests/test_canonical.py` — Test suite
- `docs/canonical_taxonomy.md` — This document
