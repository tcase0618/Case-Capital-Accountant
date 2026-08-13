# Capital Allocation Efficiency

**Purpose:** Evaluate whether a company's capital allocation decisions create or destroy shareholder value using ROIC-vs-WACC as the deterministic threshold.

**Why:** Not all capital deployment is value-creating. A company investing in projects with ROIC < WACC destroys value. Another returning cash via buybacks when ROIC > WACC also destroys value. This framework quantifies the efficiency of capital allocation decisions.

---

## Core Concept: ROIC vs. WACC Threshold

### The Rule

```
If Incremental ROIC > WACC  →  VALUE-CREATING allocation
If Incremental ROIC < WACC  →  VALUE-DESTROYING allocation
If Incremental ROIC ≈ WACC  →  NEUTRAL allocation
```

**Economic Intuition:**
- **ROIC** = Return on Incremental Invested Capital (what the company earns on new investments)
- **WACC** = Weighted Average Cost of Capital (what investors demand as return)
- If a company invests at 15% ROIC and costs 9% WACC, it creates (15% - 9%) = 6% economic spread
- If a company invests at 7% ROIC at 9% WACC, it destroys 2% value per dollar deployed

---

## The Model

### Formula

```
Allocation Score = {
    "VALUE_CREATING" if ROIC > WACC AND deployed in CapEx
    "APPROPRIATE" if ROIC > WACC AND NOT deployed in CapEx
    "VALUE_DESTROYING" if ROIC < WACC
    "NEUTRAL" if ROIC ≈ WACC (or no allocation)
}

ROIC Spread = Incremental ROIC - WACC
```

### Parameters

**Incremental ROIC:**
- Return on new capital deployed this period
- Calculated as: (Change in NOPAT) / (Change in Invested Capital)
- Annualized if multi-year investment
- Formula version: [[owner_earnings.md]] references

**WACC (Weighted Average Cost of Capital):**
- Cost of debt: Weighted by book value, tax-adjusted
- Cost of equity: Typically CAPM (risk-free rate + beta × equity risk premium)
- Typical range: 6–12% for mature companies

**Capital Deployment (in millions):**
- **Capital Expenditure** — CapEx from cash flow statement
- **Share Repurchases** — Cash used to repurchase own shares
- **Dividends** — Cash returned to shareholders
- **Debt Reduction** — Debt paydown (alternative to dividend)

### Output Structure

```python
{
    "calculation_id": "CAPITAL_ALLOCATION",
    "formula_version": "CAPITAL_ALLOCATION_THRESHOLD_V1",
    "company_id": "AAPL",
    "fiscal_year": 2024,
    "fiscal_quarter": None,
    "value": "VALUE_CREATING",  # Assessment
    "unit": "assessment",
    "calculation_status": "VALID",  # or INSUFFICIENT_DATA
    "formula": "Allocation Score = ROIC vs WACC threshold",
    "inputs": {
        "owner_earnings": 10000.0,
        "capital_expenditure": 5000.0,
        "share_repurchases": 3000.0,
        "dividends": 2000.0,
        "debt_reduction": 0.0,
        "incremental_roic": 15.0,  # percent
        "wacc": 9.0  # percent
    },
    "metadata": {
        "owner_earnings": 10000.0,
        "total_allocated": 10000.0,
        "allocation_pct": 100.0,
        "unallocated": 0.0,
        "capex": 5000.0,
        "repurchases": 3000.0,
        "dividends": 2000.0,
        "debt_reduction": 0.0,
        "incremental_roic": 15.0,
        "wacc": 9.0,
        "roic_spread": 6.0,  # 15 - 9
        "allocation_score": "VALUE_CREATING"
    },
    "warnings": [],
    "calculated_at": "2024-08-12T14:30:00Z"
}
```

---

## Capital Allocation Scenarios

### Scenario 1: Value-Creating CapEx (Best Case)

