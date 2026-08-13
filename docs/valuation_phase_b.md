# Phase B: Advanced Valuation Suite — Bear Case, Capital Structure, Special Situations

## Overview

Phase B extends THE ACCOUNTANT valuation suite with three advanced analytical engines for fundamental research:

1. **Bear Case Engine** — Downside analysis via thesis breakers and risk factor scoring
2. **Capital Structure Engine** — Balance sheet optimization and capital allocation opportunities  
3. **Special Situations Engine** — Event-driven valuation (M&A, spin-offs, restructurings, bankruptcy)

All engines follow Phase A conventions: immutable frozen dataclasses, deterministic formula versioning, 100% ruff compliance, comprehensive unit tests, and CLI integration.

---

## 1. Bear Case Engine

### Purpose

Identifies automatic disqualifications (thesis breakers) and quantifies downside risk scenarios. Used to screen out broken businesses before entering valuation.

### Architecture

#### Thesis Breakers (Automatic Disqualifications)

A thesis breaker is a binary go/no-go gate that should prevent investment:

- **NEGATIVE_FCF** — Free cash flow ≤ 0 (company burning cash)
- **DECLINING_REVENUE** — Revenue down ≥2 consecutive years
- **UNSUSTAINABLE_DEBT** — Net leverage >4.0x AND FCF coverage <1.5x
- **CUSTOMER_CONCENTRATION** — Top customer >50% of revenue
- **CAPEX_INFLATION** — Capex growth >> revenue growth (red flag)
- **REGULATORY_RISK** — Known regulatory headwinds
- **MACRO_EXPOSURE** — High economic cycle sensitivity without moat
- **TECHNOLOGICAL_DISRUPTION** — Product or business model at risk
- **SECULAR_DECLINE** — Industry in structural decline

Each breaker flag includes:
- `description`: Specific metric that triggers it
- `severity`: CRITICAL, HIGH, MEDIUM for escalation
- `threshold_metric`: Quantitative threshold crossed
- `remediation`: What management would need to fix

#### Risk Factor Assessment

Risk factors are scored but don't disqualify the investment. They identify downside catalysts:

- **MARKET_SHARE_LOSS** — Competitor actions or market share erosion (0-60% probability)
- **MARGIN_COMPRESSION** — Pricing power loss or input cost inflation
- **MULTIPLE_DERATING** — P/E at 20+ year high (cyclical adjustment)
- **RECESSION_IMPACT** — Cyclical revenue/margin decline in downturn
- **CAPEX_SURPRISES** — Growth projects requiring unexpected capex
- **REFINANCING_RISK** — Debt maturities / rising rates
- **CUSTOMER_LOSS** — Top customer defection (especially post-concentration flag)
- **LITIGATION** — Legal or regulatory contingencies
- **EXECUTION_RISK** — Management change or operational missteps
- **LEVERAGE_SPIRAL** — Debt → downgrade → higher rates → default risk

Each factor contributes to overall risk score (0-100):
```
Risk Score = Σ(probability_pct × severity_weight × base_contribution)
```

#### Scenario Modeling

Three structured downside scenarios calibrated to bear factors:

1. **Recession** (40% base probability):
   - Revenue decline: 10-20% based on cyclicality
   - Margin compression: 200-400 bps
   - Multiple derating: 15-25% compression

2. **Margin Compression** (60% if detected):
   - Revenue held flat
   - EBIT margin decline: 300-600 bps
   - Multiple stable

3. **Regulatory/Structural** (varies):
   - Revenue impact: 5-30% depending on exposure
   - Margin impact: 50-200 bps

Final bear case price = Weighted average of three scenarios.

### API Usage

