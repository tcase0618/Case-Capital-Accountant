# THE ACCOUNTANT — Accounting Formulas Reference

**Version:** 1.0  
**Date:** 2026-08-12  
**Purpose:** Complete reference for all financial metrics and formulas in THE ACCOUNTANT calculation engine.

---

## Overview

THE ACCOUNTANT implements 34+ standardized financial metrics organized by category. Every formula is deterministic, versioned, and reproducible. All calculations are pure Python with no LLM integrations.

---

## Profitability Metrics

### Revenue Growth (YoY)

**Metric ID:** `REVENUE_GROWTH`  
**Formula Version:** `REVENUE_GROWTH_V1`  
**Formula:** `(Revenue_Current - Revenue_Prior) / Revenue_Prior × 100`  
**Unit:** `%`

Measures year-over-year revenue growth rate. Requires prior-year context.

**Inputs:**
- Revenue (current period)
- Revenue (prior year)

**Calculation Steps:**
1. Get current year revenue from income statement
2. Get prior year revenue (requires prior_year_context)
3. Calculate percentage change
4. Return as percentage (multiply by 100)

**Status Codes:**
- VALID: Normal calculation
- INSUFFICIENT_DATA: Missing prior year or revenue

---

### Gross Margin

**Metric ID:** `GROSS_MARGIN`  
**Formula Version:** `GROSS_MARGIN_V1`  
**Formula:** `(Gross Profit / Revenue) × 100`  
**Unit:** `%`

Measures production efficiency and pricing power.

**Inputs:**
- Gross Profit (from income statement)
- Revenue (from income statement)

**Calculation Steps:**
1. Retrieve gross profit and revenue from income statement
2. Check both values exist and revenue > ZERO_THRESHOLD
3. Calculate ratio: GP / Revenue
4. Convert to percentage (multiply by 100)

**Status Codes:**
- VALID: Normal calculation
- INSUFFICIENT_DATA: Missing gross profit or revenue
- Warnings: If revenue near zero

---

### Operating Margin

**Metric ID:** `OPERATING_MARGIN`  
**Formula Version:** `OPERATING_MARGIN_V1`  
**Formula:** `(Operating Income / Revenue) × 100`  
**Unit:** `%`

Measures operational efficiency before financing decisions.

**Inputs:**
- Operating Income (from income statement)
- Revenue (from income statement)

**Calculation Steps:**
1. Get operating income and revenue
2. Validate revenue > ZERO_THRESHOLD
3. Calculate: OI / Revenue
4. Convert to percentage

---

### Pretax Margin

**Metric ID:** `PRETAX_MARGIN`  
**Formula Version:** `PRETAX_MARGIN_V1`  
**Formula:** `(Pretax Income / Revenue) × 100`  
**Unit:** `%`

Measures profitability before tax effects.

**Inputs:**
- Pretax Income (from income statement)
- Revenue (from income statement)

---

### Net Margin

**Metric ID:** `NET_MARGIN`  
**Formula Version:** `NET_MARGIN_V1`  
**Formula:** `(Net Income / Revenue) × 100`  
**Unit:** `%`

Measures bottom-line profitability.

**Inputs:**
- Net Income (from income statement)
- Revenue (from income statement)

---

## Cash Flow Metrics

### Free Cash Flow

**Metric ID:** `FCF`  
**Formula Version:** `FCF_V1`  
**Formula:** `Operating Cash Flow - Capital Expenditures`  
**Unit:** `USD`

Measures cash available to all investors after capital reinvestment.

**Inputs:**
- Operating Cash Flow (from cash flow statement)
- Capital Expenditures (from cash flow statement)

**Calculation Steps:**
1. Get OCF and CapEx from cash flow statement
2. Normalize CapEx sign (typically negative in filings; convert to positive)
3. Calculate: OCF - |CapEx|
4. Return as USD value

**Special Cases:**
- CapEx may be reported as negative (most common)
- CapEx may be reported as positive (some jurisdictions)
- Auto-detect sign convention and normalize

---

### FCF Margin

**Metric ID:** `FCF_MARGIN`  
**Formula Version:** `FCF_MARGIN_V1`  
**Formula:** `(FCF / Revenue) × 100`  
**Unit:** `%`

Measures what percentage of revenue converts to free cash.

**Inputs:**
- Free Cash Flow (calculated metric)
- Revenue (from income statement)

---

### CFO Margin

**Metric ID:** `CFO_MARGIN`  
**Formula Version:** `CFO_MARGIN_V1`  
**Formula:** `(Operating Cash Flow / Revenue) × 100`  
**Unit:** `%`

Measures operating cash generation efficiency.

