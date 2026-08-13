# Economic Debt Estimation

**Purpose:** Calculate total economic obligations—not just reported debt, but all claims on enterprise value including leases, pension underfunding, and contingent liabilities.

**Why:** Balance sheet debt alone understates financial leverage. ASC 842 (lease capitalization), underfunded pensions, and contingent liabilities are real economic obligations that reduce equity value and constrain cash flow. Three explicit models capture different use cases.

---

## The Three Economic Debt Models

### Model 1: Reported Economic Debt
**Best for:** GAAP-aligned analysis, benchmark against financial statements

```
Economic Debt = Total Debt + Operating Leases (ASC 842) + Finance Leases
                + Pension Underfunding + Other Long-Term Obligations
```

**What's Included:**
- **Total Debt** — Short-term + long-term debt from balance sheet
- **Operating Leases** — ROU asset liability under ASC 842
- **Finance Leases** — Capitalized lease obligations (already on BS in many cases)
- **Pension Underfunding** — Projected benefit obligation minus plan assets
- **Other Obligations** — Deferred revenue, contingent liabilities, unwound discounts

**When to Use:**
- Calculating leverage ratios (debt/EBITDA) for covenant compliance
- Comparing to peer debt metrics
- Year-over-year debt trending
- When leases and pensions are the primary economic adjustments

**Example:**
```
Total Debt:              $50,000M
Operating Leases (ASC 842): $5,000M
Finance Leases:         $2,000M
Pension Underfunding:   $1,000M
Other Obligations:      $500M
─────────────────────────────
Economic Debt (Reported): $58,500M
```

---

### Model 2: Adjusted Economic Debt
**Best for:** Stress testing, comprehensive financial analysis, conservative valuations

```
Economic Debt (Adjusted) = Reported + Capitalized Intangibles 
                          + Environmental Liabilities + Contingencies
```

**Additional Items Beyond Reported:**
- **Capitalized Intangibles** — Write-ups from M&A that don't create cash obligations but reduce tangible equity
- **Environmental Liabilities** — Remediation, decommissioning, cleanup accruals
- **Contingent Liabilities** — Disclosed lawsuits, warranties, regulatory fines (if material)

**Confidence Levels:**
- **HIGH** — Debt, ASC 842 leases (standard-settable)
- **MEDIUM** — Pensions (actuarial estimation), capitalized intangibles (purchase price allocation)
- **LOW** — Environmental, contingent (subject to materiality, disclosure practices)

**When to Use:**
- Comprehensive balance sheet analysis
- Stress-testing leverage under worst-case scenarios
- Comparing companies with different M&A and environmental exposures
- When environmental remediation or legal risk is material

**Example:**
```
Economic Debt (Reported):    $58,500M
Capitalized Intangibles:     $2,000M
Environmental Liabilities:   $1,500M
─────────────────────────────────
Economic Debt (Adjusted):    $62,000M
```

---

### Model 3: Implied Economic Debt
**Best for:** Valuation, leverage target assessment, capital structure normalization

```
Implied Economic Debt = (Market Cap × Target Leverage) - Net Cash
```

**Logic:**
- What debt *should* the company have given its size and typical capital structure?
- Compares current debt to "normalized" or "optimal" debt level
- Useful for assessing whether company is overleveraged or underleveraged

**Parameters:**
- **Market Cap** — Current equity value from stock price × shares outstanding
- **Target Leverage** — Industry/company-specific ratio (e.g., 2.0–2.5x for mature industrials)
- **Net Cash** — Cash & equivalents minus total debt (sometimes just cash)

**When to Use:**
- Assessing current leverage vs. industry peer norms
- Projection scenarios (what debt load supports growth?)
- Capital structure optimization (optimal debt = more efficient WACC)
- When reported/adjusted debt appears abnormal

**Example:**
```
Market Cap:           $3,000,000M
Target Leverage:      2.5x
Implied Debt:         $3,000,000 × 2.5 = $7,500,000M
Less: Net Cash:       $5,000M
─────────────────────────────────
Implied Economic Debt: $7,495,000M

Current Debt:         $50,000M
Assessment:           Significantly underleveraged; could take more debt
```

---

## Output Structure

### CalculationResult Fields

All three models return immutable `CalculationResult` objects:

```python
{
    "calculation_id": "ECONOMIC_DEBT",
    "formula_version": "ECONOMIC_DEBT_REPORTED_V1 | ADJUSTED_V1 | IMPLIED_V1",
    "company_id": "AAPL",
    "fiscal_year": 2024,
    "fiscal_quarter": None,
    "value": 58500.0,  # USD millions
    "unit": "USD",
    "calculation_status": "VALID",  # or INSUFFICIENT_DATA
    "formula": "Economic Debt (Reported) = ...",
    "inputs": {
        "total_debt": 50000.0,
        "operating_lease_liability": 5000.0,
        ...
    },
    "metadata": {
        "model": "REPORTED",
        "total_debt": 50000.0,
        "operating_lease_liability": 5000.0,
        ...
    },
    "warnings": [],
    "calculated_at": "2024-08-12T14:30:00Z"
}
```