```python
from accountant.valuation import BearCaseEngine

# Step 1: Assess thesis breakers
breakers = BearCaseEngine.assess_thesis_breakers(
    fcf_current=-50,  # Negative!
    revenue_trend=[1000, 950, 900],  # Declining
    net_leverage_x=5.0,  # High
    fcf_coverage_x=1.2,  # Weak
    customer_concentration_pct=0.60,  # Risky
    capex_last_year=200,
    capex_prior_year=150,
    revenue_last_year=900,
    revenue_prior_year=950,
)

# If breakers exist, investment thesis is broken
for breaker in breakers:
    print(f"REJECT: {breaker.breaker.value} — {breaker.description}")

# Step 2: Assess risk factors (only if no thesis breakers)
if not breakers:
    risks = BearCaseEngine.assess_risk_factors(
        revenue=1000,
        ebit_margin_pct=15.0,
        cyclicality_beta=1.5,
        net_leverage_x=2.0,
        current_pe_multiple=20,
        historical_pe_multiple=15,
        # ... other factors
    )
    print(f"Risk Score: {sum(r.score_contribution for r in risks):.1f}/100")

# Step 3: Full bear case analysis
result = BearCaseEngine.calculate_bear_case(
    company_id="MSFT",
    fiscal_year=2024,
    as_of_date="2024-12-31",
    # Thesis breaker inputs
    fcf_current=80000,
    revenue_trend=[200000, 210000, 220000],
    net_leverage_x=1.0,
    fcf_coverage_x=3.5,
    # Risk factor inputs
    current_pe_multiple=28,
    historical_pe_multiple=25,
    # ... rest of inputs
)

print(f"Bear Case Price: ${result.bear_case_implied_price:.2f}")
print(f"Risk Score: {result.bear_case_risk_score:.0f}/100")
```

### CLI Command

```bash
# Basic bear case
accountant bear-case MSFT --fcf-current 80000 --net-leverage 1.0

# With scenarios
accountant bear-case AAPL \
  --revenue-prior 400000 \
  --revenue-current 420000 \
  --net-leverage 1.5 \
  --pe-current 28 \
  --pe-historical 20

# JSON output
accountant bear-case GOOGL --json-output
```

### Output Structure

```python
@dataclass(frozen=True)
class BearCaseResult:
    # Thesis breaker assessment
    thesis_breaker_flags: list[ThesisBreakerFlag]  # Disqualifications
    
    # Risk factor scoring
    risk_assessments: list[BearRiskAssessment]  # Individual risk scores
    bear_case_risk_score: float  # 0-100 aggregate score
    
    # Scenario-based pricing
    scenarios: list[BearCaseScenario]  # Recession, margin, regulatory
    bear_case_implied_price: float  # Weighted average
    bear_case_upside_to_target_pct: float  # vs. bull case
    bear_case_downside_pct: float  # vs. current price
    
    # Metadata
    formula_version: str  # BEAR_CASE_V1
    calculated_at: str  # ISO timestamp
```

---

## 2. Capital Structure Engine

### Purpose

Identifies balance sheet optimization opportunities: excess cash deployment, leverage headroom, buyback attractiveness, dividend sustainability, and refinancing opportunities.

### Architecture

#### Excess Cash Analysis

Distinguishes between operational minimum cash and true excess:

```
Excess Cash = Total Cash - Operating Minimum
Operating Minimum = (Annual OpEx) × (# Days / 365) × Safety Multiple
```

For MSFT:
- OpEx: $50B/year = $137M/day
- Days of Cash: 60 (standard operating)
- Safety Multiple: 1.5x
- Operating Minimum: ~$10B
- Total Cash: $60B
- **Excess Cash: $50B**

#### Leverage Opportunity

Compares current leverage to debt capacity:

```
Debt Capacity (Target Leverage) = EBITDA × Target Multiple
Current Debt = Book Debt
Borrowing Headroom = Debt Capacity - Current Debt
Interest Rate Assumed = Base Rate + Credit Spread
```

Target leverage by type:
- **CASH_RICH** (leverage <0.5x): Can borrow aggressively
- **UNDERLEVERAGED** (0.5x-2.0x): Significant headroom
- **OPTIMAL** (2.0x-3.0x): Efficient capital structure
- **OVERLEVERAGED** (3.0x-4.0x): Limited flexibility
- **FINANCIAL_DISTRESS** (>4.0x): Constrained

#### Buyback Opportunity

Assesses EPS accretion/dilution:

```
Current EPS = Net Income / Shares Outstanding
Post-Buyback Shares = Shares - (Buyback Spend / Stock Price)
New EPS = Net Income / Post-Buyback Shares

EPS Accretion = (New EPS - Current EPS) / Current EPS
```

Recommendation:
- **AGGRESSIVE** (>20% discount to intrinsic): High accretion
- **MODERATE** (10-20% discount): Neutral to slight accretion
- **CONSERVATIVE** (<10% discount): High valuation risk
- **NONE** (premium to intrinsic): Dilutive

#### Dividend Analysis

Evaluates sustainability and expansion room:

```
FCF Payout Ratio = Annual Dividend / Free Cash Flow
NI Payout Ratio = Annual Dividend / Net Income

Sustainability = (Payout Ratio < 60%) AND (Trend not negative)
Expansion Capacity = (Payout Ratio < 40%) AND (Debt < Target)
```

