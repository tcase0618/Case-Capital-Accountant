# Owner Earnings: Three Explicit Models

**Version:** 1.0  
**Date:** 2026-08-12  
**Purpose:** Methodology for calculating Owner Earnings using three explicit, versioned approaches.

---

## Executive Summary

**Owner Earnings** represents the cash earnings available to shareholders after maintaining and growing the business. Unlike Net Income, Owner Earnings accounts for:
- Required capital expenditures (maintenance)
- Working capital investment
- Non-cash adjustments
- Economic adjustments (SBC, etc.)

Three models are provided:
1. **Conservative** — Uses total CAPEX (most conservative for safety)
2. **Maintenance CAPEX** — Uses estimated maintenance CAPEX (realistic for mature companies)
3. **CFO** — Uses operating cash flow directly (most direct)

---

## Why Owner Earnings?

**Net Income ≠ Shareholder Cash Available**

Net Income includes accrual items that don't represent cash available to owners:
- It ignores required capital investments
- It ignores changes in working capital needs
- It doesn't distinguish growth CAPEX from maintenance CAPEX

**Owner Earnings bridges that gap:**

```
Owner Earnings = Core Profit 
                - Maintenance Capital Investment 
                - Required Working Capital Investment
                + Adjustments for non-recurring items
```

---

## Model 1: Conservative Owner Earnings

**Formula Version:** `OWNER_EARNINGS_CONSERVATIVE_V1`

### Formula

```
Conservative OE = Net Income 
                + Noncash Charges (D&A, stock-based comp)
                - Total Capital Expenditures
                - Required Working Capital Investment
                - Recurring Economic Adjustments
```

### Characteristics

- **Most conservative:** Assumes ALL CAPEX is growth (worst case)
- **Worst-case estimate:** Undercounts cash available by treating growth CAPEX as maintenance
- **Useful for:** Safety margin, stress testing, valuation conservatism
- **Sector:** Works best for capital-light businesses (tech, software, services)

### Calculation Steps

```python
ni = income_stmt.lines["CC_NET_INCOME"].value_numeric
da = income_stmt.lines["CC_DEPRECIATION_AMORTIZATION"].value_numeric or 0
total_capex = cashflow_stmt.lines["CC_CAPEX"].value_numeric or 0
required_wc = calculate_required_wc_investment(current_bs, prior_bs)
sbc_adjustment = estimate_sbc_economic_cost(income_stmt)

conservative_oe = ni + da - total_capex - required_wc - sbc_adjustment
```

### Inputs

| Input | Source | Required |
|-------|--------|----------|
| Net Income | Income Statement | Yes |
| D&A | Income Statement | No (default 0) |
| Total CAPEX | Cash Flow Statement | No (default 0) |
| Required WC Investment | Balance Sheet change | No (default 0) |
| Economic Adjustments | Config/adjustment rule | No (default 0) |

### Example: AAPL FY2024 (Illustrative)

```
Net Income:                    $36,000M
+ D&A:                         +$1,500M
- Total CAPEX:                -$10,500M
- Required WC Investment:     -$  500M
- SBC Economic Adjustment:    -$  200M
────────────────────────────────────
Conservative OE:              $26,300M
```

---

## Model 2: Maintenance CAPEX Owner Earnings

**Formula Version:** `OWNER_EARNINGS_MAINT_CAPEX_V1`

### Formula

```
Maintenance CAPEX OE = Net Income 
                     + Noncash Charges
                     - Maintenance CAPEX (estimated)
                     - Required Working Capital Investment
                     - Recurring Economic Adjustments
```

### Characteristics

- **Most realistic:** Separates maintenance from growth CAPEX
- **Distinguishes:** Capital needed to maintain current operations vs. capital for growth
- **Useful for:** Valuation, capital allocation analysis, comparing across cycles
- **Sector:** Works best when maintenance/growth CAPEX split is clear

### How to Estimate Maintenance CAPEX

See `maintenance_capex.md` for detailed methodology. Four methods available:

1. **D&A Anchor:** Maintenance CAPEX ≈ D&A (historical relationship)
2. **Historical CAPEX/PPE Ratio:** Use past capital intensity
3. **Growth CAPEX Separation:** Subtract growth component from total
4. **Historical Range:** Normalize multi-year CAPEX/Revenue ratio

### Calculation Steps

```python
ni = income_stmt.lines["CC_NET_INCOME"].value_numeric
da = income_stmt.lines["CC_DEPRECIATION_AMORTIZATION"].value_numeric or 0
maint_capex = estimate_maintenance_capex(income_stmt, bs_current, bs_prior)
required_wc = calculate_required_wc_investment(current_bs, prior_bs)
sbc_adjustment = estimate_sbc_economic_cost(income_stmt)

maintenance_oe = ni + da - maint_capex - required_wc - sbc_adjustment
```

