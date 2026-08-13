# Valuation Engine: DCF, Multiples, Credit Analysis

## Overview

THE ACCOUNTANT's valuation suite provides deterministic, multi-method approaches to fundamental valuation:

- **DCF (Discounted Cash Flow)**: Intrinsic value based on projected free cash flows and terminal growth
- **Reverse DCF**: Market-implied assumptions given current price (what growth does the market assume?)
- **Credit Risk Analysis**: Leverage, coverage, maturity profile, and credit quality scoring
- **WACC Engine**: Cost of capital (equity and debt) for discount rate calculation
- **Method Applicability**: Automatic assessment of which methods are suitable for each company

## Architecture

### Core Engines

```
ValuationEngine
├── calculate_dcf()         → DCFValuation with bear/base/bull scenarios
├── assess_method_applicability() → ApplicabilityStatus
└── [Methods: DCF, Multiples, NAV, SOTP, Dividend Discount, etc.]

WACCEngine
├── calculate_cost_of_equity()  → CAPM (Rf + β(Rm - Rf) + CSP)
├── calculate_cost_of_debt()    → After-tax Rd
├── classify_capital_structure() → Type (EQUITY_HEAVY, BALANCED, DEBT_HEAVY, NO_DEBT)
└── calculate_wacc()            → WACC with sensitivities

ReverseDCFEngine
├── solve_for_terminal_growth() → Implied terminal growth rate
├── solve_for_discount_rate()   → Implied discount rate
└── calculate_reverse_dcf()     → Full market-implied analysis

CreditRiskEngine
├── calculate_leverage_metrics() → Gross/net leverage, debt/FCF ratios
├── calculate_coverage_metrics() → Interest/FCF/OE coverage
├── calculate_maturity_analysis() → Refinancing risk, duration
├── score_leverage/coverage/liquidity/maturity() → Component scoring (0-25 pts each)
└── calculate_credit_risk()     → Full credit profile with score (0-100)
```

### Data Flow

```
Financial Data (Debt, Cash, FCF, EBITDA, Interest Expense)
  ↓
WACCEngine → Cost of Equity + Cost of Debt
  ↓
ValuationEngine → DCF + Multiples + NAV + SOTP
  ↓
ReverseDCFEngine → Market-implied scenarios
  ↓
CreditRiskEngine → Credit quality score (VERY_STRONG to DISTRESSED)
```

## DCF Valuation

### Method

```
Enterprise Value = Σ(FCF_t / (1+r)^t) + (TV / (1+r)^n)

Where:
  FCF_t = Free cash flow in year t
  r = Discount rate (WACC)
  TV = Terminal value = FCF_n × (1+g) / (r - g)
  g = Terminal growth rate
  n = Forecast horizon
```

### Assumptions (V1)

| Assumption | Default | Customizable | Notes |
|-----------|---------|--------------|-------|
| **Terminal Growth** | 2.5% | Yes | Long-term GDP+inflation proxy |
| **Discount Rate** | 10% | Yes | WACC or fallback |
| **Tax Rate** | 21% | Yes | US federal rate |
| **Forecast Horizon** | 10 years | Yes | Explicit period |
| **FCF Projections** | Required | Required | From external calculations |

### Output

```python
DCFValuation(
    bear_pv = $750M              # 80% of base
    base_pv = $937M              # Central case
    bull_pv = $1,125M            # 120% of base
    
    bear_price_per_share = $7.50
    base_price_per_share = $9.37
    bull_price_per_share = $11.25
    
    terminal_value = $2,500M     # Perpetuity value
    terminal_growth_rate = 2.5%
    
    margin_of_safety_pct = -8.5% # vs $100 market price
    
    formula_version = "DCF_V1"
)
```

### Scenarios

- **Bear Case**: Assumes stress (low growth, high discount rate) → 80% of base
- **Base Case**: Central assumptions → primary valuation
- **Bull Case**: Optimistic (high growth, low risk) → 120% of base

## WACC Calculation

### Cost of Equity (CAPM)

