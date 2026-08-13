# Financial Period Resolution

## Overview

The FinancialPeriodResolver is THE ACCOUNTANT's core module for classifying and deriving financial periods from SEC/XBRL facts. It determines whether a fact is an instant (balance sheet), quarter, half-year YTD, full year, or unknown period based on:

- **Actual XBRL dates** (authoritative): `instant_date` for balance sheet facts, `period_start` and `period_end` for income/cash flow
- **Duration tolerance** for 52/53-week fiscal calendars (not rigid calendar days)
- **Fiscal year end derivation** for non-December-31 year-ends
- **Confidence scoring** to flag derivation uncertainty
- **Full lineage tracking** for audit trails

## Problem Solved

SEC/XBRL filings provide **multiple period signals** that often conflict:

1. **Raw XBRL context dates** (`instant_date`, `period_start`, `period_end`)
2. **SEC metadata** (`fiscal_year`, `fiscal_period` field like "Q1", `frame` like "CY2024Q1")
3. **Form type** (10-K = annual, 10-Q = quarterly)
4. **Document dates** (filing date, report date)

The problem: **these signals don't always agree.** For example:
- XBRL `period_end` might be Oct 3, 2024 (52nd fiscal week)
- SEC `fiscal_period` field might say "Q3" (implies 9 months)
- `frame` might say "CY2024Q4" (implies calendar quarter)

**Solution:** Trust actual XBRL dates. Use them to determine period type deterministically, only referencing SEC metadata for hints and validation.

## Architecture

### Core Classes

#### `ResolvedPeriod` (Dataclass)

Result of period resolution. Contains:

```python
@dataclass(frozen=True)
class ResolvedPeriod:
    period_type: str              # INSTANT, Q1-Q4, FY, YTD_Q1-YTD_Q3, TTM, UNKNOWN
    fiscal_year: int | None       # Calendar year (or year ending in)
    fiscal_quarter: int | None    # 1, 2, 3, 4 (for periods that map to Q)
    start_date: date | None       # Duration period start
    end_date: date | None         # Duration period end
    instant_date: date | None     # Instant (balance sheet) date
    duration_days: int | None     # (end_date - start_date) + 1
    fiscal_year_end: str | None   # MMDD format, e.g., '1231' for Dec 31
    is_ytd: bool                  # True if 6M/9M YTD
    is_derived: bool              # True if derived from YTD facts
    confidence: str               # HIGH, MEDIUM, LOW, UNKNOWN
    warnings: list[str] | None    # Issues during resolution
    notes: str | None             # Free-form annotations
```

#### `FinancialPeriodResolver` (Main Resolver)

```python
class FinancialPeriodResolver:
    def resolve_period(
        company_cik: str,
        instant_date: date | None,
        start_date: date | None,
        end_date: date | None,
        fiscal_year: int | None,                # SEC metadata (not trusted blindly)
        fiscal_period: str | None,              # "Q1", "Q2", "FY" (not trusted blindly)
        frame: str | None,                      # "CY2024Q1" (not trusted blindly)
        form: str | None,                       # "10-K", "10-Q"
        decimals: int | None,                   # Precision hint
    ) -> ResolvedPeriod:
```

### Supported Period Types

| Type | Duration | Confidence | Use Case |
|------|----------|-----------|----------|
| **INSTANT** | — | HIGH | Balance sheet facts (Assets, Liabilities, Equity) |
| **Q1-Q4** | 88-95 days | HIGH | Income statement and cash flow quarters |
| **FY** | 365-366 days | HIGH | Full fiscal year (52-week) |
| **FY** (53-week) | 371-374 days | MEDIUM | Extended fiscal year (retail, etc.) |
| **YTD_Q2** | 181-188 days | MEDIUM | 6-month year-to-date (Jan-Jun) |
| **YTD_Q3** | 273-283 days | MEDIUM | 9-month year-to-date (Jan-Sep) |
| **TTM** | ~365 days | LOW | Trailing twelve months (stub period overlap) |
| **UNKNOWN** | Any other | LOW | Ambiguous or malformed |

### Period Detection Logic

#### Instant Facts (Balance Sheets)

```
if instant_date is provided:
    period_type = INSTANT
    confidence = HIGH
    fiscal_quarter = None
```

Balance sheet items report a single point-in-time value (e.g., assets at end of quarter).

#### Duration Facts (Income Statements, Cash Flows)

Classification is based on **actual duration in days**:

1. **Check for year-long periods:**
   - 364-366 days → **FY (52-week)**, confidence=HIGH
   - 371-374 days → **FY (53-week)**, confidence=MEDIUM

2. **Check for quarter-long periods:**
   - 88-95 days → **Q1/Q2/Q3/Q4** (inferred from start/end month), confidence=HIGH

3. **Check for YTD periods:**
   - 181-188 days → **YTD_Q2** (if is_ytd flag), else Q2, confidence=MEDIUM
   - 273-283 days → **YTD_Q3** (if is_ytd flag), else Q3, confidence=MEDIUM

4. **Ambiguous:**
   - Any other duration → **UNKNOWN**, confidence=LOW

#### Fiscal Year Derivation

For non-December-31 year-ends, fiscal year is derived from end_date and fiscal_year_end:

```
fiscal_year_end = "MMDD" format (e.g., "0930" for Sept 30)
end_month_day = end_date.strftime("%m%d")

if end_month_day <= fiscal_year_end:
    # Haven't reached FYE yet in the current calendar year
    fiscal_year = end_date.year
else:
    # We've passed FYE, so we're in the next fiscal year
    fiscal_year = end_date.year + 1
```

**Examples:**
- Sept 30, 2024 with "0930" FYE → FY 2024 (at end of FY)
- Oct 1, 2024 with "0930" FYE → FY 2025 (after end of FY)
- Jan 31, 2024 with "0930" FYE → FY 2024 (before end of FY)

#### Quarter Inference

Quarter is inferred from start/end month using calendar heuristic:

```
Q1: Jan-Mar (month ≤ 3)
Q2: Apr-Jun (month ≤ 6)
Q3: Jul-Sep (month ≤ 9)
Q4: Oct-Dec (month > 9)
```

This is a simplification; advanced calendars (52/53-week retail) require explicit mapping.

### Standalone Quarter Derivation

Quarterly values can be derived from YTD facts:

```python
resolver.derive_standalone_quarter(
    ytd_q2_value=1000.0,   # 6-month YTD
    q1_value=300.0,        # Q1
    # ...
    unit="USD",
    fiscal_year=2024,
)
# Returns: Q2 = 1000 - 300 = 700
```

**Supported derivations:**
- **Q2 = YTD_Q2 - Q1** (6M YTD minus Q1)
- **Q3 = YTD_Q3 - YTD_Q2** (9M YTD minus 6M YTD)
- **Q4 = FY - YTD_Q3** (Full year minus 9M YTD)

## CLI Commands

### Classify a Period

```bash
accountant periods-classify 2024-01-01 2024-03-31 --explain
```

**Output:**
```
Period Classification:
Start Date:     2024-01-01
End Date:       2024-03-31
Duration:       91 days
Period Type:    Q1
Is YTD:         False
Confidence:     HIGH
Fiscal Quarter: Q1

Explanation:
• Q1 (88-95 day quarter)
```

### Show Periods for a Company

```bash
accountant periods-show AAPL --explain
```

*(Database integration pending)*

## Database Schema

### FinancialPeriod Table

```sql
CREATE TABLE financial_periods (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL,
    
    -- Classification
    period_type VARCHAR(32) NOT NULL,  -- INSTANT, Q1-Q4, FY, YTD_Q1-Q3, TTM, UNKNOWN
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,
    
    -- Dates
    start_date DATE,
    end_date DATE,
    instant_date DATE,
    duration_days INTEGER,
    fiscal_year_end VARCHAR(4),  -- MMDD format
    
    -- Indicators
    is_ytd BOOLEAN NOT NULL DEFAULT false,
    is_derived BOOLEAN NOT NULL DEFAULT false,
    
    -- Source tracking
    source_form VARCHAR(32),
    source_accession VARCHAR(24),
    source_fact_ids JSON,
    
    -- Derivation
    derivation_method VARCHAR(64),  -- YTD_MINUS_YTD, FY_MINUS_YTD, DIRECT_REPORT
    derivation_formula TEXT,
    
    -- Resolution
    resolver_version VARCHAR(32) NOT NULL DEFAULT 'FINANCIAL_PERIOD_RESOLVER_V1',
    confidence VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN',
    warnings JSON,
    notes TEXT,
    
    -- Amendment handling
    originally_reported BOOLEAN NOT NULL DEFAULT true,
    restated_by_accession VARCHAR(24),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    
    -- Constraints
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    UNIQUE (company_id, period_type, fiscal_year, fiscal_quarter, instant_date),
    INDEX (company_id, fiscal_year, fiscal_quarter),
    INDEX (company_id, start_date, end_date)
);
```