#### Capital Structure Type Classification

```python
if leverage < 0.5:
    structure_type = CASH_RICH
    top_priority = "Deploy excess cash: acquisition, buyback, or dividend"
elif leverage < 2.0:
    structure_type = UNDERLEVERAGED
    top_priority = "Consider borrowing for buyback/acquisition"
elif leverage < 3.0:
    structure_type = OPTIMAL
    top_priority = "Maintain current structure; deploy organic cash"
elif leverage < 4.0:
    structure_type = OVERLEVERAGED
    top_priority = "Reduce debt; conserve cash"
else:
    structure_type = FINANCIAL_DISTRESS
    top_priority = "Immediate debt reduction; preserve liquidity"
```

### API Usage

```python
from accountant.valuation import CapitalStructureEngine

result = CapitalStructureEngine.calculate_capital_structure(
    company_id="AAPL",
    fiscal_year=2024,
    as_of_date="2024-12-31",
    total_cash_usd=50000,  # $50B
    total_debt_usd=10000,  # $10B
    market_cap_usd=3000000,  # $3T
    fcf_available_usd=100000,  # $100B
    net_income_usd=110000,  # $110B
    shares_outstanding=15000,  # 15B shares
    stock_price=200.0,  # $200/share
    intrinsic_value_estimate=180.0,  # $180/share
    sector="TECHNOLOGY",
)

# Access opportunities
if result.excess_cash_analysis and result.excess_cash_analysis.excess_cash_usd > 0:
    print(f"Deploy ${result.excess_cash_analysis.excess_cash_usd:.0f}M excess cash")

if result.can_borrow_more:
    print(f"Borrow ${result.leverage_opportunity.borrowing_capacity_usd:.0f}M headroom")

if result.buyback_opportunity and result.buyback_opportunity.buyback_is_accretive:
    print(f"Buyback accretive: {result.buyback_opportunity.eps_accretion_pct:.1f}% EPS accretion")

# Top 3 priorities
for priority in result.top_priorities[:3]:
    print(f"→ {priority}")
```

### CLI Command

```bash
# Capital structure analysis
accountant capital-structure AAPL \
  --cash 50000 \
  --debt 10000 \
  --equity-cap 3000000 \
  --fcf 100000 \
  --net-income 110000

# JSON output
accountant capital-structure MSFT --json-output
```

### Output Structure

```python
@dataclass(frozen=True)
class CapitalStructureResult:
    company_id: str
    fiscal_year: int
    as_of_date: str
    
    # Analyses
    excess_cash_analysis: ExcessCashAnalysis
    leverage_opportunity: LeverageOpportunity
    buyback_opportunity: BuybackOpportunity
    dividend_analysis: DividendAnalysis
    
    # Classification
    structure_type: CapStructureType  # CASH_RICH, UNDERLEVERAGED, etc.
    has_excess_cash: bool
    can_borrow_more: bool
    
    # Use cases and priorities
    excess_cash_use_cases: list[str]
    top_priorities: list[str]
    
    formula_version: str  # CAPITAL_STRUCTURE_V1
    calculated_at: str
```

---

## 3. Special Situations Engine

### Purpose

Event-driven valuation for M&A, spin-offs, tender offers, and restructurings. Identifies mispricing and deal risk/reward.

### Architecture

#### Acquisition Scenarios

For a target company (acquisition target):

```
Control Premium = 20-40% (historical median 30%)
Adjusted Premium = Base ± Strategic Factors ± Regulatory Risk
Implied Price = Current Price × (1 + Control Premium)
Deal Probability = 35% base ± Strategic Fit ± Regulatory Risk
```

Inputs:
- `target_current_stock_price`: Market price
- `shares_outstanding`: Diluted shares
- `enterprise_value_usd`: Current EV
- `strategic_buyer_exists`: +15% premium, +15% probability
- `regulatory_risk`: -10% premium, -10% probability
- `synergy_potential_usd`: Optional acquirer cost/revenue synergies

Output: `AcquisitionScenario` with implied price, premium, deal likelihood.

#### Tender Offer (Take-Private)

For special situations (management buyout, activist take-private):

```
Offer Price = Current × 1.30 (example)
Arbitrage Spread = (Offer - Current) / Current
Deal Certainty = Financing Certainty × Regulatory Certainty
```

Scenarios:
- **High Certainty (>80%)**: Small spread risk, high deal success
- **Medium (50-80%)**: Moderate spread, execution risk
- **Low (<50%)**: Large spread, significant fail risk (downside -10% to -30%)