```
Re = Rf + β(Rm - Rf) + CSP

Where:
  Rf = Risk-free rate (10Y Treasury)
  β = Company beta (systematic risk)
  Rm - Rf = Equity risk premium (6% default)
  CSP = Company-specific premium (size, liquidity, etc.)
```

### Cost of Debt

```
Rd_after_tax = (Interest Expense / Debt) × (1 - Tax Rate)

Incorporates:
  • Pre-tax cost from interest coverage
  • Tax shield benefit
  • Marginal tax rate
```

### WACC

```
WACC = (E/V × Re) + (D/V × Rd_after_tax)

Where:
  E/V = Equity weight
  D/V = Debt weight
  V = Total capital (E + D)
```

### Sensitivities

The WACC engine calculates:
- WACC if beta increases 20%
- WACC if equity risk premium increases 100bps
- WACC if debt weight moves to 50%

## Reverse DCF

### Concept

Given market price, solve for implied assumptions:

```
Market Price = Known Input
Terminal Growth = Solve For (or Discount Rate)

What growth rate justifies the $100 stock price?
What discount rate implies current valuation?
```

### Methodology

Uses binary search with convergence checking:
1. Set upper and lower bounds for solve variable
2. Iterate: calculate implied price with midpoint
3. Adjust bounds based on error
4. Converge to ±$0.01 price error

### Reasonableness Assessment

Checks solved assumptions against historical bounds:

| Variable | Reasonable Range | Out-of-Bounds |
|----------|-----------------|----------------|
| Terminal Growth | -1% to +4% | Outside GDP+inflation envelope |
| Discount Rate | 5% to 25% | Below risk-free or above extreme risk |
| Operating Margin | 0% to 50% | Unrealistic profit levels |
| Revenue Growth | -20% to +40% | Severe decline or hyper-growth |

### Output

```python
ReverseDCFResult(
    market_price_per_share = $100
    market_cap_usd = $5,000M
    
    solve_variable = SolveVariable.TERMINAL_GROWTH_RATE
    solve_status = SolveStatus.SOLVED
    
    market_implied_assumption = ReverseAssumption(
        variable = TERMINAL_GROWTH_RATE
        market_implied_value = 3.2%
        reasonable = True
        reasonableness_note = "Within 2.5%-4.0% GDP range"
    )
    
    upside_to_consensus = +0.5%  # vs. 2.7% consensus
    implied_vs_consensus = "Market aligned with consensus"
)
```

## Credit Risk Analysis

### Leverage Metrics

```
Gross Leverage = Debt / EBITDA
  • Measures total obligations vs. operating earnings
  • >4x suggests stress, <2x adequate

Net Leverage = (Debt - Cash) / EBITDA
  • After cash buffer available
  • >3x considered elevated

Debt / FCF = Debt / Free Cash Flow
  • Years to pay off debt from cash generation
  • >5x indicates refinancing risk

Debt / Owner Earnings
  • Uses cash earnings power (more conservative than NI)
```

### Coverage Metrics

```
Interest Coverage = EBITDA / Interest Expense
  • ≥8x: Excellent
  • 5-8x: Strong
  • 3-5x: Adequate
  • <1.5x: Critical

FCF Coverage = FCF / Interest Expense
  • More stringent than EBITDA coverage
  • Reflects actual cash available

Owner Earnings Coverage = Owner Earnings / Interest Expense
  • Uses sustainable earnings definition
```

### Maturity Analysis

```
Near-term Refinancing Risk = % of Debt Due <1 Year
  • >40%: Concentration risk
  • 20-40%: Elevated
  • <20%: Comfortable

Maturity Type:
  • CONCENTRATED: Single bucket >50%
  • BALANCED: Distributed across time buckets
  • LADDERED: Well-spaced maturities

Average Maturity: Weighted duration of debt
```

### Credit Quality Score (V1)

**Scoring Components** (25 points each = 100 total):

1. **Leverage Score** (0-25)
   - ≤1.0x net leverage → 25 pts (excellent)
   - ≤2.0x → 20 pts (strong)
   - ≤3.0x → 15 pts (adequate)
   - ≤4.0x → 8 pts (weak)
   - >4.0x → 2 pts (distressed)

