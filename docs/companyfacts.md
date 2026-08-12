# CompanyFacts Ingestion & XBRL Raw Facts

## Overview

THE ACCOUNTANT Prompt 2 adds support for SEC CompanyFacts API ingestion, raw XBRL fact normalization, and deterministic fact deduplication. All facts remain immutable once ingested.

## Architecture

### CompanyFacts API

SEC CompanyFacts API provides pre-extracted XBRL instance facts as JSON. Each fact represents:
- A taxonomy concept (e.g., `us-gaap:Assets`)
- A value (numeric or text)
- A unit (e.g., USD, shares)
- A period (instant date, start/end dates, or frame)
- A filing (accession number, form type, filed date)

Source: `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`

### CompanyConcept API

Retrieves historical values for a single concept across all filings:

Source: `https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{concept}.json`

## Raw Fact Storage

### RawFact Model

Extended with CompanyFacts-specific fields:

```python
class RawFact(Base):
    # Core XBRL fields
    concept: str                          # e.g., "Assets"
    taxonomy: str | None                  # e.g., "us-gaap"
    unit: str | None                      # e.g., "USD"
    value_numeric: float | None           # Numeric value
    value_text: str | None                # Text value
    
    # Period
    period_start: date | None             # Duration start
    period_end: date | None               # Duration end
    instant_date: date | None             # Point-in-time
    
    # CompanyFacts metadata
    accession_number: str | None          # Filing accession (10-digit padded)
    fiscal_year: int | None               # Fiscal year (e.g., 2024)
    fiscal_period: str | None             # Fiscal period ("FY", "Q1", "Q2", etc.)
    frame: str | None                     # Frame (e.g., "CY2024", "CY2024Q1")
    form: str | None                      # Form type (e.g., "10-K", "10-Q")
    filed_date: date | None               # When filed with SEC
    
    # Labels & descriptions
    label: str | None                     # Concept label
    description: str | None               # Concept description
    
    # Source tracking
    source_type: str                      # "xbrl", "companyfacts", etc. (default: "xbrl")
    fact_hash: str                        # Deterministic identity hash (unique)
    
    # Immutability
    created_at: datetime                  # Ingestion timestamp
    ingested_at: datetime                 # When ingested (server default)
```

### Fact Immutability

Raw facts are insert-only. Attempting to UPDATE raises `RuntimeError`:

```python
fact.value_numeric = 2000000
session.flush()  # ← RuntimeError: raw_facts are immutable
```

Corrections are new rows with updated values and provenance.

## Fact Deduplication

### Deterministic Hashing

`compute_fact_hash()` generates a unique identity based on economically distinct attributes:

```python
hash = compute_fact_hash(
    company_id="uuid",
    taxonomy="us-gaap",
    concept="Assets",
    accession="0000320193-24-000001",
    unit="USD",
    start="2023-01-01",
    end="2023-12-31",
    instant=None,
    value=1000000,
)
```

**Includes:**
- Company ID
- Taxonomy & concept
- Accession number (unique to filing)
- Unit
- Period (start, end, instant)
- **Value** (distinguishes amendments, restarts, corrections)

**Does NOT include:**
- Decimals (metadata only)
- Frame or label (derived from period)
- Ingestion timestamp

### Deduplication Strategy

On ingestion:
1. Compute fact hash
2. Query `raw_facts` for existing hash
3. If found → skip (return `False`)
4. If not found → insert (return `True`)

**Result:** Repeated ingestion of identical CompanyFacts data creates no duplicates.

## Filing Linkage

Each raw fact attempts to link to an existing filing via `accession_number`:

```python
# If accession matches a filing in the database
filing = session.query(Filing).filter(
    Filing.accession_number == accession
).first()

if filing:
    raw_fact.filing_id = filing.id  # RESTRICT on delete
```

**Behavior:**
- **Accession found** → Link to filing; fact depends on filing (RESTRICT prevents orphaning)
- **Accession not found** → Fact remains with filing_id link (still requires a filing to insert)

## Ingestion API

### CompanyFactsClient

```python
from accountant.sec.companyfacts import CompanyFactsClient
from accountant.config import get_settings

settings = get_settings()
client = CompanyFactsClient(settings=settings)

# Fetch CompanyFacts JSON for a CIK
facts_data = client.get_company_facts("0000320193")  # Apple

# Fetch concept history
concept_data = client.get_company_concept(
    cik="0000320193",
    taxonomy="us-gaap",
    concept="Assets"
)

client.close()
```

### ingest_company_facts_for_company()

```python
from accountant.ingest.companyfacts import ingest_company_facts_for_company

result = ingest_company_facts_for_company(
    session=session,
    company=company_record,
    companyfacts_client=client,
    sec_client=sec_client
)

print(f"Inserted: {result.facts_inserted}")
print(f"Skipped:  {result.facts_skipped}")
print(f"Errors:   {result.errors}")
```

**Result fields:**
- `cik`, `ticker`, `company_name`
- `concepts_processed` — unique concepts found in CompanyFacts
- `facts_inserted` — newly inserted facts
- `facts_skipped` — duplicate (existing hash)
- `errors` — list of non-fatal errors