**Inputs:**
- Operating Cash Flow (from cash flow statement)
- Revenue (from income statement)

---

### CFO / NI Ratio

**Metric ID:** `CFO_NI_RATIO`  
**Formula Version:** `CFO_NI_RATIO_V1`  
**Formula:** `Operating Cash Flow / Net Income`  
**Unit:** `ratio`

Quality of earnings metric. Ratio > 1.0 indicates high-quality earnings (more cash than accrual).

**Inputs:**
- Operating Cash Flow (from cash flow statement)
- Net Income (from income statement)

---

### FCF / NI Ratio

**Metric ID:** `FCF_NI_RATIO`  
**Formula Version:** `FCF_NI_RATIO_V1`  
**Formula:** `Free Cash Flow / Net Income`  
**Unit:** `ratio`

Measures cash return on accrual earnings after capital investment.

**Inputs:**
- Free Cash Flow (calculated metric)
- Net Income (from income statement)

---

## Working Capital Metrics

### Working Capital

**Metric ID:** `WORKING_CAPITAL`  
**Formula Version:** `WORKING_CAPITAL_V1`  
**Formula:** `Current Assets - Current Liabilities`  
**Unit:** `USD`

Measures short-term liquidity position.

**Inputs:**
- Current Assets (from balance sheet)
- Current Liabilities (from balance sheet)

---

### Net Working Capital (NWC)

**Metric ID:** `NET_WORKING_CAPITAL`  
**Formula Version:** `NET_WORKING_CAPITAL_V1`  
**Formula:** `(Current Assets - Cash & Investments) - (Current Liabilities - Short-Term Debt)`  
**Unit:** `USD`

Measures operating working capital (excludes financing items).

**Inputs:**
- Current Assets, Cash, Current Liabilities, Short-Term Debt (from balance sheet)

---

### NWC / Revenue

**Metric ID:** `NWC_REVENUE`  
**Formula Version:** `NWC_REVENUE_V1`  
**Formula:** `(NWC / Revenue) × 100`  
**Unit:** `% of Revenue`

Measures working capital efficiency.

**Inputs:**
- Net Working Capital (calculated metric)
- Revenue (from income statement)

---

### Change in NWC

**Metric ID:** `CHANGE_NWC`  
**Formula Version:** `CHANGE_NWC_V1`  
**Formula:** `NWC_Current - NWC_Prior`  
**Unit:** `USD`

Measures working capital investment in the period.

**Inputs:**
- NWC (current period)
- NWC (prior period)

---

## Returns Metrics

### ROA (Return on Assets)

**Metric ID:** `ROA`  
**Formula Version:** `ROA_V1`  
**Formula:** `(Net Income / Average Total Assets) × 100`  
**Unit:** `%`

Measures profit generated per dollar of assets.

**Inputs:**
- Net Income (from income statement)
- Total Assets (beginning and ending from balance sheet)

**Calculation Steps:**
1. Get net income for period
2. Calculate average total assets: (Assets_Beginning + Assets_Ending) / 2
3. Calculate: NI / Avg Assets
4. Convert to percentage

---

### ROE (Return on Equity)

**Metric ID:** `ROE_AVG_EQUITY`  
**Formula Version:** `ROE_AVG_EQUITY_V1`  
**Formula:** `(Net Income / Average Shareholders' Equity) × 100`  
**Unit:** `%`

Measures profit generated per dollar of shareholder capital.

**Inputs:**
- Net Income (from income statement)
- Shareholders' Equity (beginning and ending from balance sheet)

**Calculation Steps:**
1. Get net income
2. Get beginning and ending equity
3. Calculate average equity: (Equity_Beginning + Equity_Ending) / 2
4. Calculate: NI / Avg Equity
5. Convert to percentage

**Note:** When prior-year balance sheet unavailable, falls back to period-end equity with warning.

---

## ROIC Framework

See [roic.md](roic.md) for complete ROIC methodology including:
- NOPAT (Net Operating Profit After Tax)
- Invested Capital (two methods)
- ROIC calculation
- Incremental ROIC over rolling windows

---

## Leverage Metrics

### Debt-to-Equity

**Metric ID:** `DEBT_TO_EQUITY`  
**Formula Version:** `DEBT_TO_EQUITY_V1`  
**Formula:** `Total Debt / Shareholders' Equity`  
**Unit:** `ratio`

Measures financial leverage.

**Total Debt = Short-Term Debt + Current Portion LT Debt + Long-Term Debt + Lease Liabilities**

---

### Net Debt-to-Equity

**Metric ID:** `NET_DEBT_TO_EQUITY`  
**Formula Version:** `NET_DEBT_TO_EQUITY_V1`  
**Formula:** `(Total Debt - Cash & Investments) / Shareholders' Equity`  
**Unit:** `ratio`