### Example: AAPL FY2024 (Illustrative)

Using estimated maintenance CAPEX of $6,500M:

```
Net Income:                    $36,000M
+ D&A:                         +$1,500M
- Maintenance CAPEX:           -$6,500M
- Required WC Investment:     -$  500M
- SBC Economic Adjustment:    -$  200M
────────────────────────────────────
Maintenance CAPEX OE:          $24,300M
```

**Note:** This is higher than Conservative OE because growth CAPEX ($4,000M) is excluded.

---

## Model 3: CFO Owner Earnings

**Formula Version:** `OWNER_EARNINGS_CFO_V1`

### Formula

```
CFO OE = Operating Cash Flow 
       - Maintenance CAPEX (estimated)
       - Recurring Economic Adjustments
```

### Characteristics

- **Most direct:** Starts from actual cash generation
- **No accruals:** Already reflects changes in working capital, receivables, payables
- **Useful for:** Cash quality checks, comparing to accrual-based earnings
- **Limitation:** Dependent on maintenance CAPEX estimate (like Model 2)

### Calculation Steps

```python
cfo = cashflow_stmt.lines["CC_OPERATING_CASH_FLOW"].value_numeric
maint_capex = estimate_maintenance_capex(income_stmt, bs_current, bs_prior)
economic_adj = estimate_recurring_economic_adjustments(income_stmt)

cfo_oe = cfo - maint_capex - economic_adj
```

### Example: AAPL FY2024 (Illustrative)

Using estimated maintenance CAPEX of $6,500M and CFO of $32,300M:

```
Operating Cash Flow:           $32,300M
- Maintenance CAPEX:           -$6,500M
- Economic Adjustments:        -$  200M
────────────────────────────────────
CFO OE:                         $25,600M
```

---

## Working Capital Investment

**Required Working Capital** is the structural, non-temporary change in NWC.

### Definition

```
Required WC Investment = Δ NWC from operations
                       (excluding financing activities)
```

### Calculation

```
Current NWC = (Current Assets - Cash) - (Current Liabilities - Short-Term Debt)
Prior NWC   = (Prior Assets - Cash) - (Prior Liabilities - Short-Term Debt)
Required WC = Current NWC - Prior NWC
```

### Examples

| Scenario | Δ NWC | Interpretation |
|----------|-------|---|
| +$100M | Business growing, needs more cash tied up in AR/inventory | Capital use |
| -$50M | Better collections or payables stretched | Capital source |
| $0 | Stable working capital needs | No capital use |

**Note:** Only include structural changes. Exclude temporary fluctuations or seasonal patterns.

---

## Recurring Economic Adjustments

### What to Include

| Item | Treatment | Example |
|------|-----------|---------|
| Stock-Based Compensation | Economic cost (dilution) | $200M annual SBC |
| Restructuring charges | If recurring/expected | $50M annual charges |
| Legal settlements | If recurring/expected | $25M annual |
| Discontinued operations | Exclude (one-time) | Skip |

### SBC Treatment Options

**Default (Economic View):** Recognize full economic cost of SBC dilution

```python
sbc_economic_cost = 0.8 * sbc_expense  # Conservative: 80% of reported SBC
```

**Alternative (Cash Flow View):** Subtract only the cash SBC component

```python
sbc_cash_cost = actual_shares_repurchased * stock_price
```

### Configuration

Set via calculation context:

```python
context.configuration = {
    "sbc_treatment": "economic",  # or "cash_flow"
    "recurring_cost_rules": {
        "restructuring": True,
        "legal_settlements": False,
    }
}
```

---

## Non-Cash Charges

### Include

- Depreciation & Amortization
- Amortization of intangible assets
- Deferred taxes (if negative)
- Stock-based compensation (if excluded from net income)

### Exclude

- Goodwill impairment (one-time)
- Write-downs on specific assets
- Gain/loss on asset sales

---

## Comparison: Three Models

| Aspect | Conservative | Maintenance CAPEX | CFO |
|--------|---|---|---|
| **Starting Point** | Net Income | Net Income | Operating Cash Flow |
| **CAPEX Treatment** | All CAPEX is "growth" | Separates maintenance | Embedded in CFO |
| **WC Investment** | Explicit adjustment | Explicit adjustment | Already in CFO |
| **Conservatism** | Highest | Medium | Medium |
| **Data Requirement** | Income + Cash flow | Income + BS + Cash | Cash flow + BS |
| **Best For** | Safety margin | Valuation | Sanity check |

### When to Use Which

**Conservative:**
- Valuing turnaround situations
- Stress testing
- High uncertainty scenarios

