# Equity Dilution Analysis

**Purpose:** Quantify the economic dilution to current shareholders from stock-based compensation, warrants, and options—essential for accurate per-share valuation and capital allocation analysis.

**Why:** Reported shares outstanding don't include the dilutive effect of unvested equity grants or in-the-money options. GAAP earnings don't reflect SBC as a cash cost. Two methods capture these dynamics separately.

---

## The Two Dilution Models

### Model 1: Stock-Based Compensation (SBC) Dilution

**Best for:** Technology and growth companies, annual dilution tracking, cash flow analysis

```
SBC Dilution (Shares) = (SBC Expense × Vesting Years) / Stock Price
```

**Logic:**
- SBC is expensed over vesting period (typically 3–4 years)
- Each year's grant represents future dilution as shares vest
- Dividing expense by stock price estimates share count

**Parameters:**
- **SBC Expense** — Annual stock-based compensation (from income statement, often in 10-K footnote)
- **Vesting Years** — Typical vesting period (default: 3.0 years, often 4-year cliff with 1-year vest)
- **Stock Price** — Current or fiscal year-end stock price (for forward-looking dilution)

**When to Use:**
- Calculating annual dilution run-rate
- Determining "fully diluted" shares for per-share metrics (EPS, book value per share)
- Assessing executive compensation cost
- When SBC is material expense (tech companies)

**Example:**
```
Annual SBC Expense:     $20,000M  (from equity compensation note)
Vesting Years:          3.0 years
Stock Price (YE):       $200/share
────────────────────────────────
SBC Dilution:           (20,000 × 3.0) / 200 = 300M shares
Dilution %:             300M / 16B shares = 1.9%
```

**Interpretation:**
- 1.9% annual dilution is typical for mega-cap tech (AAPL, MSFT, GOOG)
- 3–5% typical for high-growth SaaS
- >10% suggests aggressive equity compensation

---

### Model 2: Warrants & Options Dilution (Treasury Stock Method)

**Best for:** Comprehensive diluted share count, option pools, structured finance

```
Net Dilution = ITM Shares - (Proceeds / Stock Price)
            = ITM Shares - Shares Repurchased
```

**Logic:**
- When warrant/option holders exercise, they inject capital at exercise price
- Company uses proceeds to repurchase shares at current market price
- Net dilution = gross shares issued minus shares repurchased

**Parameters:**
- **In-the-Money Warrants** — Warrant count where exercise price < current stock price
- **In-the-Money Options** — Option count where strike < current stock price
- **Average Exercise Price** — Weighted average strike price across all ITM instruments
- **Stock Price** — Current market price (for scenario analysis, use multiple prices)

**When to Use:**
- Calculating fully-diluted shares for EPS
- Assessing option pool adequacy
- Valuation models (PE multiples on diluted shares)
- When company has significant warrant or option overhang

**Example:**
```
In-the-Money Warrants:    50M
In-the-Money Options:     100M
Total ITM Shares:         150M
────────────────────────────────
Proceeds (150M × $150):   $22,500M
Shares Repurchased:       $22,500M / $200 = 112.5M
Net Dilution:             150M - 112.5M = 37.5M shares
Dilution %:               37.5M / 16B shares = 0.23%
```

**Interpretation:**
- Lower dilution than SBC in this scenario (warrants are deeper ITM)
- High average exercise price ($150) vs. stock price ($200) provides cushion
- If exercise price > stock price, warrants are out-of-money (zero dilution)

---

## Output Structure

### CalculationResult Fields

Both models return immutable `CalculationResult` objects:

```python
{
    "calculation_id": "DILUTION",
    "formula_version": "DILUTION_SBC_V1 | DILUTION_WARRANTS_OPTIONS_V1",
    "company_id": "TECH",
    "fiscal_year": 2024,
    "fiscal_quarter": None,
    "value": 300.0,  # Dilutive shares in millions
    "unit": "shares",
    "calculation_status": "VALID",  # or INSUFFICIENT_DATA
    "formula": "Dilution (SBC) = (SBC Expense × Vesting Years) / Stock Price",
    "inputs": {
        "shares_outstanding": 16000.0,
        "sbc_expense": 20000.0,
        "stock_price": 200.0,
        "sbc_vesting_years": 3.0
    },
    "metadata": {
        "method": "SBC",
        "shares_outstanding": 16000.0,
        "sbc_shares": 300.0,
        "dilution_percent": 1.875  # percentage
    },
    "warnings": [],
    "calculated_at": "2024-08-12T14:30:00Z"
}
```

---

## Dilution Tracking

### Annual vs. Cumulative

**Annual (incremental):**
```
SBC Dilution (2024) = 300M shares
```

**Cumulative (fully diluted):**
```
Reported Shares:        16,000M
+ SBC Dilution:           300M
+ Warrant/Option:          37.5M
─────────────────────────────
Fully Diluted Shares:   16,337.5M

Dilution %:             337.5 / 16,337.5 = 2.07%
```