#### Spin-Off (Separation)

For parent company splitting off a division:

```
Sum-of-the-Parts Valuation:
  Parent Standalone Value = Parent EBIT × P/E Multiple
  Spinco Value = Spinco EBIT × P/E Multiple (usually higher)
  SOTP = Parent Value + Spinco Value
  Value Creation = (SOTP - Current Market Cap) / Current Market Cap
```

Considerations:
- Standalone viability score (1-10 scale)
- Synergy loss from separation
- Tax efficiency (tax-free reorganization or taxable)

#### Restructuring (Bankruptcy)

For distressed situations:

```
Recovery Value = Enterprise Value × Recovery %
  Chapter 11: Debt recovery ~70%, Equity recovery ~5%
  Out-of-Court: Debt recovery ~80%, Equity recovery ~10%
  
New Equity Dilution = (1 - Debt Recovery) × Debt / Equity Value
Timeline: CH11 ~18 months, OOC ~12 months
```

#### Mispricing Detection

Probability-weighted expected value:

```
EV = Bear Case Price × (1 - Probability) + Bull Case × Probability
Mispricing = (Current Price - EV) / EV
  > 5%  → DOWNSIDE (stock overvalued)
  < -5% → UPSIDE (stock undervalued)
  else → FAIR
```

### API Usage

```python
from accountant.valuation import SpecialSituationsEngine, SpecialSituationType

# Model M&A acquisition
acq = SpecialSituationsEngine.model_acquisition(
    target_current_stock_price=100.0,
    shares_outstanding=100.0,
    enterprise_value_usd=10000.0,
    strategic_buyer_exists=True,  # +premium
    synergy_potential_usd=500.0,
    regulatory_risk=False,
)
print(f"Implied Price: ${acq.implied_price_per_share:.2f}")
print(f"Deal Probability: {acq.deal_likelihood_pct:.0f}%")

# Model tender offer (take-private)
tender = SpecialSituationsEngine.model_tender_offer(
    current_stock_price=100.0,
    offer_price_per_share=130.0,
    financing_certainty_pct=85,  # Some risk
    regulatory_certainty_pct=90,
)
print(f"Arbitrage Spread: {tender.arbitrage_spread_pct:.1f}%")
print(f"Deal Certainty: {tender.deal_certainty_pct:.0f}%")
print(f"Downside if Fails: {tender.downside_if_fails_pct:.0f}%")

# Full analysis
result = SpecialSituationsEngine.calculate_special_situations(
    company_id="MSFT",
    fiscal_year=2024,
    as_of_date="2024-12-31",
    situation_type=SpecialSituationType.M_AND_A_ACQUISITION,
    current_stock_price=100.0,
    base_case_price=100.0,
    event_probability_pct=60,
    acquisition_scenario=acq,
)

print(f"Expected Value: ${result.expected_value_price:.2f}")
print(f"Mispricing: {result.mispricing_opportunity}")
print(f"Action: {result.action}")
```

### CLI Command

```bash
# M&A scenario
accountant special-situations MSFT \
  --situation-type M_AND_A_ACQUISITION \
  --probability 60 \
  --base-case-price 100

# Tender offer scenario
accountant special-situations SNAP \
  --situation-type TENDER_OFFER \
  --current-price 12.50 \
  --base-case-price 15.00 \
  --probability 70

# JSON output
accountant special-situations ZOOM --situation-type SPIN_OFF --json-output
```

### Output Structure

```python
@dataclass(frozen=True)
class SpecialSituationResult:
    company_id: str
    fiscal_year: int
    as_of_date: str
    
    # Event assessment
    situation_type: SpecialSituationType
    event_probability: EventProbability
    probability_pct: float
    
    # Price scenarios
    base_case_price: float
    bull_case_price: float
    bear_case_price: float
    expected_value_price: float
    
    # Scenario details
    acquisition_scenario: AcquisitionScenario | None
    tender_offer_scenario: TenderOfferScenario | None
    spinoff_scenario: SpinOffScenario | None
    restructuring_scenario: RestructuringScenario | None
    
    # Risk/Mispricing
    deal_risks: list[str]
    key_catalysts: list[str]
    timeline_milestones: list[str]
    current_price_vs_base_case_pct: float
    current_price_vs_expected_value_pct: float
    mispricing_opportunity: str  # UPSIDE, DOWNSIDE, FAIR
    
    # Action
    investment_thesis: str
    action: str  # BUY, REDUCE, HOLD, AVOID
    catalyst_timeline: str
    risk_reward: str
    
    formula_version: str  # SPECIAL_SITUATIONS_V1
    calculated_at: str
```