## Testing

### Test Coverage

Comprehensive test suite in `tests/test_period_resolver.py`:

- **26 tests** covering:
  - Instant fact resolution (HIGH confidence)
  - Quarterly periods (Q1-Q4 with duration validation)
  - YTD detection (6M, 9M)
  - Full-year periods (52-week, 53-week)
  - Fiscal year derivation (calendar vs. non-calendar FYE)
  - Standalone quarter derivation (Q2, Q3, Q4 from YTD)
  - Edge cases (leap years, single-day periods, multi-year spans)
  - Negative values (losses, decreases)

### Running Tests

```bash
uv run pytest tests/test_period_resolver.py -v
```

**Result:** 26/26 passing

## API Examples

### Resolve a Q1 2024 Quarterly Fact

```python
from accountant.financial.period_resolver import FinancialPeriodResolver
from datetime import date

resolver = FinancialPeriodResolver()
result = resolver.resolve_period(
    company_cik="0000789019",
    instant_date=None,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 3, 31),
    fiscal_year=2024,
    fiscal_period="FY1",
    frame=None,
    form="10-Q",
    decimals=-6,
)

print(f"Period Type: {result.period_type}")          # Q1
print(f"Fiscal Quarter: {result.fiscal_quarter}")    # 1
print(f"Duration: {result.duration_days} days")      # 91
print(f"Confidence: {result.confidence}")            # HIGH
```

### Resolve a Balance Sheet (Instant) Fact

```python
result = resolver.resolve_period(
    company_cik="0000789019",
    instant_date=date(2024, 12, 31),
    start_date=None,
    end_date=None,
    fiscal_year=2024,
    fiscal_period=None,
    frame=None,
    form="10-K",
    decimals=-6,
)

print(f"Period Type: {result.period_type}")          # INSTANT
print(f"Instant Date: {result.instant_date}")        # 2024-12-31
print(f"Confidence: {result.confidence}")            # HIGH
```

### Derive Q2 from YTD Facts

```python
q2_result, method = resolver.derive_standalone_quarter(
    ytd_q2_value=1000.0,    # Revenue YTD through Q2
    q1_value=300.0,         # Revenue Q1
    ytd_q3_value=None,
    ytd_q2_for_q3=None,
    fy_value=None,
    ytd_q3_for_q4=None,
    unit="USD",
    fiscal_year=2024,
    decimals=-6,
)

if q2_result:
    print(f"Q2 Value: {q2_result['value']}")          # 700.0
    print(f"Derivation: {method}")                    # YTD_MINUS_Q1
else:
    print(f"Derivation failed: {method}")             # error message
```

## Known Limitations

1. **52/53-week calendars:** Duration tolerance handles most retail calendars, but exact start/end dates require company-specific mapping (not yet implemented).

2. **TTM (Trailing Twelve Months):** Not yet classified (placeholder for future implementation).

3. **Stub periods:** Short periods (< 88 days) between fiscal year changes require special handling (marked UNKNOWN for now).

4. **Dimensional context:** Period resolution does not currently account for segment/dimension overrides (e.g., segment-specific Q1 vs. consolidated Q1).

5. **Amendment/restatement:** Period resolution tracks `originally_reported` and `restated_by_accession` flags but does not yet implement full version control for period changes across amendments.

## Permanent Rules Compliance

- ✅ **Zero LLM:** All logic is deterministic, rule-based, reproducible
- ✅ **SEC/XBRL as fact source:** Authoritative dates used (not SEC metadata)
- ✅ **Raw data immutable:** Periods reference source facts, never modify them
- ✅ **Python calculates:** Duration logic, fiscal year derivation in Python
- ✅ **SQL stores:** Resolved periods persisted to PostgreSQL
- ✅ **Provenance required:** Every period tracks source filings and facts
- ✅ **No silent guesses:** LOW confidence periods flagged with warnings
- ✅ **Versioned formulas:** `resolver_version` field enables reproducibility
- ✅ **Tests required:** 26 comprehensive tests covering all period types

## Future Work (Prompt 6+)

- [ ] Multi-year comparative periods (LY, YoY)
- [ ] Segment period mapping (dimensional context)
- [ ] TTM (trailing twelve months) classification
- [ ] Stub period detection and normalization
- [ ] Amendment/restatement version history
- [ ] 52/53-week calendar customization per company
- [ ] Period conflicts and reconciliation
- [ ] Financial statement reconstruction (GL, IS, CF)
- [ ] Formula validation and consistency checks