**Use fully diluted shares for:**
- Earnings per share (EPS) calculations (reported vs. diluted)
- Book value per share (BVPS)
- Price-to-book (P/B) valuation multiples

---

## Model Comparison

| Factor | SBC Dilution | W&O Dilution |
|--------|--------------|--------------|
| **Formula Complexity** | Simple (linear) | Medium (treasury stock) |
| **Data Required** | SBC expense + stock price | ITM count + exercise prices |
| **Timing** | Annual (recurring) | Ongoing (until exercise) |
| **Magnitude** | Usually 1–5% | Usually 0.1–2% (exercise cushion) |
| **Visibility** | Clear in compensation note | Disclosed in equity footnote |
| **Timing Impact** | Front-loaded in fiscal year | Triggered by exercise event |

---

## Implementation Details

### SBC Dilution

**Query Structure (SQL):**
```sql
SELECT
    sbc_expense,           -- From note 19 (stock comp) or line item
    shares_outstanding,    -- Reported shares
    stock_price            -- Year-end or current
FROM financial_statement
WHERE company_id = 'TECH'
  AND fiscal_year = 2024
```

**Calculation (Python):**
```python
from accountant.calculations import DilutionCalculator, CalculationContext

context = CalculationContext(company_id="TECH", fiscal_year=2024)

result = DilutionCalculator.calculate_sbc_dilution(
    shares_outstanding=16000.0,
    sbc_expense=20000.0,
    stock_price=200.0,
    sbc_vesting_years=3.0,
    context=context
)

print(f"SBC Dilution: {result.value}M shares ({result.metadata['dilution_percent']:.2f}%)")
```

**Validation:**
- All fields required (None triggers INSUFFICIENT_DATA)
- Stock price must be > 0 (rejects zero or negative prices)
- SBC vesting years typically 3–4 (default: 3.0)

---

### Warrants & Options Dilution

**Query Structure (SQL):**
```sql
SELECT
    in_the_money_warrants,  -- From equity footnote
    in_the_money_options,
    avg_exercise_price,     -- Weighted average strike
    stock_price             -- Current or fiscal year-end
FROM financial_statement
WHERE company_id = 'TECH'
  AND fiscal_year = 2024
```

**Calculation (Python):**
```python
result = DilutionCalculator.calculate_warrants_options_dilution(
    shares_outstanding=16000.0,
    in_the_money_warrants=50.0,
    in_the_money_options=100.0,
    stock_price=200.0,
    avg_exercise_price=150.0,
    context=context
)

print(f"W&O Dilution: {result.value}M shares ({result.metadata['dilution_percent']:.2f}%)")
```

**Treasury Stock Method Breakdown:**
```
1. Total ITM Shares = 50M + 100M = 150M
2. Proceeds = 150M × $150 = $22,500M
3. Shares Repurchased = $22,500M / $200 = 112.5M
4. Net Dilution = 150M - 112.5M = 37.5M
```

**Edge Cases:**
- If avg_exercise_price > stock_price: Warrants/options are OTM (net dilution = 0)
- If in_the_money_warrants + in_the_money_options < threshold: INSUFFICIENT_DATA

---

## Scenario Analysis

### Price Sensitivity (SBC)

```python
stock_prices = [150, 175, 200, 225, 250]
for price in stock_prices:
    dilution = (20000 * 3.0) / price
    dilution_pct = (dilution / 16000) * 100
    print(f"@ ${price}: {dilution:.0f}M shares ({dilution_pct:.2f}%)")

# Output:
# @ $150: 400M shares (2.50%)
# @ $175: 343M shares (2.14%)
# @ $200: 300M shares (1.88%)
# @ $225: 267M shares (1.67%)
# @ $250: 240M shares (1.50%)
```

**Insight:** SBC dilution inversely correlates with stock price. Higher prices = lower dilutive share count (same $ cost spreads over fewer shares).

### Price Sensitivity (W&O Treasury Stock)

```python
stock_prices = [150, 175, 200, 225, 250]
itm_warrants, itm_options = 50, 100
avg_exercise = 150

for price in stock_prices:
    total_itm = itm_warrants + itm_options
    proceeds = total_itm * avg_exercise
    repurchased = proceeds / price if price > 0 else 0
    dilution = max(0, total_itm - repurchased)
    dilution_pct = (dilution / 16000) * 100
    print(f"@ ${price}: {dilution:.1f}M shares ({dilution_pct:.2f}%)")

# Output:
# @ $150: 0.0 shares (0.00%)   — Fully offset by repurchase
# @ $175: 21.4 shares (0.13%)
# @ $200: 37.5 shares (0.23%)
# @ $225: 50.0 shares (0.31%)
# @ $250: 60.0 shares (0.37%)
```

**Insight:** Dilution increases with stock price above exercise price. At exercise price ($150), dilution is zero (proceeds exactly offset issuance).

---

## Real-World Patterns