```
Owner Earnings (OE):         $10,000M
Incremental ROIC:            15% (new plants, product lines)
WACC:                        9%
ROIC Spread:                 6% (positive)

Capital Deployment:
  CapEx (new plants):        $5,000M
  Share Repurchases:         $3,000M
  Dividends:                 $2,000M
  ─────────────────
  Total Allocated:           $10,000M (100% of OE)

Assessment: VALUE_CREATING
→ Deploying at 15% ROIC when cost is 9%
→ Every dollar of CapEx creates ~$0.06 value
→ Appropriate to reinvest; buybacks only after reinvestment needs met
```

**Verdict:** Excellent capital allocation. Company should prioritize CapEx.

---

### Scenario 2: Value-Destroying CapEx (Worst Case)

```
Owner Earnings (OE):         $10,000M
Incremental ROIC:            6% (mature, low-growth projects)
WACC:                        9%
ROIC Spread:                 -3% (negative)

Capital Deployment:
  CapEx (maintenance):       $4,000M
  Share Repurchases:         $0M
  Dividends:                 $3,000M
  Debt Reduction:            $3,000M
  ─────────────────
  Total Allocated:           $10,000M (100% of OE)

Assessment: VALUE_DESTROYING
→ Deploying at 6% ROIC when cost is 9%
→ Every dollar of CapEx destroys ~$0.03 value
→ Should return cash to shareholders (buyback or dividend)
```

**Verdict:** Poor capital allocation. Company should reduce CapEx and return capital.

---

### Scenario 3: Neutral/Appropriate (Mature Company)

```
Owner Earnings (OE):         $10,000M
Incremental ROIC:            9% (mature, stable returns)
WACC:                        9%
ROIC Spread:                 0% (exactly at threshold)

Capital Deployment:
  CapEx (maintenance):       $2,000M
  Dividends:                 $5,000M
  Share Repurchases:         $3,000M
  ─────────────────
  Total Allocated:           $10,000M (100% of OE)

Assessment: NEUTRAL
→ CapEx returns exactly cost of capital (no spread)
→ Buybacks and dividends appropriate for mature business
→ Stable value creation (neither creating nor destroying)
```

**Verdict:** Reasonable for mature company. Maintain current allocation.

---

### Scenario 4: Partial Allocation (Flexible)

```
Owner Earnings (OE):         $10,000M
Incremental ROIC:            14% (high-growth opportunities)
WACC:                        8%
ROIC Spread:                 6% (strongly value-creating)

Capital Deployment:
  CapEx (growth):            $6,000M
  Share Repurchases:         $3,000M
  Dividends:                 $1,000M
  ─────────────────
  Total Allocated:           $10,000M (100% of OE)
  Unallocated:               $0M

Assessment: VALUE_CREATING
→ Strong ROIC spread (6%) suggests invest more
→ Could justify increasing CapEx beyond maintenance
→ Buybacks only after all high-return projects funded
```

**Verdict:** Excellent. Company should increase reinvestment rate; reduce buybacks/dividends.

---

## Three-Metric Assessment

### Allocation Pct (Capital Utilization)
```python
allocation_pct = (total_allocated / owner_earnings) * 100
```

| Allocation % | Assessment | Interpretation |
|--------------|------------|-----------------|
| **< 50%** | Underallocated | Cash piling up; likely value-destroying (not deploying) |
| **50–100%** | Fully allocated | Typical; company using earnings for growth/returns |
| **> 100%** | Overextended | Using debt/cash reserves; may signal growth ambitions or low earnings |

---

### Allocation Mix (Composition)

| Mix Type | Example | Interpretation |
|----------|---------|-----------------|
| **100% CapEx** | CapEx $10B / OE $10B | High-growth, reinvesting all earnings |
| **70% CapEx + 30% Dividend** | CapEx + Div = $10B | Balanced (mature growth company) |
| **50% CapEx + 50% Buyback** | CapEx + Buyback = $10B | Growth with shareholder returns |
| **0% CapEx + 100% Buyback/Div** | Buyback + Div = $10B | Mature, low-growth, returning cash |

---

### ROIC Spread (Value Creation)

| Spread | Label | Action |
|--------|-------|--------|
| **> 5%** | High spread | Increase CapEx; reduce buybacks; reinvest |
| **2–5%** | Positive spread | Maintain current allocation; consider slight CapEx increase |
| **0–2%** | Near hurdle | Neutral; balanced allocation appropriate |
| **< 0%** | Negative spread | Reduce CapEx; increase buybacks/dividends; return capital |