---

## Model Comparison

| Dimension | Reported | Adjusted | Implied |
|-----------|----------|----------|---------|
| **Complexity** | Low | Medium | Simple |
| **Data Required** | ~5 BS items | ~7 items | Market cap + leverage target |
| **Confidence** | High | Medium | Medium-High |
| **Use Case** | Benchmark, trends | Stress test, comprehensive | Valuation, capital structure |
| **Best for Leverage Ratios** | ✓ Primary | ✓ Conservative stress | ✗ Not for ratios |
| **Auditable** | ✓ All on/near BS | ✓ Disclosed items | ✓ Market observable |
| **Time to Calculate** | Seconds | Seconds | Seconds |

---

## Implementation Details

### Reported Model

**Query Structure (SQL):**
```sql
SELECT
    total_debt,
    operating_lease_liability,  -- ASC 842 ROU liability
    finance_lease_liability,
    pension_underfunding,       -- PBO - Plan Assets
    other_obligations
FROM financial_statement
WHERE company_id = 'AAPL'
  AND fiscal_year = 2024
```

**Calculation (Python):**
```python
result = EconomicDebtCalculator.calculate_reported(
    total_debt=50000.0,
    operating_lease_liability=5000.0,
    finance_lease_liability=2000.0,
    pension_underfunding=1000.0,
    other_obligations=500.0,
    context=context
)
# result.value = 58500.0
```

**Validation:**
- `total_debt` is required (raises INSUFFICIENT_DATA if missing)
- Other fields default to 0.0 if missing (are they material?)
- No negative values or extreme outliers

---

### Adjusted Model

**Additional Data:**
```sql
SELECT
    capitalized_intangibles,     -- Goodwill + acquisition adjustments
    environment_liabilities      -- Remediation accruals
FROM financial_statement
WHERE company_id = 'AAPL'
  AND fiscal_year = 2024
```

**Python:**
```python
result = EconomicDebtCalculator.calculate_adjusted(
    total_debt=50000.0,
    operating_lease_liability=5000.0,
    finance_lease_liability=2000.0,
    pension_underfunding=1000.0,
    other_obligations=500.0,
    capitalized_intangibles=2000.0,
    environment_liabilities=1500.0,
    context=context
)
# result.value = 62000.0
```

**Note:** Adjusted > Reported always. If adjusted < reported, check for data errors.

---

### Implied Model

**Market Data:**
```python
market_cap = stock_price * shares_outstanding  # From Yahoo Finance
net_cash = cash - total_debt

# Or use from database if persisted
```

**Calculation (Python):**
```python
result = EconomicDebtCalculator.calculate_implied(
    total_debt=50000.0,
    market_cap=3000000.0,
    net_cash=5000.0,
    context=context,
    leverage_target=2.5  # Industry typical
)
# Implied = (3,000,000 × 2.5) - 5,000 = 7,495,000
```

**Interpretation:**
- If current debt < implied, company could support more leverage
- If current debt > implied, company is overleveraged relative to peer norms
- Useful for capital structure optimization (reduce implied → reduce WACC)

---

## Industry Benchmarks (Typical Leverage Targets)

| Sector | Typical Leverage (Debt/EBITDA) | Range |
|--------|--------------------------------|-------|
| **Mature Industrials** | 2.0–2.5x | 1.5–3.0x |
| **Utilities** | 3.0–4.0x | 2.5–4.5x (regulated) |
| **REITs** | 4.0–6.0x | 3.0–7.0x |
| **Financial Institutions** | Varies (use equity ratio) | 8–12x |
| **Software/Tech** | <1.5x | 0.0–2.0x (high growth) |
| **Consumer Staples** | 2.0–3.0x | 1.5–3.5x |
| **Telecom** | 2.5–3.5x | 2.0–4.0x |

**Use these for "typical" leverage_target parameter in implied model.**

---

## Known Issues & Limitations

### Data Quality
1. **Pension Underfunding** — Estimate may differ from actuarial valuation; use latest 10-K disclosures
2. **ASC 842 Leases** — Adoption incomplete for some private companies; check footnotes
3. **Contingent Liabilities** — Often understated unless material; review legal disclosures
4. **Capitalized Intangibles** — Highly specific to M&A activity; varies by accounting policy

### Model Limitations
1. **Reported** — Ignores off-balance-sheet items (SPVs, joint ventures)
2. **Adjusted** — Requires subjective judgment on materiality of contingencies
3. **Implied** — Assumes market cap is "correct" (may be overvalued/undervalued); sensitive to leverage_target

### Timing
- All models use point-in-time data (fiscal year-end). Mid-year calculations use YTD estimates.
- Market-based implied debt updates daily (if using live stock prices).

---

## CLI Usage

### List All Concepts
```bash
uv run accountant economic-debt AAPL --fiscal-year 2024
```