Measures net financial leverage (adjusting for cash position).

---

### Interest Coverage

**Metric ID:** `INTEREST_COVERAGE`  
**Formula Version:** `INTEREST_COVERAGE_V1`  
**Formula:** `Operating Income / Interest Expense`  
**Unit:** `ratio`

Measures ability to service debt obligations.

**Status Codes:**
- VALID: Normal calculation
- INSUFFICIENT_DATA: Missing operating income or interest expense
- Warnings: Interest expense near zero

---

### Goodwill / Assets

**Metric ID:** `GOODWILL_RATIO`  
**Formula Version:** `GOODWILL_RATIO_V1`  
**Formula:** `Goodwill / Total Assets`  
**Unit:** `%`

Measures proportion of intangible assets from acquisitions.

---

### Cash / Assets

**Metric ID:** `CASH_RATIO`  
**Formula Version:** `CASH_RATIO_V1`  
**Formula:** `(Cash & Equivalents + Short-Term Investments) / Total Assets`  
**Unit:** `%`

Measures liquidity position.

---

## Quality Metrics

### Accrual Ratio

**Metric ID:** `ACCRUAL_RATIO`  
**Formula Version:** `ACCRUAL_RATIO_V1`  
**Formula:** `(Change in NWC + D&A - CapEx) / Average Total Assets`  
**Unit:** `%`

Measures accrual intensity. Higher ratio indicates lower earnings quality.

**Interpretation:**
- < 0: Negative accruals (high quality)
- 0-5%: Moderate accruals (normal)
- > 5%: High accruals (lower quality)

**Inputs:**
- Change in Net Working Capital
- Depreciation & Amortization
- Capital Expenditures
- Average Total Assets

---

## Version Control

Every metric has a `formula_version` identifier (e.g., ROIC_V1). This enables:

1. **Reproducibility:** Same version always produces same result
2. **Comparisons:** Can analyze using multiple versions if definitions change
3. **Backwards Compatibility:** Old versions remain callable
4. **Audit Trail:** Every calculation records which version was used

### Version Numbering

- **V1:** Initial production version (2026-08-12)
- **V2+:** Reserved for future enhancements or corrections

---

## Calculation Constants

### ZERO_THRESHOLD
**Value:** 1.0 USD  
**Purpose:** Minimum denominator value to avoid divide-by-zero on trivial values  
**Applied To:** All ratios and margin calculations  
**Behavior:** If denominator < threshold, calculation returns INSUFFICIENT_DATA status

### MAX_REASONABLE_RATIO
**Value:** 1000.0  
**Purpose:** Sanity check for ratio calculations  
**Applied To:** All metric ratios  
**Behavior:** Ratios exceeding this value trigger warnings (may indicate data quality issues)

---

## Input Hierarchy

When calculating a metric, THE ACCOUNTANT uses this priority:

1. **Explicit Override:** User-provided value (tax_rate_override, etc.)
2. **Reported Value:** Direct from financial statements
3. **Calculated Value:** Derived from component metrics
4. **Inferred Value:** Best guess with fallback rules (e.g., 21% tax rate)
5. **Missing:** Return status = INSUFFICIENT_DATA

---

## Audit Trail

Every calculation includes:

- **formula:** Human-readable formula text
- **inputs:** Dict of all input values used
- **formula_version:** Which version was used
- **calculation_status:** Success/failure indicator
- **warnings:** List of decision points and assumptions
- **metadata:** Extended results (e.g., beginning/ending/average IC for ROIC)
- **source_statement_snapshot_ids:** Which statements were used
- **source_statement_line_ids:** Which line items were used
- **source_canonical_fact_ids:** Which facts were used
- **calculated_at:** Timestamp of calculation

This enables complete reproduction: given the same inputs and formula version, you can recreate any calculation.

---

## Error Handling

Calculations use structured status codes rather than exceptions:

- **VALID:** Normal result
- **INSUFFICIENT_DATA:** Missing required inputs
- **UNSTABLE_DENOMINATOR:** Divisor too close to zero
- **NEGATIVE_INCREMENTAL_CAPITAL:** Capital reduction (special case)
- **CONFLICT:** Multiple conflicting data sources

All edge cases are logged in `warnings` field for audit review.

---

## Future Enhancements

**Deferred to Prompt 8+:**
- Economic depreciation adjustments
- Normalized earnings adjustments
- Owner Earnings formula
- Tax normalization options
- Multi-year CAGR calculations
- Segment-specific metrics
- Currency conversion adjustments

---

*For implementation details, see [roic.md](roic.md) and [incremental_roic.md](incremental_roic.md).*