### Mega-Cap Tech (AAPL, MSFT, GOOG)
- **SBC Dilution:** 1.5–2.5% annually
- **W&O Dilution:** ~0.2–0.5% (most options deep ITM)
- **Total Fully Diluted:** 2–3% above reported shares
- **Reason:** Massive market caps make SBC dilution smaller percentage

### SaaS/Growth (CRM, NOW, DDOG)
- **SBC Dilution:** 3–5% annually
- **W&O Dilution:** ~0.5–1.5% (larger option pools)
- **Total Fully Diluted:** 4–7% above reported
- **Reason:** Smaller market caps, larger % SBC to recruit talent

### Biotech (AMGN, BIIB, VRTX)
- **SBC Dilution:** 1–2% annually
- **W&O Dilution:** 2–5% (legacy options, research team)
- **Total Fully Diluted:** 3–8% above reported
- **Reason:** High-value research talent, long-dated option grants

---

## CLI Usage

### All Dilution Models
```bash
uv run accountant dilution TECH --fiscal-year 2024
```

**Output:**
```
Company: TECH (2024 FY)
─────────────────────────────────────────
Method: SBC Dilution
  Shares Outstanding:   16,000M
  SBC Expense:          $20,000M
  Stock Price:          $200/share
  Vesting Years:        3.0
  ─────────────
  Dilution Shares:      300M
  Dilution %:           1.88%

Method: Warrants & Options (Treasury Stock)
  Shares Outstanding:   16,000M
  ITM Warrants:         50M
  ITM Options:          100M
  Total ITM:            150M
  Avg Exercise Price:   $150
  Stock Price:          $200
  ─────────────
  Proceeds:             $22,500M
  Shares Repurchased:   112.5M
  Net Dilution:         37.5M
  Dilution %:           0.23%

Total Fully Diluted Shares: 16,337.5M
```

### Single Method
```bash
uv run accountant dilution TECH --fiscal-year 2024 --method sbc
uv run accountant dilution TECH --fiscal-year 2024 --method warrants_options
```

---

## Python API

### Basic Usage
```python
from accountant.calculations import DilutionCalculator, CalculationContext

context = CalculationContext(company_id="TECH", fiscal_year=2024)

# SBC Dilution
sbc = DilutionCalculator.calculate_sbc_dilution(
    shares_outstanding=16000.0,
    sbc_expense=20000.0,
    stock_price=200.0,
    sbc_vesting_years=3.0,
    context=context
)

# Warrants & Options Dilution
wo = DilutionCalculator.calculate_warrants_options_dilution(
    shares_outstanding=16000.0,
    in_the_money_warrants=50.0,
    in_the_money_options=100.0,
    stock_price=200.0,
    avg_exercise_price=150.0,
    context=context
)

# Fully Diluted
fully_diluted = 16000.0 + sbc.value + wo.value
print(f"Fully Diluted Shares: {fully_diluted}M")
```

### Scenario Loop
```python
stock_prices = [150, 175, 200, 225, 250]

for price in stock_prices:
    sbc = DilutionCalculator.calculate_sbc_dilution(
        shares_outstanding=16000.0,
        sbc_expense=20000.0,
        stock_price=price,
        context=context
    )
    print(f"@ ${price}: {sbc.value:.0f}M shares ({sbc.metadata['dilution_percent']:.2f}%)")
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
    'DILUTION',
    'DILUTION_SBC_V1',
    'TECH',
    2024,
    300.0,
    'shares',
    'VALID',
    'Dilution (SBC) = (SBC Expense × Vesting Years) / Stock Price',
    '{"shares_outstanding": 16000.0, ...}',
    '{"method": "SBC", "dilution_percent": 1.88}',
    '2024-08-12 14:30:00'
);
```

---

## Known Issues & Limitations

### SBC Dilution
1. **Vesting Period Assumption** — Standard 3–4 years, but some tech companies use longer cliffs
2. **Expense vs. Grant Value** — SBC expense includes forfeitures; actual dilution is gross grants
3. **Option Pool** — Not all granted options vest (typical forfeiture rate: 10–15%)

### Warrants & Options
1. **ITM Definition** — Exercise price vs. current stock price. In declining markets, less ITM than expected
2. **Average Exercise Price** — Often disclosed, but may not match detailed strike breakdown
3. **Barrier to Exercise** — Some options have vesting cliffs or performance conditions

### General
1. **Stock Price Volatility** — Dilution estimates are point-in-time; recompute quarterly
2. **Data Gaps** — Smaller companies may not disclose all option detail
3. **Vintage Tracking** — Old option pools from prior acquisitions may not be tracked

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| **V1** | 2026-08-12 | Initial release: SBC and treasury stock methods |

---

## Related Documents

- [[capital_allocation.md]] — Capital allocation efficiency assessment
- [[economic_debt.md]] — Economic debt for leverage/WACC calculations
- [[owner_earnings.md]] — Owner earnings as valuation input
- docs/maintenance_capex.md — Maintenance CAPEX for free cash flow

---

**For questions:** Contact the financial analysis team or file an issue on GitHub.