2. **Coverage Score** (0-25)
   - ≥8.0x interest coverage → 25 pts (excellent)
   - ≥5.0x → 20 pts (strong)
   - ≥3.0x → 15 pts (adequate)
   - ≥1.5x → 8 pts (weak)
   - <1.5x → 2 pts (distressed)

3. **Liquidity Score** (0-25)
   - Cash / Debt Service ≥1.5x → 25 pts
   - ≥1.0x → 20 pts
   - ≥0.75x → 15 pts
   - ≥0.5x → 8 pts
   - <0.5x → 2 pts

4. **Maturity Score** (0-25)
   - Near-term refinancing <20% → 25 pts
   - <30% → 20 pts
   - <40% → 15 pts
   - <50% → 8 pts
   - >50% → 2 pts

**Credit Classification** (0-100):
- **VERY_STRONG**: 85-100 (minimal default risk)
- **STRONG**: 65-84 (low default risk)
- **ADEQUATE**: 45-64 (moderate risk)
- **WEAK**: 25-44 (elevated risk)
- **DISTRESSED**: <25 (distress signals)

## Method Applicability Rules

### DCF
- ✅ Non-financial, non-REIT companies with FCF history
- ❌ Banks, insurance companies, REITs (use FCFE/multiples instead)
- ❌ No FCF history (insufficient data)

### Dividend Discount Model
- ✅ Mature, stable dividend-paying companies
- ❌ Non-dividend payers or sporadic payments

### Peer Multiples (P/E, EV/EBITDA, etc.)
- ✅ Requires peer group (minimum 3-5 comparable companies)
- ❌ Unique business model or no peer data

### Historical Multiples
- ✅ Requires 5+ years of historical multiples
- ❌ New IPO or limited history

### Sum-of-the-Parts
- ✅ Multi-segment conglomerates with segment financials
- ❌ Single business or undisclosed segments

### Net Asset Value
- ✅ Banks, insurance, REITs, asset-heavy companies
- ❌ Service businesses with minimal tangible assets

## CLI Commands

### Valuation
```bash
# Basic DCF with defaults
accountant valuation MSFT

# Custom assumptions
accountant valuation AAPL --discount-rate 0.08 --terminal-growth 0.03

# Output as JSON
accountant valuation TSLA --json-output
```

### Reverse DCF
```bash
# Solve for terminal growth given market price
accountant reverse-dcf MSFT --current-price 350 --fcf-per-share 12

# Solve for discount rate instead
accountant reverse-dcf AAPL --solve-for discount_rate --current-price 175
```

### Credit Analysis
```bash
# Credit scoring with balance sheet data
accountant credit MSFT --gross-debt 60000 --ebitda 90000 --fcf 50000

# Quick credit check
accountant credit AAPL --gross-debt 120000 --cash 30000
```

## Python API

### DCF Example
```python
from accountant.valuation import ValuationEngine

# Project FCF for next 10 years (in millions)
fcf_projections = [1000, 1050, 1103, 1158, 1216, 1277, 1341, 1408, 1478, 1552]

dcf = ValuationEngine.calculate_dcf(
    company_id="MSFT",
    fiscal_year=2024,
    as_of_date="2024-12-31",
    fcf_projections=fcf_projections,
    terminal_growth=0.025,
    discount_rate=0.087,  # WACC
    forecast_horizon=10,
    shares_outstanding=2_400,
    reference_price=350,
)

print(f"Base valuation: ${dcf.base_price_per_share:.2f}")
print(f"Bull case: ${dcf.bull_price_per_share:.2f}")
print(f"Bear case: ${dcf.bear_price_per_share:.2f}")
print(f"Margin of Safety: {dcf.margin_of_safety_pct:.1f}%")
```

### WACC Example
```python
from accountant.valuation import WACCEngine

wacc = WACCEngine.calculate_wacc(
    company_id="MSFT",
    fiscal_year=2024,
    as_of_date="2024-12-31",
    market_cap_usd=3_100_000,
    debt_amount_usd=60_000,
    interest_expense_usd=2_500,
    tax_rate=0.15,
    risk_free_rate=0.045,
    beta=0.9,
    equity_risk_premium=0.065,
)

print(f"WACC: {wacc.wacc*100:.2f}%")
print(f"Cost of Equity: {wacc.cost_of_equity_components.cost_of_equity*100:.2f}%")
print(f"After-tax Cost of Debt: {wacc.cost_of_debt_components.after_tax_cost_of_debt*100:.2f}%")
```

