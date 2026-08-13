# Maintenance CAPEX: Four Deterministic Estimation Methods

**Version:** 1.0  
**Date:** 2026-08-12  
**Purpose:** Methodology for estimating maintenance CAPEX from financial statement data.

---

## Executive Summary

**Maintenance CAPEX** is capital expenditure required to sustain existing operations at current levels. This differs from **Growth CAPEX**, which funds expansion.

Problem: Most companies don't separately disclose maintenance vs. growth CAPEX.

Solution: Four deterministic estimation methods with explicit assumptions.

**Formula versions:**
- `MAINTENANCE_CAPEX_DA_ANCHOR_V1` — D&A relationship
- `MAINTENANCE_CAPEX_HISTORICAL_RATIO_V1` — CAPEX/PPE ratio
- `MAINTENANCE_CAPEX_GROWTH_SEPARATION_V1` — Growth component isolation
- `MAINTENANCE_CAPEX_RANGE_V1` — Multi-year normalized range

All methods return `(low, base, high)` estimates with confidence levels.

---

## Why Estimate?

### The Problem

```
Reported CAPEX = Maintenance CAPEX + Growth CAPEX
But companies don't break this down separately!
```

Impact on Owner Earnings:

```
Owner Earnings = NI + DA - CAPEX - ΔWC - Adjustments

If we use total CAPEX:
  Conservative OE = understated (assumes no growth)

If we use wrong maintenance estimate:
  OE model = misleading (understates or overstates available cash)
```

### The Need

For accurate valuation and capital allocation analysis, we need to distinguish:
- **Maintenance CAPEX:** Required to replace worn assets (reinvestment)
- **Growth CAPEX:** Expands productive capacity
- **Efficiency CAPEX:** Reduces cost without expanding (e.g., automation)

---

## Method A: D&A Anchor

**Formula Version:** `MAINTENANCE_CAPEX_DA_ANCHOR_V1`

### Theory

Over long periods, well-managed companies invest in maintenance CAPEX approximately equal to their annual depreciation:

```
Maintenance CAPEX ≈ D&A × multiple
```

Why? Depreciation represents the cost of asset usage. To maintain asset base, reinvest accordingly.

### Formula

```
Maint CAPEX (base) = D&A × 1.0
Maint CAPEX (low)  = D&A × 0.9
Maint CAPEX (high) = D&A × 1.1
```

### Calculation Steps

```python
da = income_stmt.lines["CC_DEPRECIATION_AMORTIZATION"].value_numeric

if da is None or da == 0:
    return INSUFFICIENT_DATA

maint_capex_low = da * 0.90
maint_capex_base = da * 1.00
maint_capex_high = da * 1.10

return {
    "low": maint_capex_low,
    "base": maint_capex_base,
    "high": maint_capex_high,
    "method": "DA_ANCHOR",
}
```

### Inputs

| Input | Source | Required |
|-------|--------|----------|
| D&A | Income Statement | Yes |

### Assumptions & Limitations

| Assumption | Validity | Notes |
|-----------|----------|-------|
| D&A reflects asset replacement need | Medium | Works for mature, stable companies |
| D&A policy consistent across years | Medium | Varies by depreciation method (straight-line vs. accelerated) |
| No major efficiency investments | Medium | Automation or tech investment distorts ratio |
| Asset base stable | Medium | Growing or shrinking companies skew |

### Example: Capital-Light Tech Company

```
Company:           SaaS provider
D&A (FY2024):     $50M
Maintenance CAPEX:
  Low:             $45M (assume D&A overstates need)
  Base:            $50M (D&A anchor)
  High:            $55M (assume D&A understates)
```

### Example: Capital-Heavy Industrials

```
Company:           Industrial manufacturer
D&A (FY2024):     $500M
Maintenance CAPEX:
  Low:             $450M
  Base:            $500M
  High:            $550M
Note: May underestimate if major facility upgrades planned
```

---

## Method B: Historical CAPEX/PPE Ratio

**Formula Version:** `MAINTENANCE_CAPEX_HISTORICAL_RATIO_V1`

### Theory

Maintenance CAPEX as percentage of gross PPE is relatively stable over time (asset intensity):

```
Maintenance CAPEX / PPE ≈ historical ratio
```

Insight: If PPE is $10B and historical ratio is 8%, expect ~$800M annual maintenance.

### Formula

```
Current Year CAPEX / Current Year PPE = historical_ratio
Estimated Maint CAPEX = total_capex × 0.50 to 0.80
```

Why 50-80%? Historical CAPEX includes both maintenance and growth.

