"""Canonical mapping rules for XBRL concepts to canonical accounting concepts.

This module contains deterministic mapping rules that map raw XBRL concepts
to standardized canonical concepts. Rules are versioned and support
priority-based conflict resolution.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MappingRuleDefinition:
    """Definition of a mapping rule from raw XBRL to canonical concept."""

    taxonomy: str
    source_concept: str
    canonical_concept_code: str
    priority: int = 100
    confidence: str = "HIGH"
    rationale: str = ""
    industry_applicability: str | None = None
    mapping_version: int = 1


# Comprehensive US-GAAP to Canonical Mappings
# Organized by financial statement section
# Priority: Higher number = higher priority (100 is default/normal)
# Confidence: HIGH = definitive, MEDIUM = probable, LOW = speculative

CANONICAL_MAPPINGS = [
    # ========== INCOME STATEMENT ==========
    # Revenue
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="Revenues",
        canonical_concept_code="CC_REVENUE",
        priority=100,
        confidence="HIGH",
        rationale="Standard US-GAAP revenue concept",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="RevenuesNet",
        canonical_concept_code="CC_REVENUE",
        priority=100,
        confidence="HIGH",
        rationale="Net revenue after returns and allowances",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="ProductRevenues",
        canonical_concept_code="CC_REVENUE",
        priority=95,
        confidence="HIGH",
        rationale="Product revenue (part of total)",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="ServiceRevenues",
        canonical_concept_code="CC_REVENUE",
        priority=95,
        confidence="HIGH",
        rationale="Service revenue (part of total)",
    ),
    # Cost of Revenue
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="CostOfRevenues",
        canonical_concept_code="CC_COST_OF_REVENUE",
        priority=100,
        confidence="HIGH",
        rationale="Cost of goods/services sold",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="CostOfGoodsAndServicesSold",
        canonical_concept_code="CC_COST_OF_REVENUE",
        priority=100,
        confidence="HIGH",
        rationale="COGS/service costs",
    ),
    # Gross Profit
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="GrossProfit",
        canonical_concept_code="CC_GROSS_PROFIT",
        priority=100,
        confidence="HIGH",
        rationale="Revenue minus cost of revenue",
    ),
    # Operating Expenses
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="OperatingExpenses",
        canonical_concept_code="CC_OPERATING_EXPENSES",
        priority=100,
        confidence="HIGH",
        rationale="Total operating expenses",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="ResearchAndDevelopmentExpense",
        canonical_concept_code="CC_RD_EXPENSE",
        priority=100,
        confidence="HIGH",
        rationale="R&D expense",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="SellingGeneralAndAdministrativeExpense",
        canonical_concept_code="CC_SGA_EXPENSE",
        priority=100,
        confidence="HIGH",
        rationale="SG&A expense",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="GeneralAndAdministrativeExpense",
        canonical_concept_code="CC_SGA_EXPENSE",
        priority=95,
        confidence="HIGH",
        rationale="G&A expense (component of SG&A)",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="SellingExpense",
        canonical_concept_code="CC_SGA_EXPENSE",
        priority=90,
        confidence="MEDIUM",
        rationale="Selling expense (component of SG&A)",
    ),
    # Operating Income
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="OperatingIncomeLoss",
        canonical_concept_code="CC_OPERATING_INCOME",
        priority=100,
        confidence="HIGH",
        rationale="Income from operations",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="IncomeFromOperations",
        canonical_concept_code="CC_OPERATING_INCOME",
        priority=100,
        confidence="HIGH",
        rationale="Operating income",
    ),
    # Interest Expense
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="InterestExpense",
        canonical_concept_code="CC_INTEREST_EXPENSE",
        priority=100,
        confidence="HIGH",
        rationale="Interest expense on debt",
    ),
    # Income Tax
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="IncomeTaxExpenseBenefit",
        canonical_concept_code="CC_INCOME_TAX_EXPENSE",
        priority=100,
        confidence="HIGH",
        rationale="Income tax expense",
    ),
    # Net Income
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="NetIncomeLoss",
        canonical_concept_code="CC_NET_INCOME",
        priority=100,
        confidence="HIGH",
        rationale="Net income/loss for period",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="NetIncome",
        canonical_concept_code="CC_NET_INCOME",
        priority=100,
        confidence="HIGH",
        rationale="Net income",
    ),
    # ========== BALANCE SHEET - ASSETS ==========
    # Total Assets
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="Assets",
        canonical_concept_code="CC_ASSETS",
        priority=100,
        confidence="HIGH",
        rationale="Total assets",
    ),
    # Current Assets
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="AssetsCurrent",
        canonical_concept_code="CC_CURRENT_ASSETS",
        priority=100,
        confidence="HIGH",
        rationale="Current assets",
    ),
    # Cash
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="Cash",
        canonical_concept_code="CC_CASH",
        priority=100,
        confidence="HIGH",
        rationale="Cash and cash equivalents",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="CashAndCashEquivalentsAtCarryingValue",
        canonical_concept_code="CC_CASH",
        priority=100,
        confidence="HIGH",
        rationale="Cash at carrying value",
    ),
    # Short-term Investments
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="MarketableSecuritiesCurrent",
        canonical_concept_code="CC_SHORT_TERM_INVESTMENTS",
        priority=100,
        confidence="HIGH",
        rationale="Marketable securities current",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="AvailableForSaleSecuritiesCurrent",
        canonical_concept_code="CC_SHORT_TERM_INVESTMENTS",
        priority=100,
        confidence="HIGH",
        rationale="AFS securities current",
    ),
    # Accounts Receivable
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="AccountsReceivableNetCurrent",
        canonical_concept_code="CC_ACCOUNTS_RECEIVABLE",
        priority=100,
        confidence="HIGH",
        rationale="AR net of allowance",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="AccountsReceivableGrossCurrent",
        canonical_concept_code="CC_ACCOUNTS_RECEIVABLE",
        priority=95,
        confidence="HIGH",
        rationale="AR gross (use net when available)",
    ),
    # Inventory
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="InventoryNet",
        canonical_concept_code="CC_INVENTORY",
        priority=100,
        confidence="HIGH",
        rationale="Inventory net of valuation",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="Inventories",
        canonical_concept_code="CC_INVENTORY",
        priority=100,
        confidence="HIGH",
        rationale="Total inventories",
    ),
    # Property, Plant, Equipment
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="PropertyPlantAndEquipmentNet",
        canonical_concept_code="CC_PPE",
        priority=100,
        confidence="HIGH",
        rationale="PP&E net of depreciation",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="PropertyPlantAndEquipmentGross",
        canonical_concept_code="CC_PPE",
        priority=95,
        confidence="HIGH",
        rationale="PP&E gross (use net when available)",
    ),
    # Accumulated Depreciation
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
        canonical_concept_code="CC_ACCUMULATED_DEPRECIATION",
        priority=100,
        confidence="HIGH",
        rationale="Accumulated depreciation",
    ),
    # Intangible Assets
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="IntangibleAssetsNetExcludingGoodwill",
        canonical_concept_code="CC_INTANGIBLE_ASSETS",
        priority=100,
        confidence="HIGH",
        rationale="Intangible assets excluding goodwill",
    ),
    # Goodwill
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="Goodwill",
        canonical_concept_code="CC_GOODWILL",
        priority=100,
        confidence="HIGH",
        rationale="Goodwill from acquisitions",
    ),
    # ========== BALANCE SHEET - LIABILITIES ==========
    # Total Liabilities
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="Liabilities",
        canonical_concept_code="CC_LIABILITIES",
        priority=100,
        confidence="HIGH",
        rationale="Total liabilities",
    ),
    # Current Liabilities
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="LiabilitiesCurrent",
        canonical_concept_code="CC_CURRENT_LIABILITIES",
        priority=100,
        confidence="HIGH",
        rationale="Current liabilities",
    ),
    # Accounts Payable
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="AccountsPayableCurrent",
        canonical_concept_code="CC_ACCOUNTS_PAYABLE",
        priority=100,
        confidence="HIGH",
        rationale="Accounts payable current",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="AccountsPayable",
        canonical_concept_code="CC_ACCOUNTS_PAYABLE",
        priority=100,
        confidence="HIGH",
        rationale="Accounts payable",
    ),
    # Short-term Debt
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="DebtCurrent",
        canonical_concept_code="CC_SHORT_TERM_DEBT",
        priority=100,
        confidence="HIGH",
        rationale="Debt due within one year",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="ShortTermDebt",
        canonical_concept_code="CC_SHORT_TERM_DEBT",
        priority=100,
        confidence="HIGH",
        rationale="Short-term borrowings",
    ),
    # Long-term Debt
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="DebtNoncurrent",
        canonical_concept_code="CC_LONG_TERM_DEBT",
        priority=100,
        confidence="HIGH",
        rationale="Debt due after one year",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="LongTermDebt",
        canonical_concept_code="CC_LONG_TERM_DEBT",
        priority=100,
        confidence="HIGH",
        rationale="Long-term borrowings",
    ),
    # Lease Liabilities
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="OperatingLeaseLiability",
        canonical_concept_code="CC_LEASE_LIABILITIES",
        priority=100,
        confidence="HIGH",
        rationale="Operating lease liability (ASC 842)",
    ),
    # ========== BALANCE SHEET - EQUITY ==========
    # Total Shareholders Equity
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="StockholdersEquity",
        canonical_concept_code="CC_SHAREHOLDERS_EQUITY",
        priority=100,
        confidence="HIGH",
        rationale="Total shareholders equity",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="Equity",
        canonical_concept_code="CC_SHAREHOLDERS_EQUITY",
        priority=95,
        confidence="HIGH",
        rationale="Total equity",
    ),
    # Common Stock
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="CommonStockValue",
        canonical_concept_code="CC_COMMON_STOCK",
        priority=100,
        confidence="HIGH",
        rationale="Common stock at par value",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="CommonStock",
        canonical_concept_code="CC_COMMON_STOCK",
        priority=100,
        confidence="HIGH",
        rationale="Common stock",
    ),
    # Retained Earnings
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="RetainedEarningsAccumulatedDeficit",
        canonical_concept_code="CC_RETAINED_EARNINGS",
        priority=100,
        confidence="HIGH",
        rationale="Accumulated retained earnings",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="RetainedEarnings",
        canonical_concept_code="CC_RETAINED_EARNINGS",
        priority=100,
        confidence="HIGH",
        rationale="Retained earnings",
    ),
    # ========== CASH FLOW STATEMENT ==========
    # Operating Cash Flow
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="NetCashProvidedByUsedInOperatingActivities",
        canonical_concept_code="CC_OPERATING_CASH_FLOW",
        priority=100,
        confidence="HIGH",
        rationale="Cash from operations",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="OperatingCashFlow",
        canonical_concept_code="CC_OPERATING_CASH_FLOW",
        priority=100,
        confidence="HIGH",
        rationale="Operating cash flow",
    ),
    # Investing Cash Flow
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="NetCashProvidedByUsedInInvestingActivities",
        canonical_concept_code="CC_INVESTING_CASH_FLOW",
        priority=100,
        confidence="HIGH",
        rationale="Cash from/for investing",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="InvestingCashFlow",
        canonical_concept_code="CC_INVESTING_CASH_FLOW",
        priority=100,
        confidence="HIGH",
        rationale="Investing cash flow",
    ),
    # Financing Cash Flow
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="NetCashProvidedByUsedInFinancingActivities",
        canonical_concept_code="CC_FINANCING_CASH_FLOW",
        priority=100,
        confidence="HIGH",
        rationale="Cash from/for financing",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="FinancingCashFlow",
        canonical_concept_code="CC_FINANCING_CASH_FLOW",
        priority=100,
        confidence="HIGH",
        rationale="Financing cash flow",
    ),
    # Capital Expenditures
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="PaymentsToAcquirePropertyPlantAndEquipment",
        canonical_concept_code="CC_CAPITAL_EXPENDITURES",
        priority=100,
        confidence="HIGH",
        rationale="Cash paid for PP&E",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="CapitalExpenditures",
        canonical_concept_code="CC_CAPITAL_EXPENDITURES",
        priority=100,
        confidence="HIGH",
        rationale="Capital expenditures",
    ),
    # Depreciation & Amortization
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="DepreciationDepletionAndAmortization",
        canonical_concept_code="CC_DEPRECIATION_AMORTIZATION",
        priority=100,
        confidence="HIGH",
        rationale="D&A non-cash expense",
    ),
    # Stock-Based Compensation
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="StockBasedCompensation",
        canonical_concept_code="CC_STOCK_BASED_COMPENSATION",
        priority=100,
        confidence="HIGH",
        rationale="SBC non-cash expense",
    ),
    # Dividends Paid
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="PaymentOfDividends",
        canonical_concept_code="CC_DIVIDENDS",
        priority=100,
        confidence="HIGH",
        rationale="Cash dividends paid",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="DividendsPaidCommonStockCash",
        canonical_concept_code="CC_DIVIDENDS",
        priority=100,
        confidence="HIGH",
        rationale="Common stock dividends",
    ),
    # Share Repurchases
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="PaymentForRepurchaseOfCommonStock",
        canonical_concept_code="CC_SHARE_REPURCHASES",
        priority=100,
        confidence="HIGH",
        rationale="Share buyback cash",
    ),
    # ========== SHARES & METRICS ==========
    # Shares Outstanding
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="CommonStockSharesOutstanding",
        canonical_concept_code="CC_SHARES_OUTSTANDING",
        priority=100,
        confidence="HIGH",
        rationale="Common shares outstanding",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="WeightedAverageNumberOfSharesOutstandingBasic",
        canonical_concept_code="CC_WEIGHTED_SHARES_BASIC",
        priority=100,
        confidence="HIGH",
        rationale="Weighted average shares basic",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="WeightedAverageNumberOfSharesOutstandingDiluted",
        canonical_concept_code="CC_WEIGHTED_SHARES_DILUTED",
        priority=100,
        confidence="HIGH",
        rationale="Weighted average shares diluted",
    ),
    # EPS
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="EarningsPerShareBasic",
        canonical_concept_code="CC_EPS",
        priority=100,
        confidence="HIGH",
        rationale="Basic earnings per share",
    ),
    MappingRuleDefinition(
        taxonomy="us-gaap",
        source_concept="EarningsPerShareDiluted",
        canonical_concept_code="CC_EPS_DILUTED",
        priority=100,
        confidence="HIGH",
        rationale="Diluted earnings per share",
    ),
]


def get_mapping_rules(
    mapping_version: int = 1, industry: str | None = None
) -> list[MappingRuleDefinition]:
    """Get mapping rules, optionally filtered by version and industry.

    Args:
        mapping_version: Version of mapping rules (default: latest)
        industry: Optional industry code for industry-specific rules

    Returns:
        List of MappingRuleDefinition objects
    """
    rules = [r for r in CANONICAL_MAPPINGS if r.mapping_version == mapping_version]

    if industry:
        # Include both industry-specific and general rules
        general_rules = [r for r in rules if r.industry_applicability is None]
        industry_rules = [r for r in rules if r.industry_applicability == industry]
        rules = industry_rules + general_rules

    return rules


def get_mapping_rule(
    taxonomy: str,
    source_concept: str,
    mapping_version: int = 1,
    industry: str | None = None,
) -> MappingRuleDefinition | None:
    """Get a single mapping rule for a taxonomy/concept pair.

    Args:
        taxonomy: Taxonomy name
        source_concept: Source concept name
        mapping_version: Version of mapping rules
        industry: Optional industry code

    Returns:
        MappingRuleDefinition or None if not found
    """
    rules = get_mapping_rules(mapping_version, industry)
    matches = [
        r
        for r in rules
        if r.taxonomy.lower() == taxonomy.lower()
        and r.source_concept == source_concept
    ]

    if not matches:
        return None

    # Sort by priority (highest first), then confidence level
    confidence_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    matches.sort(
        key=lambda r: (
            -r.priority,
            -confidence_rank.get(r.confidence, 0),
        )
    )

    return matches[0]


def find_mapping_candidates(
    taxonomy: str,
    source_concept: str,
    mapping_version: int = 1,
    industry: str | None = None,
) -> list[MappingRuleDefinition]:
    """Find all candidate mappings for a taxonomy/concept pair.

    Args:
        taxonomy: Taxonomy name
        source_concept: Source concept name
        mapping_version: Version of mapping rules
        industry: Optional industry code

    Returns:
        List of MappingRuleDefinition objects sorted by priority/confidence
    """
    rules = get_mapping_rules(mapping_version, industry)
    matches = [
        r
        for r in rules
        if r.taxonomy.lower() == taxonomy.lower()
        and r.source_concept == source_concept
    ]

    confidence_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    matches.sort(
        key=lambda r: (
            -r.priority,
            -confidence_rank.get(r.confidence, 0),
        )
    )

    return matches


__all__ = [
    "MappingRuleDefinition",
    "get_mapping_rules",
    "get_mapping_rule",
    "find_mapping_candidates",
]