---

## 4. Integration with Phase A

Phase B engines are designed to work alongside Phase A:

### Workflow

1. **Initial Valuation (Phase A)**
   - Run DCF, Multiples, NAV/SOTP
   - Establish base case, bull case, bear case prices
   - Compute WACC and capital structure snapshot

2. **Thesis Validation (Phase B Bear Case)**
   - Check for thesis breakers (automatic disqualifications)
   - If any breaker triggered → REJECT investment
   - Score risk factors for downside analysis
   - Compare bear case price to base/bull prices

3. **Capital Allocation (Phase B Capital Structure)**
   - Assess balance sheet efficiency
   - Identify excess cash deployment opportunities
   - Evaluate buyback vs. other uses of capital
   - Understand leverage and refinancing runway

4. **Event Scenarios (Phase B Special Situations)**
   - If M&A rumors/activity: model acquisition scenarios
   - If restructuring risk: model bankruptcy recovery
   - If spin-off candidate: model SOTP value creation
   - Estimate event probability and deal risk/reward

### Example: Complete Analysis

```python
from accountant.valuation import (
    ValuationEngine,
    BearCaseEngine,
    CapitalStructureEngine,
    SpecialSituationsEngine,
)

ticker = "MSFT"
company_id = ticker
fiscal_year = 2024
as_of_date = "2024-12-31"

# Phase A: Base valuation
dcf = ValuationEngine.calculate_dcf(...)
print(f"DCF Range: ${dcf.bear_price_per_share:.2f} - ${dcf.bull_price_per_share:.2f}")

# Phase B1: Bear case
bear = BearCaseEngine.calculate_bear_case(...)
if bear.thesis_breaker_flags:
    print("REJECT: Thesis breakers detected")
else:
    print(f"Risk Score: {bear.bear_case_risk_score:.0f}/100")

# Phase B2: Capital structure
capstruct = CapitalStructureEngine.calculate_capital_structure(...)
print(f"Structure Type: {capstruct.structure_type.value}")
print(f"Top Priority: {capstruct.top_priorities[0]}")

# Phase B3: Special situations
special = SpecialSituationsEngine.calculate_special_situations(...)
print(f"Expected Value: ${special.expected_value_price:.2f}")
print(f"Action: {special.action}")

# Synthesis
print(f"\n=== Investment Summary ===")
print(f"Base Case (DCF): ${dcf.base_price_per_share:.2f}")
print(f"Bear Case Risk: {bear.bear_case_risk_score:.0f}/100")
print(f"Opportunity: {capstruct.structure_type.value}")
print(f"Event Probability: {special.probability_pct:.0f}%")
```

---

## 5. Testing

All three engines include comprehensive unit test suites:

### Test Coverage

**Bear Case Engine (10 tests)**
- Thesis breaker detection (NEGATIVE_FCF, DECLINING_REVENUE, etc.)
- Risk factor assessment and scoring
- Scenario modeling (recession, margin, regulatory)
- Bear case pricing and downside calculation

**Capital Structure Engine (9 tests)**
- Excess cash analysis and deployment
- Leverage opportunity and borrowing capacity
- Buyback opportunity and EPS accretion
- Dividend sustainability and expansion room
- Structure type classification

**Special Situations Engine (12 tests)**
- Acquisition scenario modeling and control premiums
- Tender offer arbitrage spread and deal certainty
- Spin-off value creation and standalone viability
- Restructuring recovery scenarios and dilution
- Mispricing detection and event probability

**Total: 31 new tests** (all passing)

Run tests:
```bash
uv run pytest tests/test_phase_b.py -v
```

---

## 6. Code Quality & Compliance

### Ruff Compliance

All Phase B code is 100% compliant with project linting rules:
- **E/F**: Error and undefined names
- **I**: Import organization
- **UP**: Syntax upgrades
- **B**: Bugbear conventions
- **SIM**: Simplification rules
- **E501**: Line length (explicitly ignored)

```bash
uv run ruff check src/accountant/valuation/
# All checks passed!
```

### Immutability & Versioning

All output dataclasses use `@dataclass(frozen=True)`:
- Prevents accidental mutation
- Enables hashability for caching
- Enforces explicit re-run for new analysis

Formula versions tracked:
- `BEAR_CASE_V1` — Initial formula version
- `CAPITAL_STRUCTURE_V1` — Initial formula version
- `SPECIAL_SITUATIONS_V1` — Initial formula version