```
Maint CAPEX (conservative) = total_capex × 0.50
Maint CAPEX (base)         = total_capex × 0.65
Maint CAPEX (high)         = total_capex × 0.80
```

### Calculation Steps

```python
current_capex = cashflow_stmt.lines["CC_CAPEX"].value_numeric
current_ppe = balance_sheet.lines["CC_PROPERTY_PLANT_EQUIPMENT"].value_numeric

if not current_capex or not current_ppe or current_ppe == 0:
    return INSUFFICIENT_DATA

capex_ppe_ratio = abs(current_capex) / abs(current_ppe)

# Conservative: assume 50% of CAPEX is maintenance
maint_low = abs(current_capex) * 0.50
maint_base = abs(current_capex) * 0.65
maint_high = abs(current_capex) * 0.80

return {
    "low": maint_low,
    "base": maint_base,
    "high": maint_high,
    "capex_ppe_ratio": capex_ppe_ratio,
}
```

### Inputs

| Input | Source | Required |
|-------|--------|----------|
| Total CAPEX (current) | Cash Flow Statement | Yes |
| PPE (current) | Balance Sheet | Yes |

### Assumptions & Limitations

| Assumption | Validity | Notes |
|-----------|----------|-------|
| 50-80% range is typical split | Medium | Varies by cycle (upturns favor growth, downturns favor maintenance) |
| PPE ratio stable | Medium | Changes with acquisition strategy |
| No major one-time capex | Low | Renovation, factory consolidation distorts |

### Example: Mature Industrial

```
Company:           General Motors
Total CAPEX:       $5,000M
PPE:              $60,000M
CAPEX/PPE:         8.3%

Maintenance Estimate:
  Low (50%):       $2,500M
  Base (65%):      $3,250M
  High (80%):      $4,000M
```

---

## Method C: Growth CAPEX Separation

**Formula Version:** `MAINTENANCE_CAPEX_GROWTH_SEPARATION_V1`

### Theory

Separate growth and maintenance by analyzing PPE changes:

```
Δ PPE = Maintenance CAPEX - D&A + Growth CAPEX
```

Rearranged:
```
Growth CAPEX ≈ Δ PPE + D&A - Maintenance CAPEX
```

Estimate growth CAPEX from revenue growth signal:

```
Growth CAPEX ≈ Δ PPE × revenue_growth_rate
```

Then:
```
Maintenance CAPEX = Total CAPEX - Growth CAPEX
```

### Formula

```
PPE_current = current_balance_sheet.ppe
PPE_prior   = prior_balance_sheet.ppe
Δ PPE       = PPE_current - PPE_prior
revenue_growth = (revenue_current - revenue_prior) / revenue_prior

Growth_CAPEX_estimate = Δ PPE × revenue_growth
Maintenance_CAPEX = Total_CAPEX - Growth_CAPEX_estimate
```

### Calculation Steps

```python
current_capex = cashflow_stmt.lines["CC_CAPEX"].value_numeric
delta_ppe = current_ppe - prior_ppe
revenue_growth_rate = (current_revenue - prior_revenue) / prior_revenue

# Estimate growth CAPEX as portion of PPE growth
growth_capex = abs(delta_ppe) * max(0, revenue_growth_rate)

# Maintenance is the remainder
maint_capex = abs(current_capex) - growth_capex
if maint_capex < 0:
    maint_capex = 0  # Cap at zero

# Range: ±20% around estimate
return {
    "low": maint_capex * 0.80,
    "base": maint_capex * 1.00,
    "high": maint_capex * 1.20,
    "estimated_growth_capex": growth_capex,
}
```

### Inputs

| Input | Source | Required |
|-------|--------|----------|
| Total CAPEX | Cash Flow Statement | Yes |
| PPE (current) | Balance Sheet | Yes |
| PPE (prior) | Balance Sheet | Yes |
| Revenue Growth Rate | Income Statement | Yes |

### Assumptions & Limitations

| Assumption | Validity | Notes |
|-----------|----------|-------|
| Growth CAPEX ∝ revenue growth | Medium | Works for organic growth; poor for M&A |
| PPE change captures growth needs | Medium | Doesn't account for efficiency improvements |
| No asset disposals | Low | Asset sales distort Δ PPE |

### Example: High-Growth Tech Company