**Output:**
```
Company: AAPL (2024 FY)
─────────────────────────────────────────
Model: REPORTED
  Total Debt:            $50,000M
  Operating Leases:      $5,000M
  Finance Leases:        $2,000M
  Pension Underfunding:  $1,000M
  Other Obligations:     $500M
  ─────────────────────
  Economic Debt:         $58,500M

Model: ADJUSTED
  Economic Debt (Reported): $58,500M
  Capitalized Intangibles:  $2,000M
  Environment Liabilities:  $1,500M
  ─────────────────────
  Economic Debt:         $62,000M

Model: IMPLIED (Target Leverage: 2.5x)
  Market Cap:            $3,000,000M
  Net Cash:              $5,000M
  Implied Debt:          $7,495,000M
  Current Debt:          $50,000M
  Assessment:            Underleveraged
```

### Single Model
```bash
uv run accountant economic-debt AAPL --fiscal-year 2024 --model reported
```

### With Explanation
```bash
uv run accountant economic-debt AAPL --fiscal-year 2024 --explain
```

---

## Python API

### Basic Usage
```python
from accountant.calculations import EconomicDebtCalculator, CalculationContext

context = CalculationContext(
    company_id="AAPL",
    fiscal_year=2024,
    fiscal_quarter=None
)

# Reported Model
reported = EconomicDebtCalculator.calculate_reported(
    total_debt=50000.0,
    operating_lease_liability=5000.0,
    finance_lease_liability=2000.0,
    pension_underfunding=1000.0,
    other_obligations=500.0,
    context=context
)
print(f"Reported Economic Debt: ${reported.value}M")

# Adjusted Model
adjusted = EconomicDebtCalculator.calculate_adjusted(
    total_debt=50000.0,
    operating_lease_liability=5000.0,
    finance_lease_liability=2000.0,
    pension_underfunding=1000.0,
    other_obligations=500.0,
    capitalized_intangibles=2000.0,
    environment_liabilities=1500.0,
    context=context
)
print(f"Adjusted Economic Debt: ${adjusted.value}M")

# Implied Model
implied = EconomicDebtCalculator.calculate_implied(
    total_debt=50000.0,
    market_cap=3000000.0,
    net_cash=5000.0,
    context=context,
    leverage_target=2.5
)
print(f"Implied Economic Debt: ${implied.value}M")
```

### Accessing Results
```python
# Check status
if reported.calculation_status == "VALID":
    debt_value = reported.value
else:
    # Handle missing data
    print(reported.warnings)

# Access metadata
model_used = reported.metadata["model"]
components = {
    k: v for k, v in reported.metadata.items()
    if k != "model"
}

# Audit trail
inputs = reported.inputs
formula = reported.formula
version = reported.formula_version
```

---

## Three-Model Workflow

**Recommended approach for comprehensive analysis:**

```python
# 1. Run all three models
reported = EconomicDebtCalculator.calculate_reported(...)
adjusted = EconomicDebtCalculator.calculate_adjusted(...)
implied = EconomicDebtCalculator.calculate_implied(...)

# 2. Compare results
print(f"Reported:  ${reported.value}M")
print(f"Adjusted:  ${adjusted.value}M")
print(f"Implied:   ${implied.value}M")

# 3. Assess leverage
if implied.value > reported.value:
    headroom = (implied.value - reported.value) / implied.value * 100
    print(f"Debt capacity headroom: {headroom:.1f}%")

# 4. Scenario analysis
if adjusted.value / ebitda > 3.5:
    print("WARNING: Adjusted leverage exceeds 3.5x threshold")
```

---

## Database Persistence

**Storage (SQL):**
```sql
INSERT INTO calculation_results (
    calculation_id,
    formula_version,
    company_id,
    fiscal_year,
    fiscal_quarter,
    value,
    unit,
    calculation_status,
    formula,
    inputs,
    metadata,
    warnings,
    calculated_at
) VALUES (
    'ECONOMIC_DEBT',
    'ECONOMIC_DEBT_REPORTED_V1',
    'AAPL',
    2024,
    NULL,
    58500.0,
    'USD',
    'VALID',
    'Economic Debt (Reported) = Total Debt + Operating Leases + ...',
    '{"total_debt": 50000.0, ...}',
    '{"model": "REPORTED", ...}',
    '[]',
    '2024-08-12 14:30:00'
);
```

**Query (retrieve historical):**
```sql
SELECT value, calculated_at
FROM calculation_results
WHERE calculation_id = 'ECONOMIC_DEBT'
  AND formula_version = 'ECONOMIC_DEBT_REPORTED_V1'
  AND company_id = 'AAPL'
ORDER BY calculated_at DESC
LIMIT 10;
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| **V1** | 2026-08-12 | Initial release: three models (reported, adjusted, implied) |

---

## Related Documents

- [[dilution.md]] — Equity dilution from stock-based compensation and warrants
- [[capital_allocation.md]] — ROIC-based capital allocation efficiency
- [[owner_earnings.md]] — Owner earnings as starting point for enterprise cash flow
- docs/maintenance_capex.md — Maintenance CAPEX estimation (feeds free cash flow analysis)

---

**For questions:** Contact the financial analysis team or file an issue on GitHub.