### query_facts()

```python
from accountant.ingest.companyfacts import query_facts

facts = query_facts(
    session=session,
    company_id=str(company.id),
    concept="Assets",           # Optional
    taxonomy="us-gaap",         # Optional
    form="10-K",                # Optional
    limit=100
)

for fact in facts:
    print(f"{fact.concept}: {fact.value_numeric} {fact.unit}")
```

## CLI Commands

### Ingest CompanyFacts

```bash
accountant ingest-companyfacts AAPL
```

Output:
```
Ingested for: AAPL (0000320193)
Company: Apple Inc.
Concepts processed: 247
Facts inserted: 15432
Facts skipped: 82
```

**Requires:**
- Company already ingested via `accountant ingest AAPL`
- SEC_USER_AGENT configured

### Query Facts

```bash
accountant facts AAPL --limit 20
accountant facts AAPL --concept Assets --taxonomy us-gaap
accountant facts AAPL --form 10-K
```

Output: Rich table with concept, taxonomy, form, period, value, unit.

### CompanyConcept History

```bash
accountant companyconcept AAPL us-gaap Assets
```

Output: Concept metadata + table of historical values with filed date, form, value.

## Known Limitations

1. **No filing linkage for unknown accessions**
   - If accession is not in the database, fact requires a valid `filing_id`
   - Current implementation: facts without linkage are skipped
   - Future: Consider storing orphan facts with accession reference

2. **No period resolver**
   - Frames are parsed naively (e.g., "CY2024Q1" → fiscal_year=2024, fiscal_period="Q1")
   - Does not handle special frames (e.g., "CY2024-Q1-13W")
   - Period resolution (matching to canonical periods) is out of scope for Prompt 2

3. **No canonical taxonomy**
   - Stores raw taxonomy/concept pairs as provided by SEC
   - Does not normalize XBRL taxonomy versions or aliases
   - Canonical mapping is Prompt 3+

4. **No amendments reconciliation**
   - Stores all facts from all filings, including amendments
   - Does not auto-detect superseded values
   - Amendment handling via explicit form detection (is_amendment on Filing)

5. **No segment/dimension handling**
   - `dimensions` JSON field exists but not populated
   - CompanyFacts API provides limited segment data
   - Full segment analysis is Prompt 4+

6. **No text fact analysis**
   - Stores text values as-is
   - No NLP or extraction
   - Text facts treated as opaque values

## Testing

Test suite covers:

- **Fact hashing** — deterministic identity, collision avoidance
- **Deduplication** — repeated ingestion produces no duplicates
- **Filtering** — query_facts with concept, taxonomy, form filters
- **Immutability** — UPDATE attempts raise RuntimeError
- **Client initialization** — CompanyFactsClient setup and cleanup
- **Mock responses** — CompanyFacts parsing without live SEC API

Run tests:
```bash
uv run pytest tests/test_companyfacts.py -v
```

## Error Handling

Ingestion is **non-blocking**:
- Missing optional fields → store as NULL (not errors)
- Malformed accession → stored as-is, filing linkage skipped
- Missing unit → stored with unit=None
- Unknown taxonomy → stored as-is
- Missing concept metadata (label, description) → skipped

Fatal errors (network, database):
- Logged at ERROR level
- Added to result.errors
- Ingestion continues for other concepts

## Migration

Schema changes in `alembic/versions/002_extend_raw_facts.py`:

```sql
ALTER TABLE raw_facts ADD COLUMN accession_number VARCHAR(24) NULL;
ALTER TABLE raw_facts ADD COLUMN fiscal_year INTEGER NULL;
ALTER TABLE raw_facts ADD COLUMN fiscal_period VARCHAR(16) NULL;
ALTER TABLE raw_facts ADD COLUMN frame VARCHAR(32) NULL;
ALTER TABLE raw_facts ADD COLUMN form VARCHAR(32) NULL;
ALTER TABLE raw_facts ADD COLUMN filed_date DATE NULL;
ALTER TABLE raw_facts ADD COLUMN label VARCHAR(512) NULL;
ALTER TABLE raw_facts ADD COLUMN description TEXT NULL;
ALTER TABLE raw_facts ADD COLUMN source_type VARCHAR(32) NOT NULL DEFAULT 'xbrl';

CREATE INDEX ix_raw_facts_accession_number ON raw_facts(accession_number);
```

Apply:
```bash
uv run alembic upgrade head
```

## Future Work (Prompt 3+)

- **Period resolver**: Map frame/start/end to canonical periods (e.g., "FY2024", "Q1FY2024")
- **Canonical taxonomy**: Normalize XBRL taxonomy versions and aliases
- **Segment extraction**: Parse and store dimension/member facts
- **Statement reconstruction**: Build GL, IS, BS from raw facts
- **Arelle validation**: Validate XBRL instances for consistency
- **Fact versioning**: Track when facts changed across amendments
- **Coverage metrics**: Report fact availability per company/concept/period