---

## Implementation Details

### Formula Calculation

**Input Requirements:**
```
Owner Earnings (cash available after reinvestment)
Incremental Invested Capital (new capex)
Incremental ROIC (return on new capital)
WACC (cost of capital)
CapEx (capital expenditure deployment)
Share Repurchases (buyback deployment)
Dividends (dividend deployment)
Debt Reduction (deleverage deployment)
```

**Computation (Python):**
```python
from accountant.calculations import CapitalAllocationCalculator, CalculationContext

context = CalculationContext(company_id="AAPL", fiscal_year=2024)

result = CapitalAllocationCalculator.evaluate_allocation(
    owner_earnings=10000.0,
    incremental_invested_capital=3000.0,
    incremental_roic=15.0,  # percent
    wacc=9.0,  # percent
    capital_expenditure=5000.0,
    share_repurchases=3000.0,
    dividends=2000.0,
    debt_reduction=0.0,
    context=context
)

print(f"Assessment: {result.value}")
print(f"ROIC Spread: {result.metadata['roic_spread']}%")
print(f"Allocation: {result.metadata['allocation_pct']:.1f}%")
```

**Validation:**
- Owner earnings required (None → INSUFFICIENT_DATA)
- Total allocated must be > $1M (threshold) or INSUFFICIENT_DATA
- ROIC and WACC optional (if missing, score = "UNKNOWN")

---

## Scenario Analysis

### Growth Company (High ROIC)

```
Owner Earnings:           $5,000M
CapEx Needs:              $4,000M (high-growth expansion)
Incremental ROIC:         18% (new markets, products)
WACC:                     8%
ROIC Spread:              +10% (excellent)

Allocation:
  CapEx:                  $4,000M
  Dividends:              $1,000M
  ─────────────────
  Total:                  $5,000M

Score: VALUE_CREATING
Recommendation: Increase CapEx further; reduce dividend
```

**Rationale:** Every dollar invested at 18% ROIC vs. 8% WACC creates 10% spread. Shareholder returns secondary to growth.

---

### Mature Company (Moderate ROIC)

```
Owner Earnings:           $8,000M
CapEx Needs:              $2,000M (maintenance only)
Incremental ROIC:         10% (stable market)
WACC:                     7%
ROIC Spread:              +3% (modest)

Allocation:
  CapEx:                  $2,000M
  Dividends:              $3,000M
  Buybacks:               $3,000M
  ─────────────────
  Total:                  $8,000M

Score: APPROPRIATE
Recommendation: Maintain allocation; strong dividend foundation
```

**Rationale:** After funding necessary CapEx, return excess to shareholders. 3% spread modest but positive.

---

### Declining Company (Low ROIC)

```
Owner Earnings:           $6,000M
CapEx Needs:              $1,500M (cost reduction only)
Incremental ROIC:         5% (shrinking market)
WACC:                     10%
ROIC Spread:              -5% (destructive)

Allocation:
  CapEx:                  $1,500M
  Dividends:              $2,000M
  Buybacks:               $2,500M
  ─────────────────
  Total:                  $6,000M

Score: VALUE_DESTROYING
Recommendation: Cut CapEx further; maximize cash returns
```

**Rationale:** CapEx at 5% ROIC destroys -5% value vs. 10% WACC. Prioritize returning capital to shareholders.

---

## CLI Usage

### All Scenarios
```bash
uv run accountant capital-allocation AAPL --fiscal-year 2024
```

**Output:**
```
Company: AAPL (2024 FY)
─────────────────────────────────────────
Owner Earnings:             $10,000M
Total Allocated:            $10,000M (100%)
───────────────────────────────────
Allocation Mix:
  CapEx:                    $5,000M (50%)
  Share Repurchases:        $3,000M (30%)
  Dividends:                $2,000M (20%)
  Debt Reduction:           $0M (0%)
───────────────────────────────────
Incremental ROIC:           15.0%
WACC:                       9.0%
ROIC Spread:                +6.0% (VALUE-CREATING)
───────────────────────────────────
Recommendation: Strong capital allocation
  → 15% returns exceed 9% cost of capital
  → CapEx deployment appropriate for 6% spread
  → Consider higher CapEx if more projects available at >9% ROIC
```