Timestamp every result: `calculated_at: str` (ISO 8601)

### Error Handling

All CLI commands include structured error handling:
```python
except Exception as e:
    console.print(f"[red]Error: {e}[/red]")
    log.exception("command_failed", ticker=ticker, error=str(e))
    raise typer.Exit(1) from None
```

---

## 7. CLI Reference

### Bear Case

```bash
accountant bear-case TICKER [OPTIONS]

Options:
  --fcf-current FLOAT              Current FCF ($ millions)
  --revenue-prior FLOAT            Prior year revenue ($ millions)
  --revenue-current FLOAT          Current year revenue ($ millions)
  --net-leverage FLOAT             Net leverage ratio [default: 2.0]
  --fcf-coverage FLOAT             FCF coverage ratio [default: 2.0]
  --customer-concentration FLOAT   Top customer concentration (0-1) [default: 0.3]
  --pe-current FLOAT               Current P/E multiple
  --pe-historical FLOAT            Historical P/E multiple
  --json-output                    Output as JSON
```

Example:
```bash
accountant bear-case MSFT \
  --fcf-current 80000 \
  --net-leverage 1.0 \
  --customer-concentration 0.15
```

### Capital Structure

```bash
accountant capital-structure TICKER [OPTIONS]

Options:
  --cash FLOAT                 Current cash ($ millions)
  --debt FLOAT                 Current debt ($ millions)
  --equity-cap FLOAT           Market cap ($ millions)
  --fcf FLOAT                  Free cash flow ($ millions)
  --net-income FLOAT           Net income ($ millions)
  --json-output                Output as JSON
```

Example:
```bash
accountant capital-structure AAPL \
  --cash 50000 \
  --debt 10000 \
  --equity-cap 3000000
```

### Special Situations

```bash
accountant special-situations TICKER [OPTIONS]

Options:
  --situation-type STR       Situation type (M_AND_A_ACQUISITION, TENDER_OFFER, SPIN_OFF, etc.)
  --current-price FLOAT      Current stock price
  --base-case-price FLOAT    Base case valuation per share
  --probability FLOAT        Event probability (0-100) [default: 50]
  --json-output              Output as JSON
```

Example:
```bash
accountant special-situations MSFT \
  --situation-type M_AND_A_ACQUISITION \
  --probability 60 \
  --current-price 380 \
  --base-case-price 380
```

---

## 8. Known Limitations & Future Work

### Current Scope (Phase B)

✅ Thesis breaker detection  
✅ Risk factor scoring and scenarios  
✅ Excess cash and leverage analysis  
✅ Buyback accretion modeling  
✅ Dividend sustainability  
✅ M&A, tender, spin-off, restructuring scenarios  
✅ Mispricing detection  
✅ CLI integration  
✅ 100% test coverage  

### Future Enhancements (Phase C+)

- **Multi-year Projections** — Extend bear case scenarios across forecast period
- **Monte Carlo Simulation** — Probabilistic scenarios for key variables
- **Peer Comparison** — Benchmark risk scores against industry peers
- **Sensitivity Analysis** — One-way and two-way sensitivity on key inputs
- **Scenario Blending** — Custom probability-weighted combinations of events
- **Deep-Dive Reports** — Executive summary with detailed exhibits
- **Real-Time Data** — Live market cap, debt, cash from SEC filings
- **Database Storage** — Persist analyses for tracking and comparison over time
- **Recommendation Tracking** — Monitor actual outcomes vs. predicted scenarios

---

## 9. Philosophy & Design

### Determinism

Every result is fully deterministic. Same inputs = same output, every time. No randomness, no LLM inference, no guessing.

### Conservatism in Downside

Bear case assumes worst-case scenario: no synergies, cyclical downturn, competitive loss. Better to be surprised upside than blindsided downside.

### Balance Sheet Over Income

Capital structure analysis prioritizes balance sheet strength and cash generation over accounting earnings. A strong balance sheet gives a weak company time to improve.

### Event-Driven Edge

Special situations capture mispricing when markets misprice deal risk, timing, or recovery value. Systematic analysis beats sentiment.

### Formula Transparency

Every calculation is explicit, versioned, and auditable. No black boxes. Analysts can understand, challenge, and improve the formulas.

---

## References

- **Phase A Documentation** — [valuation_engine.md](valuation_engine.md)
- **Architecture** — [architecture.md](architecture.md)
- **Permanent Rules** — [PERMANENT_RULES.md](../PERMANENT_RULES.md)