### Credit Risk Example
```python
from accountant.valuation import CreditRiskEngine

credit = CreditRiskEngine.calculate_credit_risk(
    company_id="MSFT",
    fiscal_year=2024,
    as_of_date="2024-12-31",
    gross_debt_usd=60_000,
    cash_and_equivalents_usd=30_000,
    ebitda_usd=90_000,
    fcf_usd=50_000,
    owner_earnings_usd=55_000,
    operating_cf_usd=52_000,
    interest_expense_usd=2_500,
    debt_service_annual_usd=3_500,
    due_within_1_year_usd=3_000,
    due_within_1_3_years_usd=9_000,
    due_within_3_5_years_usd=15_000,
    due_after_5_years_usd=33_000,
)

print(f"Credit Rating: {credit.credit_quality_score.quality_classification}")
print(f"Credit Score: {credit.credit_quality_score.total_score:.0f}/100")
print(f"Net Leverage: {credit.leverage_metrics.net_leverage_x:.2f}x")
print(f"Interest Coverage: {credit.coverage_metrics.interest_coverage_x:.2f}x")
```

## Sector Applicability

### Technology (Software, SaaS)
- **Best Methods**: DCF (high FCF predictability), Multiples (P/S, P/E)
- **Skip**: NAV (limited tangible assets), Dividend Discount (no dividend)
- **Special Considerations**: High capex for data centers, R&D capitalization

### Financial Services (Banks, Insurance)
- **Best Methods**: P/B (price-to-book), Dividend Discount (if applicable), NAV
- **Skip**: DCF (different capital structure), EV/EBITDA (not applicable)
- **Special Considerations**: Regulatory capital constraints, provisioning changes

### REITs
- **Best Methods**: FFO multiples (funds from operations), NAV
- **Skip**: Traditional DCF (cash conversion different), P/E (distributed earnings)
- **Special Considerations**: Required dividend payout, asset valuations

### Utilities
- **Best Methods**: DDM (stable dividends), Regulatory ROE multiples
- **Skip**: Growth-based DCF (limited growth), Peer multiples (regulated)
- **Special Considerations**: Regulatory rate base, allowed returns

## Known Limitations

1. **No LLM Integration**: All valuation calculations are deterministic Python, no AI/ML analysis
2. **External FCF Input**: Engine assumes FCF projections provided externally
3. **Sector-Specific Rules**: Limited applicability rules (banks/REITs are excluded, not optimized)
4. **No Sentiment Analysis**: Based purely on financial fundamentals
5. **Point-in-Time Gaps**: Does not yet validate against historical information availability
6. **No Peer Lookup**: Peer selection must be manual or external
7. **Simplified Beta**: Does not calculate rolling beta; must be provided

## Versioning

All engines use explicit formula versions for reproducibility:

- **DCF_V1**: Basic PV calculation with terminal value
- **WACC_V1**: CAPM cost of equity, after-tax cost of debt
- **REVERSE_DCF_V1**: Binary search solver for terminal growth / discount rate
- **CREDIT_RISK_V1**: 4-component scoring (leverage, coverage, liquidity, maturity)
- **CREDIT_QUALITY_SCORE_V1**: Credit classification (VERY_STRONG to DISTRESSED)

## Testing

- **29 tests** covering all engines, scenarios, edge cases
- **100% ruff compliance** for code quality
- **Unit tests** for each component method
- **Integration tests** for full workflows

## Future Enhancements

- [ ] Peer multiples lookup (automated peer selection)
- [ ] Segment-level DCF (SOTP implementation)
- [ ] Operating leverage analysis (fixed vs. variable costs)
- [ ] Acquisition premium benchmarking
- [ ] Foreign exchange sensitivity
- [ ] Commodity/commodity-like cost hedging
- [ ] Monte Carlo valuation scenarios
- [ ] Historical backtest of valuations