### With Explanation
```bash
uv run accountant capital-allocation AAPL --fiscal-year 2024 --explain
```

---

## Python API

### Basic Usage
```python
from accountant.calculations import CapitalAllocationCalculator, CalculationContext

context = CalculationContext(company_id="AAPL", fiscal_year=2024)

result = CapitalAllocationCalculator.evaluate_allocation(
    owner_earnings=10000.0,
    incremental_invested_capital=3000.0,
    incremental_roic=15.0,
    wacc=9.0,
    capital_expenditure=5000.0,
    share_repurchases=3000.0,
    dividends=2000.0,
    debt_reduction=0.0,
    context=context
)

print(f"Score: {result.value}")
print(f"Spread: {result.metadata['roic_spread']}%")
print(f"Allocated: {result.metadata['allocation_pct']:.1f}%")
```

### Scenario Comparison
```python
scenarios = [
    # Growth company
    {
        "name": "High-Growth",
        "oe": 5000, "roic": 18, "wacc": 8,
        "capex": 4000, "div": 1000, "buyback": 0, "debt": 0
    },
    # Mature company
    {
        "name": "Mature",
        "oe": 8000, "roic": 10, "wacc": 7,
        "capex": 2000, "div": 3000, "buyback": 3000, "debt": 0
    },
    # Declining company
    {
        "name": "Declining",
        "oe": 6000, "roic": 5, "wacc": 10,
        "capex": 1500, "div": 2000, "buyback": 2500, "debt": 0
    }
]

for scenario in scenarios:
    result = CapitalAllocationCalculator.evaluate_allocation(
        owner_earnings=scenario["oe"],
        incremental_invested_capital=scenario["capex"],
        incremental_roic=scenario["roic"],
        wacc=scenario["wacc"],
        capital_expenditure=scenario["capex"],
        share_repurchases=scenario["buyback"],
        dividends=scenario["div"],
        debt_reduction=scenario["debt"],
        context=context
    )
    
    print(f"{scenario['name']}: {result.value} ({result.metadata['roic_spread']:.1f}% spread)")
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
    value,
    unit,
    calculation_status,
    formula,
    inputs,
    metadata,
    calculated_at
) VALUES (
    'CAPITAL_ALLOCATION',
    'CAPITAL_ALLOCATION_THRESHOLD_V1',
    'AAPL',
    2024,
    'VALUE_CREATING',
    'assessment',
    'VALID',
    'Allocation Score = ROIC vs WACC threshold',
    '{"owner_earnings": 10000, "incremental_roic": 15, "wacc": 9, ...}',
    '{"allocation_score": "VALUE_CREATING", "roic_spread": 6.0, ...}',
    '2024-08-12 14:30:00'
);
```

---

## Known Issues & Limitations

### ROIC Estimation
1. **Incremental Basis** — Requires tracking new capital separately from existing base
2. **Time-Lag** — New CapEx may take 1–2 years to generate full returns (lag effect)
3. **Cyclicality** — Single-year ROIC may not reflect normalized return (use 3-year)

### WACC Calculation
1. **Beta Estimation** — Equity cost sensitive to beta; short-term volatility affects long-term estimate
2. **Target vs. Actual** — Companies operate at different capital structures; use target weights
3. **Tax Rate** — Debt cost assumes constant tax rate; changes affect WACC

### Capital Deployment
1. **Timing** — Annual allocations may not reflect mid-year decisions
2. **Unallocated Earnings** — Cash buildup signals either caution or poor capital discipline
3. **Hidden Allocations** — R&D, acquisitions may not show as traditional CapEx

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| **V1** | 2026-08-12 | Initial release: ROIC vs WACC threshold model |

---

## Related Documents

- [[owner_earnings.md]] — Owner earnings as OE input
- [[economic_debt.md]] — Leverage assumptions for WACC calculation
- [[dilution.md]] — Equity dilution impact on shares outstanding
- docs/maintenance_capex.md — Maintenance vs. growth CapEx breakdown

---

**For questions:** Contact the financial analysis team or file an issue on GitHub.