**Maintenance CAPEX:**
- Standard valuation
- Free cash flow models
- Capital allocation analysis
- Most common choice

**CFO:**
- Sanity check vs. Net Income
- Detecting earnings quality issues
- Validating maintenance CAPEX estimates

---

## Calculation Status Codes

### VALID
- All inputs available
- Calculation successful
- Assumptions applied and documented

### INSUFFICIENT_DATA
- Missing net income or CFO
- Cannot proceed without core starting point

### Example

```json
{
  "calculation_id": "OWNER_EARNINGS",
  "formula_version": "OWNER_EARNINGS_MAINT_CAPEX_V1",
  "value": 24300000000,
  "unit": "USD",
  "calculation_status": "VALID",
  "inputs": {
    "net_income": 36000000000,
    "depreciation_amortization": 1500000000,
    "maintenance_capex": 6500000000,
    "required_wc_investment": 500000000,
    "recurring_economic_adjustments": 200000000
  },
  "metadata": {
    "model": "MAINTENANCE_CAPEX",
    "maintenance_capex_method": "DA_ANCHOR",
    "maintenance_capex_estimate_confidence": "MEDIUM"
  },
  "warnings": [
    "Maintenance CAPEX is estimated; see maintenance_capex.md for detail"
  ]
}
```

---

## Database Persistence

Owner Earnings results are stored using the existing `calculation_results` table:

```sql
SELECT
    calculation_id,
    fiscal_year,
    value,
    formula_version,
    inputs,
    metadata,
    warnings
FROM calculation_results
WHERE company_id = :company_id
  AND calculation_id = 'OWNER_EARNINGS'
  AND formula_version IN (
    'OWNER_EARNINGS_CONSERVATIVE_V1',
    'OWNER_EARNINGS_MAINT_CAPEX_V1',
    'OWNER_EARNINGS_CFO_V1'
  )
ORDER BY fiscal_year DESC;
```

---

## Version History

- **OWNER_EARNINGS_CONSERVATIVE_V1 (2026-08-12):** Initial production version
- **OWNER_EARNINGS_MAINT_CAPEX_V1 (2026-08-12):** Maintenance CAPEX variant
- **OWNER_EARNINGS_CFO_V1 (2026-08-12):** CFO-based variant

All three versions are available in the same calculation run.

---

## Limitations and Known Issues

1. **Maintenance CAPEX Estimation:** Not all companies report detail. Estimates vary ±20-30%.
2. **Working Capital Volatility:** One-time swings can distort OE (e.g., post-acquisition integration).
3. **Accounting Method Changes:** Lease capitalization (ASC 842) affects CAPEX comparisons.
4. **Cyclical Industries:** Maintenance CAPEX varies with cycle (e.g., airlines, restaurants).

---

## CLI Usage

### Calculate Owner Earnings (All Models)

```bash
uv run accountant owner-earnings AAPL --fiscal-year 2024
```

### Specific Model

```bash
uv run accountant owner-earnings AAPL --fiscal-year 2024 --method maintenance
```

### With Explanation

```bash
uv run accountant owner-earnings AAPL --fiscal-year 2024 --explain
```

### Historical (10-year)

```bash
uv run accountant owner-earnings AAPL --fiscal-year 2024 --years 10
```

---

## Python API

### Conservative Model

```python
from accountant.calculations import OwnerEarningsCalculator, CalculationContext

context = CalculationContext(
    company_id="AAPL",
    fiscal_year=2024,
    fiscal_quarter=None,
)

result = OwnerEarningsCalculator.calculate_conservative(
    net_income=36000.0,  # $36B
    noncash_charges=1500.0,  # D&A
    total_capex=10500.0,  # $10.5B total
    required_working_capital_investment=500.0,
    context=context,
    recurring_economic_adjustments=200.0,
)

print(f"Conservative OE: ${result.value / 1e9:.1f}B")
```

### Maintenance CAPEX Model

```python
result = OwnerEarningsCalculator.calculate_maintenance_capex_model(
    net_income=36000.0,
    noncash_charges=1500.0,
    maintenance_capex=6500.0,  # Estimated, not total
    required_working_capital_investment=500.0,
    context=context,
    recurring_economic_adjustments=200.0,
)

print(f"Maintenance CAPEX OE: ${result.value / 1e9:.1f}B")
```

### CFO Model

```python
result = OwnerEarningsCalculator.calculate_cfo_model(
    operating_cash_flow=32300.0,  # From cash flow statement
    maintenance_capex=6500.0,
    context=context,
    recurring_economic_adjustments=200.0,
)

print(f"CFO OE: ${result.value / 1e9:.1f}B")
```

---

*See also: [maintenance_capex.md](maintenance_capex.md) for detailed maintenance CAPEX estimation methodology.*
