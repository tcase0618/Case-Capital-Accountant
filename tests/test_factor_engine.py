from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from accountant.db.models import RawFact
from accountant.research.factor_engine import build_accounting_factor_pack


def _fact(
    concept: str,
    value: float,
    *,
    fiscal_year: int,
    period_end: date,
    fiscal_period: str = "FY",
) -> RawFact:
    return RawFact(
        id=uuid.uuid4(),
        filing_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        concept=concept,
        taxonomy="us-gaap",
        unit="USD",
        period_end=period_end,
        value_numeric=Decimal(str(value)),
        fact_hash=f"{concept}-{fiscal_year}-{value}",
        accession_number=f"{fiscal_year}-000001",
        form="10-K",
        filed_date=date(fiscal_year + 1, 2, 20) if fiscal_year < 2026 else date(2026, 2, 20),
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        source_type="companyfacts",
    )


def test_build_accounting_factor_pack_computes_expected_core_factors() -> None:
    facts = [
        _fact("RevenueFromContractWithCustomerExcludingAssessedTax", 1000, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("AccountsReceivableNetCurrent", 100, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("CostOfGoodsSold", 600, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("AssetsCurrent", 500, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("PropertyPlantAndEquipmentNet", 400, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("ShortTermInvestments", 50, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("Assets", 1200, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("DepreciationAndAmortization", 80, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("SellingGeneralAndAdministrativeExpense", 150, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("LiabilitiesCurrent", 300, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("LongTermDebtNoncurrent", 200, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("NetIncomeLoss", 90, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("NetCashProvidedByUsedInOperatingActivities", 110, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("InventoryNet", 100, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("PrepaidExpenseCurrent", 20, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("DeferredRevenueCurrent", 40, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("AccountsPayableCurrent", 70, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("AccruedLiabilitiesCurrent", 50, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("RetainedEarningsAccumulatedDeficit", 250, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("OperatingIncomeLoss", 120, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("StockholdersEquity", 700, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("Liabilities", 500, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("WeightedAverageNumberOfDilutedSharesOutstanding", 100, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("CashAndCashEquivalentsAtCarryingValue", 180, fiscal_year=2024, period_end=date(2024, 12, 31)),
        _fact("RevenueFromContractWithCustomerExcludingAssessedTax", 1200, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("AccountsReceivableNetCurrent", 150, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("CostOfGoodsSold", 700, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("AssetsCurrent", 560, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("PropertyPlantAndEquipmentNet", 420, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("ShortTermInvestments", 50, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("Assets", 1400, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("DepreciationAndAmortization", 78, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("SellingGeneralAndAdministrativeExpense", 160, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("LiabilitiesCurrent", 320, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("LongTermDebtNoncurrent", 180, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("NetIncomeLoss", 100, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("NetCashProvidedByUsedInOperatingActivities", 95, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("InventoryNet", 130, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("PrepaidExpenseCurrent", 25, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("DeferredRevenueCurrent", 50, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("AccountsPayableCurrent", 90, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("AccruedLiabilitiesCurrent", 55, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("RetainedEarningsAccumulatedDeficit", 300, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("OperatingIncomeLoss", 130, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("StockholdersEquity", 800, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("Liabilities", 600, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("WeightedAverageNumberOfDilutedSharesOutstanding", 98, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("CashAndCashEquivalentsAtCarryingValue", 200, fiscal_year=2025, period_end=date(2025, 12, 31)),
    ]

    pack = build_accounting_factor_pack(facts)

    assert pack.period_label.startswith("FY2025")
    assert pack.prior_period_label.startswith("FY2024")
    assert pack.piotroski_f_score == 7
    assert pack.altman_z_score is not None and round(pack.altman_z_score, 3) == 3.847
    assert pack.sloan_accrual_ratio == 0.0038
    assert pack.asset_growth_pct == 16.67
    assert pack.beneish_m_score is not None and round(pack.beneish_m_score, 3) == -1.894
    assert pack.cash_based_operating_profitability is not None and round(pack.cash_based_operating_profitability, 4) == 0.2231
    assert pack.factor_quality_score is not None and pack.factor_quality_score > 70
    assert pack.factor_forensic_risk_score is not None and pack.factor_forensic_risk_score < 70
    assert pack.warnings == []


def test_build_accounting_factor_pack_flags_partial_history() -> None:
    facts = [
        _fact("RevenueFromContractWithCustomerExcludingAssessedTax", 500, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("Assets", 900, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("NetIncomeLoss", 50, fiscal_year=2025, period_end=date(2025, 12, 31)),
        _fact("NetCashProvidedByUsedInOperatingActivities", 60, fiscal_year=2025, period_end=date(2025, 12, 31)),
    ]

    pack = build_accounting_factor_pack(facts)

    assert pack.prior_period_label is None
    assert pack.piotroski_f_score is None
    assert pack.beneish_m_score is None
    assert "only one annual period available" in pack.warnings[0]