```
Company:           Cloud infrastructure provider
Total CAPEX:       $8,000M
PPE (current):    $15,000M
PPE (prior):      $12,000M
Δ PPE:            $3,000M
Revenue Growth:   30%

Growth CAPEX Estimate = $3,000M × 0.30 = $900M
Maintenance CAPEX = $8,000M - $900M = $7,100M

Range:
  Low (×0.80):    $5,680M
  Base:           $7,100M
  High (×1.20):   $8,520M
```

---

## Method D: Historical Range

**Formula Version:** `MAINTENANCE_CAPEX_RANGE_V1`

### Theory

Use normalized multi-year CAPEX/Revenue ratio:

```
Maint CAPEX ≈ Current Revenue × historical_capex_revenue_ratio
```

By averaging ratios over multiple years, we smooth cycles.

### Formula

```
For each year in history:
  ratio_i = CAPEX_i / Revenue_i
  
Filter ratios for outliers (drop if ratio > 10x or < 0.1% of revenue)

Maint CAPEX (low)  = current_revenue × min(ratio)
Maint CAPEX (base) = current_revenue × avg(ratio)
Maint CAPEX (high) = current_revenue × max(ratio)
```

### Calculation Steps

```python
capex_history = [500, 600, 650, 700, 750]  # 5 years
revenue_history = [10000, 11000, 12000, 13000, 14000]

# Calculate ratios
ratios = []
for capex, revenue in zip(capex_history, revenue_history):
    if revenue == 0:
        continue
    ratio = capex / revenue
    if ratio > 0.10:  # Sanity check
        continue
    ratios.append(ratio)

if not ratios:
    return INSUFFICIENT_DATA

ratios.sort()
low_ratio = ratios[0]
base_ratio = sum(ratios) / len(ratios)
high_ratio = ratios[-1]

current_revenue = revenue_history[-1]

return {
    "low": current_revenue * low_ratio,
    "base": current_revenue * base_ratio,
    "high": current_revenue * high_ratio,
    "method": "HISTORICAL_RANGE",
}
```

### Inputs

| Input | Source | Required |
|-------|--------|----------|
| CAPEX History (3-10 years) | Cash Flow Statements | Yes |
| Revenue History (same years) | Income Statements | Yes |
| Current Revenue | Income Statement | Yes |

### Assumptions & Limitations

| Assumption | Validity | Notes |
|-----------|----------|-------|
| Historical pattern continues | Medium | Breaks during major restructuring |
| No major one-time capex | Low | Divestitures or factories skew range |
| Sufficient historical data | Medium | Requires 3+ years minimum |

### Example: Stable Mature Company

```
Company:           Coca-Cola
Historical CAPEX/Revenue:
  Year 1:  4.2%
  Year 2:  4.1%
  Year 3:  4.3%
  Year 4:  4.0%
  Year 5:  4.4%

Average:  4.2%
Min:      4.0%
Max:      4.4%

Current Revenue: $50,000M

Maintenance CAPEX:
  Low (4.0%):     $2,000M
  Base (4.2%):    $2,100M
  High (4.4%):    $2,200M
```

---

## Choosing a Method

### Recommendation Matrix

| Company Type | Best Method | Why |
|--------------|---|---|
| Capital-light SaaS | DA_Anchor | Low asset intensity, D&A predictable |
| Mature industrial | Historical_Range | Stable capital needs, long history |
| High-growth tech | Growth_Separation | Rapid expansion, separate growth signal |
| Post-acquisition | Historical_Ratio | Adjust for new asset base |
| Turnaround/restructure | Avoid estimates | Unusual patterns, use with caution |

### Combining Methods

**Best Practice:** Calculate all four methods, compare outputs.

- If all four converge → Confidence **HIGH**
- If 3 of 4 converge → Confidence **MEDIUM**
- If methods diverge widely → Confidence **LOW**, flag for review

### Configuration

```python
context.configuration = {
    "maintenance_capex_method": "maintenance_capex_growth_separation",
    # or: "da_anchor", "historical_ratio", "historical_range"
    "fallback_method": "historical_range",
    "require_confidence_high": False,
}
```

---

## Output Structure

All four methods return:

```json
{
  "calculation_id": "MAINTENANCE_CAPEX_DA_ANCHOR",
  "formula_version": "MAINTENANCE_CAPEX_DA_ANCHOR_V1",
  "value": 6500000000,
  "unit": "USD",
  "calculation_status": "VALID",
  "metadata": {
    "method": "DA_ANCHOR",
    "low": 5850000000,
    "base": 6500000000,
    "high": 7150000000,
    "da_value": 6500000000,
    "da_multiple_base": 1.0
  },
  "inputs": {
    "depreciation_amortization": 6500000000,
    "da_multiple_low": 0.9,
    "da_multiple_base": 1.0,
    "da_multiple_high": 1.1
  },
  "warnings": []
}
```

