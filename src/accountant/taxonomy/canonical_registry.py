"""Case Capital canonical accounting taxonomy registry.

Defines 40+ standardized accounting concepts mapping XBRL taxonomies
to canonical concepts with versioned rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class CanonicalConceptDef:
    """Definition of a canonical accounting concept."""

    code: str
    label: str
    description: str
    category: str
    unit_hint: str | None = None
    version: int = 1


class CanonicalRegistry:
    """Registry of Case Capital canonical concepts.

    Manages ~40+ standardized accounting concepts and their mappings
    from SEC XBRL taxonomies (us-gaap, ifrs-full, etc.).
    """

    def __init__(self):
        """Initialize registry with canonical concepts."""
        self._concepts = self._build_concepts()

    @staticmethod
    def _build_concepts() -> dict[str, CanonicalConceptDef]:
        """Build map of canonical concept code → definition."""
        return {
            # Balance Sheet — Assets
            "CC_ASSETS": CanonicalConceptDef(
                code="CC_ASSETS",
                label="Total Assets",
                description="Total assets as of balance sheet date",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_CURRENT_ASSETS": CanonicalConceptDef(
                code="CC_CURRENT_ASSETS",
                label="Current Assets",
                description="Assets expected to be realized within one year",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_CASH": CanonicalConceptDef(
                code="CC_CASH",
                label="Cash and Cash Equivalents",
                description="Cash and short-term investments readily convertible to cash",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_SHORT_TERM_INVESTMENTS": CanonicalConceptDef(
                code="CC_SHORT_TERM_INVESTMENTS",
                label="Short-term Investments",
                description="Liquid investments expected to convert to cash within one year",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_ACCOUNTS_RECEIVABLE": CanonicalConceptDef(
                code="CC_ACCOUNTS_RECEIVABLE",
                label="Accounts Receivable",
                description="Amounts due from customers",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_INVENTORY": CanonicalConceptDef(
                code="CC_INVENTORY",
                label="Inventory",
                description="Goods available for sale",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_PPE": CanonicalConceptDef(
                code="CC_PPE",
                label="Property, Plant & Equipment",
                description="Tangible long-lived assets",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_ACCUMULATED_DEPRECIATION": CanonicalConceptDef(
                code="CC_ACCUMULATED_DEPRECIATION",
                label="Accumulated Depreciation",
                description="Cumulative depreciation on PP&E",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_INTANGIBLE_ASSETS": CanonicalConceptDef(
                code="CC_INTANGIBLE_ASSETS",
                label="Intangible Assets",
                description="Goodwill and other intangible assets",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_GOODWILL": CanonicalConceptDef(
                code="CC_GOODWILL",
                label="Goodwill",
                description="Acquisition goodwill carried on the balance sheet",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            # Balance Sheet — Liabilities
            "CC_LIABILITIES": CanonicalConceptDef(
                code="CC_LIABILITIES",
                label="Total Liabilities",
                description="Total obligations as of balance sheet date",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_CURRENT_LIABILITIES": CanonicalConceptDef(
                code="CC_CURRENT_LIABILITIES",
                label="Current Liabilities",
                description="Obligations due within one year",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_ACCOUNTS_PAYABLE": CanonicalConceptDef(
                code="CC_ACCOUNTS_PAYABLE",
                label="Accounts Payable",
                description="Amounts owed to suppliers",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_SHORT_TERM_DEBT": CanonicalConceptDef(
                code="CC_SHORT_TERM_DEBT",
                label="Short-term Debt",
                description="Debt obligations due within one year",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_LONG_TERM_DEBT": CanonicalConceptDef(
                code="CC_LONG_TERM_DEBT",
                label="Long-term Debt",
                description="Debt obligations due after one year",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_LEASE_LIABILITIES": CanonicalConceptDef(
                code="CC_LEASE_LIABILITIES",
                label="Lease Liabilities",
                description="Operating and finance lease obligations",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            # Balance Sheet — Equity
            "CC_SHAREHOLDERS_EQUITY": CanonicalConceptDef(
                code="CC_SHAREHOLDERS_EQUITY",
                label="Total Shareholders' Equity",
                description="Residual interest in assets after liabilities",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_COMMON_STOCK": CanonicalConceptDef(
                code="CC_COMMON_STOCK",
                label="Common Stock",
                description="Par or stated value of issued common stock",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            "CC_RETAINED_EARNINGS": CanonicalConceptDef(
                code="CC_RETAINED_EARNINGS",
                label="Retained Earnings",
                description="Accumulated net income not distributed as dividends",
                category="Balance Sheet",
                unit_hint="USD",
                version=1,
            ),
            # Income Statement
            "CC_REVENUE": CanonicalConceptDef(
                code="CC_REVENUE",
                label="Net Revenue",
                description="Total revenue from operations",
                category="Income Statement",
                unit_hint="USD",
                version=1,
            ),
            "CC_COST_OF_REVENUE": CanonicalConceptDef(
                code="CC_COST_OF_REVENUE",
                label="Cost of Revenue",
                description="Direct costs of goods/services sold",
                category="Income Statement",
                unit_hint="USD",
                version=1,
            ),
            "CC_GROSS_PROFIT": CanonicalConceptDef(
                code="CC_GROSS_PROFIT",
                label="Gross Profit",
                description="Revenue minus cost of revenue",
                category="Income Statement",
                unit_hint="USD",
                version=1,
            ),
            "CC_OPERATING_EXPENSES": CanonicalConceptDef(
                code="CC_OPERATING_EXPENSES",
                label="Operating Expenses",
                description="SG&A and other operating costs",
                category="Income Statement",
                unit_hint="USD",
                version=1,
            ),
            "CC_RD_EXPENSE": CanonicalConceptDef(
                code="CC_RD_EXPENSE",
                label="Research & Development",
                description="Costs for R&D activities",
                category="Income Statement",
                unit_hint="USD",
                version=1,
            ),
            "CC_SGA_EXPENSE": CanonicalConceptDef(
                code="CC_SGA_EXPENSE",
                label="Selling, General & Administrative",
                description="SG&A expenses",
                category="Income Statement",
                unit_hint="USD",
                version=1,
            ),
            "CC_OPERATING_INCOME": CanonicalConceptDef(
                code="CC_OPERATING_INCOME",
                label="Operating Income",
                description="Income from core business operations",
                category="Income Statement",
                unit_hint="USD",
                version=1,
            ),
            "CC_INTEREST_EXPENSE": CanonicalConceptDef(
                code="CC_INTEREST_EXPENSE",
                label="Interest Expense",
                description="Cost of borrowing",
                category="Income Statement",
                unit_hint="USD",
                version=1,
            ),
            "CC_INCOME_TAX_EXPENSE": CanonicalConceptDef(
                code="CC_INCOME_TAX_EXPENSE",
                label="Income Tax Expense",
                description="Provision for income taxes",
                category="Income Statement",
                unit_hint="USD",
                version=1,
            ),
            "CC_NET_INCOME": CanonicalConceptDef(
                code="CC_NET_INCOME",
                label="Net Income",
                description="Bottom-line profit after all expenses and taxes",
                category="Income Statement",
                unit_hint="USD",
                version=1,
            ),
            # Cash Flow Statement
            "CC_OPERATING_CASH_FLOW": CanonicalConceptDef(
                code="CC_OPERATING_CASH_FLOW",
                label="Operating Cash Flow",
                description="Cash generated by operations",
                category="Cash Flow",
                unit_hint="USD",
                version=1,
            ),
            "CC_INVESTING_CASH_FLOW": CanonicalConceptDef(
                code="CC_INVESTING_CASH_FLOW",
                label="Investing Cash Flow",
                description="Cash used in investing activities",
                category="Cash Flow",
                unit_hint="USD",
                version=1,
            ),
            "CC_FINANCING_CASH_FLOW": CanonicalConceptDef(
                code="CC_FINANCING_CASH_FLOW",
                label="Financing Cash Flow",
                description="Cash from financing activities",
                category="Cash Flow",
                unit_hint="USD",
                version=1,
            ),
            "CC_CAPITAL_EXPENDITURES": CanonicalConceptDef(
                code="CC_CAPITAL_EXPENDITURES",
                label="Capital Expenditures",
                description="Cash spent on PP&E and acquisitions",
                category="Cash Flow",
                unit_hint="USD",
                version=1,
            ),
            "CC_DEPRECIATION_AMORTIZATION": CanonicalConceptDef(
                code="CC_DEPRECIATION_AMORTIZATION",
                label="Depreciation and Amortization",
                description="Non-cash depreciation, depletion, and amortization expense",
                category="Cash Flow",
                unit_hint="USD",
                version=1,
            ),
            "CC_STOCK_BASED_COMPENSATION": CanonicalConceptDef(
                code="CC_STOCK_BASED_COMPENSATION",
                label="Stock-based Compensation",
                description="Equity compensation expense recognized in the period",
                category="Cash Flow",
                unit_hint="USD",
                version=1,
            ),
            "CC_DIVIDENDS": CanonicalConceptDef(
                code="CC_DIVIDENDS",
                label="Dividends",
                description="Cash dividends paid to shareholders",
                category="Cash Flow",
                unit_hint="USD",
                version=1,
            ),
            "CC_SHARE_REPURCHASES": CanonicalConceptDef(
                code="CC_SHARE_REPURCHASES",
                label="Share Repurchases",
                description="Cash used to repurchase common shares",
                category="Cash Flow",
                unit_hint="USD",
                version=1,
            ),
            # Metrics
            "CC_SHARES_OUTSTANDING": CanonicalConceptDef(
                code="CC_SHARES_OUTSTANDING",
                label="Shares Outstanding",
                description="Number of common shares issued",
                category="Metrics",
                unit_hint="Shares",
                version=1,
            ),
            "CC_WEIGHTED_SHARES_BASIC": CanonicalConceptDef(
                code="CC_WEIGHTED_SHARES_BASIC",
                label="Weighted Average Shares Basic",
                description="Weighted average basic shares outstanding during the period",
                category="Metrics",
                unit_hint="Shares",
                version=1,
            ),
            "CC_WEIGHTED_SHARES_DILUTED": CanonicalConceptDef(
                code="CC_WEIGHTED_SHARES_DILUTED",
                label="Weighted Average Shares Diluted",
                description="Weighted average diluted shares outstanding during the period",
                category="Metrics",
                unit_hint="Shares",
                version=1,
            ),
            "CC_EPS": CanonicalConceptDef(
                code="CC_EPS",
                label="Earnings Per Share",
                description="Net income per share",
                category="Metrics",
                unit_hint="USD",
                version=1,
            ),
            "CC_EPS_DILUTED": CanonicalConceptDef(
                code="CC_EPS_DILUTED",
                label="Diluted Earnings Per Share",
                description="Diluted net income per share",
                category="Metrics",
                unit_hint="USD",
                version=1,
            ),
            "CC_BOOK_VALUE_PER_SHARE": CanonicalConceptDef(
                code="CC_BOOK_VALUE_PER_SHARE",
                label="Book Value Per Share",
                description="Equity per share",
                category="Metrics",
                unit_hint="USD",
                version=1,
            ),
            "CC_DEBT_TO_EQUITY": CanonicalConceptDef(
                code="CC_DEBT_TO_EQUITY",
                label="Debt-to-Equity Ratio",
                description="Total debt divided by total equity",
                category="Metrics",
                unit_hint=None,
                version=1,
            ),
            "CC_CURRENT_RATIO": CanonicalConceptDef(
                code="CC_CURRENT_RATIO",
                label="Current Ratio",
                description="Current assets divided by current liabilities",
                category="Metrics",
                unit_hint=None,
                version=1,
            ),
            "CC_QUICK_RATIO": CanonicalConceptDef(
                code="CC_QUICK_RATIO",
                label="Quick Ratio",
                description="(Current assets - inventory) / current liabilities",
                category="Metrics",
                unit_hint=None,
                version=1,
            ),
            "CC_ROE": CanonicalConceptDef(
                code="CC_ROE",
                label="Return on Equity",
                description="Net income divided by average shareholders' equity",
                category="Metrics",
                unit_hint=None,
                version=1,
            ),
            "CC_ROA": CanonicalConceptDef(
                code="CC_ROA",
                label="Return on Assets",
                description="Net income divided by average total assets",
                category="Metrics",
                unit_hint=None,
                version=1,
            ),
            "CC_PROFIT_MARGIN": CanonicalConceptDef(
                code="CC_PROFIT_MARGIN",
                label="Net Profit Margin",
                description="Net income divided by revenue",
                category="Metrics",
                unit_hint=None,
                version=1,
            ),
            "CC_ASSET_TURNOVER": CanonicalConceptDef(
                code="CC_ASSET_TURNOVER",
                label="Asset Turnover",
                description="Revenue divided by average total assets",
                category="Metrics",
                unit_hint=None,
                version=1,
            ),
        }

    def get_concept(self, code: str) -> CanonicalConceptDef | None:
        """Retrieve canonical concept by code.

        Args:
            code: Concept code (e.g., "CC_REVENUE")

        Returns:
            CanonicalConceptDef or None if not found
        """
        return self._concepts.get(code)

    def list_concepts(self, category: str | None = None) -> list[CanonicalConceptDef]:
        """List all canonical concepts, optionally filtered by category.

        Args:
            category: Optional category to filter (e.g., "Balance Sheet")

        Returns:
            List of CanonicalConceptDef
        """
        if category is None:
            return list(self._concepts.values())
        return [c for c in self._concepts.values() if c.category == category]

    def categories(self) -> set[str]:
        """Get all unique categories.

        Returns:
            Set of category names
        """
        return {c.category for c in self._concepts.values()}

    def count(self) -> int:
        """Get total number of canonical concepts.

        Returns:
            Count of concepts in registry
        """
        return len(self._concepts)


# Global singleton instance
_registry: CanonicalRegistry | None = None


def get_canonical_registry() -> CanonicalRegistry:
    """Get global canonical registry instance."""
    global _registry
    if _registry is None:
        _registry = CanonicalRegistry()
    return _registry


__all__ = ["CanonicalConceptDef", "CanonicalRegistry", "get_canonical_registry"]