### Interpretation

- **value:** Base estimate (most likely)
- **metadata.low:** Conservative scenario
- **metadata.high:** Optimistic scenario
- **metadata.method:** Which method was used
- **warnings:** Data quality flags

---

## Status Codes

### VALID
- Sufficient data
- Calculation succeeded
- Result is usable

### INSUFFICIENT_DATA
- Missing required inputs
- Cannot proceed
- Example: D&A is zero or missing

### Example

```python
result = MaintenanceCapexEstimator.estimate_da_anchor(stmt, context)

if result.calculation_status == "VALID":
    use_capex = result.value  # Proceed with model
else:
    use_capex = None  # Fall back or flag
    print(result.warnings)  # See why estimation failed
```

---

## Validation & Sanity Checks

### CAPEX/Revenue should be in range

```
Capital-light (software, services):    0.5% - 3.0%
Mixed (consumer, healthcare):          2.0% - 5.0%
Capital-heavy (industrials):           5.0% - 15.0%
Utilities:                            10.0% - 20.0%
```

If outside range, flag warning.

### D&A / CAPEX ratio

```
Mature company:   D&A ≈ 0.6x to 1.2x CAPEX (some growth)
Stable company:   D&A ≈ 0.8x to 1.0x CAPEX (mostly maintenance)
Growing company:  D&A << CAPEX (heavy growth investment)
```

---

## Database Persistence

Maintenance CAPEX estimates are persisted as `CalculationResult` rows:

```sql
SELECT
    calculation_id,
    formula_version,
    fiscal_year,
    value,
    metadata,
    inputs
FROM calculation_results
WHERE company_id = :company_id
  AND calculation_id = 'MAINTENANCE_CAPEX_*'
ORDER BY fiscal_year DESC, formula_version;
```

Each method version is stored separately, allowing comparison.

---

## CLI Usage

### Estimate Maintenance CAPEX

```bash
uv run accountant maintenance-capex AAPL --fiscal-year 2024
```

### Specific Method

```bash
uv run accountant maintenance-capex AAPL --fiscal-year 2024 --method da_anchor
```

### With Explanation

```bash
uv run accountant maintenance-capex AAPL --fiscal-year 2024 --explain
```

---

## Python API

### D&A Anchor

```python
from accountant.calculations import MaintenanceCapexEstimator, CalculationContext

context = CalculationContext(company_id="AAPL", fiscal_year=2024)
result = MaintenanceCapexEstimator.estimate_da_anchor(
    income_stmt,
    context,
    da_multiple_low=0.9,
    da_multiple_base=1.0,
    da_multiple_high=1.1,
)
print(f"Maintenance CAPEX: ${result.value / 1e9:.1f}B")
print(f"Range: ${result.metadata['low']/1e9:.1f}B - ${result.metadata['high']/1e9:.1f}B")
```

### Growth Separation

```python
result = MaintenanceCapexEstimator.estimate_growth_separation(
    current_year_capex=10500.0,
    prior_year_ppe=180000.0,
    current_year_ppe=200000.0,
    revenue_growth_rate=10.0,
    context=context,
)
print(f"Maintenance CAPEX (growth separated): ${result.value / 1e9:.1f}B")
print(f"Estimated growth CAPEX: ${result.metadata['estimated_growth_capex']/1e9:.1f}B")
```

### Historical Range

```python
result = MaintenanceCapexEstimator.estimate_range(
    historical_capex_list=[500, 600, 650, 700, 750],
    historical_revenue_list=[10000, 11000, 12000, 13000, 14000],
    context=context,
)
print(f"Maintenance CAPEX: ${result.value / 1e9:.1f}B")
print(f"Historical range: {result.metadata['low_ratio']:.1%} to {result.metadata['high_ratio']:.1%} of revenue")
```

---

## Version History

- **MAINTENANCE_CAPEX_DA_ANCHOR_V1 (2026-08-12):** Initial D&A anchor version
- **MAINTENANCE_CAPEX_HISTORICAL_RATIO_V1 (2026-08-12):** CAPEX/PPE ratio version
- **MAINTENANCE_CAPEX_GROWTH_SEPARATION_V1 (2026-08-12):** Growth separation version
- **MAINTENANCE_CAPEX_RANGE_V1 (2026-08-12):** Multi-year range version

---

*See also: [owner_earnings.md](owner_earnings.md) for how maintenance CAPEX is used in Owner Earnings models.*
