from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from accountant.db.models import RawFact


@dataclass(frozen=True)
class FactorPeriod:
    fiscal_year: int
    fiscal_period: str
    period_end: date | None
    facts: dict[str, float]


@dataclass(frozen=True)
class AccountingFactorPack:
    period_label: str
    prior_period_label: str | None
    beneish_m_score: float | None
    piotroski_f_score: int | None
    altman_z_score: float | None
    sloan_accrual_ratio: float | None
    cash_based_operating_profitability: float | None
    gross_profitability: float | None
    net_operating_assets_ratio: float | None
    asset_growth_pct: float | None
    external_financing_ratio: float | None
    factor_quality_score: float | None
    factor_forensic_risk_score: float | None
    warnings: list[str]
    factor_version: str = "ACCOUNTING_FACTOR_PACK_V1"


def build_accounting_factor_pack(facts: list[RawFact]) -> AccountingFactorPack:
    annual_periods = _annual_periods(facts)
    warnings: list[str] = []
    if not annual_periods:
        return AccountingFactorPack(
            period_label="N/A",
            prior_period_label=None,
            beneish_m_score=None,
            piotroski_f_score=None,
            altman_z_score=None,
            sloan_accrual_ratio=None,
            cash_based_operating_profitability=None,
            gross_profitability=None,
            net_operating_assets_ratio=None,
            asset_growth_pct=None,
            external_financing_ratio=None,
            factor_quality_score=None,
            factor_forensic_risk_score=None,
            warnings=["no annual periods available for factor computation"],
        )

    current = annual_periods[0]
    prior = annual_periods[1] if len(annual_periods) > 1 else None
    if prior is None:
        warnings.append("only one annual period available; YoY factors remain partial")

    beneish = _beneish_m_score(current, prior)
    piotroski = _piotroski_f_score(current, prior)
    altman = _altman_z_score(current)
    sloan = _sloan_accrual_ratio(current, prior)
    cbop = _cash_based_operating_profitability(current, prior)
    gross_profitability = _gross_profitability(current, prior)
    noa_ratio = _net_operating_assets_ratio(current)
    asset_growth_pct = _asset_growth_pct(current, prior)
    external_financing_ratio = _external_financing_ratio(current, prior)
    factor_quality_score = _factor_quality_score(
        piotroski_f_score=piotroski,
        cash_based_operating_profitability=cbop,
        gross_profitability=gross_profitability,
        altman_z_score=altman,
        sloan_accrual_ratio=sloan,
        asset_growth_pct=asset_growth_pct,
    )
    factor_forensic_risk_score = _factor_forensic_risk_score(
        beneish_m_score=beneish,
        sloan_accrual_ratio=sloan,
        net_operating_assets_ratio=noa_ratio,
        external_financing_ratio=external_financing_ratio,
    )
    return AccountingFactorPack(
        period_label=_period_label(current),
        prior_period_label=_period_label(prior) if prior else None,
        beneish_m_score=_round(beneish, 3),
        piotroski_f_score=piotroski,
        altman_z_score=_round(altman, 3),
        sloan_accrual_ratio=_round(sloan, 4),
        cash_based_operating_profitability=_round(cbop, 4),
        gross_profitability=_round(gross_profitability, 4),
        net_operating_assets_ratio=_round(noa_ratio, 4),
        asset_growth_pct=_round(asset_growth_pct, 2),
        external_financing_ratio=_round(external_financing_ratio, 4),
        factor_quality_score=_round(factor_quality_score, 2),
        factor_forensic_risk_score=_round(factor_forensic_risk_score, 2),
        warnings=warnings,
    )


def _annual_periods(facts: list[RawFact]) -> list[FactorPeriod]:
    grouped: dict[tuple[int, str, date | None], dict[str, float]] = {}
    for fact in facts:
        if fact.value_numeric is None or fact.fiscal_year is None:
            continue
        fiscal_period = (fact.fiscal_period or "").upper()
        if fiscal_period and fiscal_period != "FY":
            continue
        key = (fact.fiscal_year, fiscal_period or "FY", fact.period_end)
        bucket = grouped.setdefault(key, {})
        bucket.setdefault(fact.concept, float(Decimal(fact.value_numeric)))

    periods = [
        FactorPeriod(
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            period_end=period_end,
            facts=period_facts,
        )
        for (fiscal_year, fiscal_period, period_end), period_facts in grouped.items()
    ]
    periods.sort(key=lambda item: (item.fiscal_year, item.period_end or date.min), reverse=True)
    return periods


def _period_label(period: FactorPeriod | None) -> str:
    if period is None:
        return "N/A"
    if period.period_end is None:
        return f"FY{period.fiscal_year}"
    return f"FY{period.fiscal_year} ({period.period_end.isoformat()})"


def _fact(period: FactorPeriod | None, concepts: list[str]) -> float | None:
    if period is None:
        return None
    for concept in concepts:
        value = period.facts.get(concept)
        if value is not None:
            return value
    return None


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return ((current - prior) / abs(prior)) * 100


def _avg(*values: float | None) -> float | None:
    usable = [value for value in values if value is not None]
    if not usable:
        return None
    return sum(usable) / len(usable)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round(value: float | None, digits: int) -> float | None:
    return round(value, digits) if value is not None else None


def _revenue(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"])


def _cost_of_revenue(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["CostOfGoodsSold", "CostOfRevenue", "CostOfGoodsAndServicesSold"])


def _current_assets(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["AssetsCurrent"])


def _current_liabilities(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["LiabilitiesCurrent"])


def _accounts_receivable(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"])


def _inventory(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["InventoryNet"])


def _ppe(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["PropertyPlantAndEquipmentNet", "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization"])


def _securities(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["AvailableForSaleSecuritiesCurrent", "ShortTermInvestments", "MarketableSecuritiesCurrent"])


def _depreciation(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["DepreciationDepletionAndAmortization", "Depreciation", "DepreciationAndAmortization"])


def _sga(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["SellingGeneralAndAdministrativeExpense"])


def _short_term_debt(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["ShortTermBorrowings", "LongTermDebtCurrent"])


def _long_term_debt(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["LongTermDebtNoncurrent", "LongTermDebt"])


def _total_assets(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["Assets"])


def _net_income(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["NetIncomeLoss"])


def _cash_from_ops(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["NetCashProvidedByUsedInOperatingActivities"])


def _retained_earnings(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["RetainedEarningsAccumulatedDeficit", "RetainedEarningsAppropriated"])


def _ebit(period: FactorPeriod | None) -> float | None:
    operating_income = _fact(period, ["OperatingIncomeLoss"])
    if operating_income is not None:
        return operating_income
    pretax = _fact(period, ["IncomeBeforeTaxExpenseBenefit"])
    interest = _fact(period, ["InterestExpenseAndDebtExpense", "InterestExpense"])
    if pretax is not None and interest is not None:
        return pretax + abs(interest)
    return None


def _book_equity(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"])


def _total_liabilities(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["Liabilities"])


def _shares_outstanding(period: FactorPeriod | None) -> float | None:
    return _fact(period, [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "CommonStockSharesOutstanding",
    ])


def _cash(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"])


def _accounts_payable(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["AccountsPayableCurrent"])


def _accrued_expenses(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["AccruedLiabilitiesCurrent"])


def _deferred_revenue(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["DeferredRevenueCurrent", "ContractWithCustomerLiabilityCurrent"])


def _prepaids(period: FactorPeriod | None) -> float | None:
    return _fact(period, ["PrepaidExpenseAndOtherAssetsCurrent", "PrepaidExpenseCurrent"])


def _gross_profit(period: FactorPeriod | None) -> float | None:
    explicit = _fact(period, ["GrossProfit"])
    if explicit is not None:
        return explicit
    revenue = _revenue(period)
    cost = _cost_of_revenue(period)
    if revenue is None or cost is None:
        return None
    return revenue - cost


def _total_debt(period: FactorPeriod | None) -> float | None:
    short_term = _short_term_debt(period) or 0.0
    long_term = _long_term_debt(period) or 0.0
    total = short_term + long_term
    return total if total > 0 else None


def _beneish_m_score(current: FactorPeriod, prior: FactorPeriod | None) -> float | None:
    if prior is None:
        return None
    sales_t = _revenue(current)
    sales_prev = _revenue(prior)
    recv_t = _accounts_receivable(current)
    recv_prev = _accounts_receivable(prior)
    cogs_t = _cost_of_revenue(current)
    cogs_prev = _cost_of_revenue(prior)
    ca_t = _current_assets(current)
    ca_prev = _current_assets(prior)
    ppe_t = _ppe(current)
    ppe_prev = _ppe(prior)
    sec_t = _securities(current) or 0.0
    sec_prev = _securities(prior) or 0.0
    ta_t = _total_assets(current)
    ta_prev = _total_assets(prior)
    dep_t = _depreciation(current)
    dep_prev = _depreciation(prior)
    sga_t = _sga(current)
    sga_prev = _sga(prior)
    cl_t = _current_liabilities(current)
    cl_prev = _current_liabilities(prior)
    ltd_t = _long_term_debt(current)
    ltd_prev = _long_term_debt(prior)
    ni_t = _net_income(current)
    cfo_t = _cash_from_ops(current)

    dsri = _safe_divide(_safe_divide(recv_t, sales_t), _safe_divide(recv_prev, sales_prev))
    gm_t = _safe_divide((sales_t - cogs_t) if sales_t is not None and cogs_t is not None else None, sales_t)
    gm_prev = _safe_divide((sales_prev - cogs_prev) if sales_prev is not None and cogs_prev is not None else None, sales_prev)
    gmi = _safe_divide(gm_prev, gm_t)
    aq_t = None
    aq_prev = None
    if ta_t not in (None, 0) and ca_t is not None and ppe_t is not None:
        aq_t = 1 - ((ca_t + ppe_t + sec_t) / ta_t)
    if ta_prev not in (None, 0) and ca_prev is not None and ppe_prev is not None:
        aq_prev = 1 - ((ca_prev + ppe_prev + sec_prev) / ta_prev)
    aqi = _safe_divide(aq_t, aq_prev)
    sgi = _safe_divide(sales_t, sales_prev)
    depi = _safe_divide(_safe_divide(dep_prev, (dep_prev or 0.0) + (ppe_prev or 0.0)), _safe_divide(dep_t, (dep_t or 0.0) + (ppe_t or 0.0)))
    sgai = _safe_divide(_safe_divide(sga_t, sales_t), _safe_divide(sga_prev, sales_prev))
    lvgi = _safe_divide(_safe_divide((cl_t or 0.0) + (ltd_t or 0.0), ta_t), _safe_divide((cl_prev or 0.0) + (ltd_prev or 0.0), ta_prev))
    tata = _safe_divide((ni_t - cfo_t) if ni_t is not None and cfo_t is not None else None, ta_t)

    components = [dsri, gmi, aqi, sgi, depi, sgai, tata, lvgi]
    if any(component is None for component in components):
        return None
    return (
        -4.84
        + (0.920 * dsri)
        + (0.528 * gmi)
        + (0.404 * aqi)
        + (0.892 * sgi)
        + (0.115 * depi)
        - (0.172 * sgai)
        + (4.679 * tata)
        - (0.327 * lvgi)
    )


def _piotroski_f_score(current: FactorPeriod, prior: FactorPeriod | None) -> int | None:
    if prior is None:
        return None
    assets_t = _total_assets(current)
    assets_prev = _total_assets(prior)
    ni_t = _net_income(current)
    ni_prev = _net_income(prior)
    cfo_t = _cash_from_ops(current)
    debt_t = _long_term_debt(current)
    debt_prev = _long_term_debt(prior)
    ca_t = _current_assets(current)
    ca_prev = _current_assets(prior)
    cl_t = _current_liabilities(current)
    cl_prev = _current_liabilities(prior)
    shares_t = _shares_outstanding(current)
    shares_prev = _shares_outstanding(prior)
    revenue_t = _revenue(current)
    revenue_prev = _revenue(prior)
    gross_profit_t = _gross_profit(current)
    gross_profit_prev = _gross_profit(prior)

    roa_t = _safe_divide(ni_t, assets_t)
    roa_prev = _safe_divide(ni_prev, assets_prev)
    leverage_t = _safe_divide(debt_t, assets_t)
    leverage_prev = _safe_divide(debt_prev, assets_prev)
    current_ratio_t = _safe_divide(ca_t, cl_t)
    current_ratio_prev = _safe_divide(ca_prev, cl_prev)
    gross_margin_t = _safe_divide(gross_profit_t, revenue_t)
    gross_margin_prev = _safe_divide(gross_profit_prev, revenue_prev)
    asset_turnover_t = _safe_divide(revenue_t, assets_t)
    asset_turnover_prev = _safe_divide(revenue_prev, assets_prev)

    components = [
        roa_t is not None,
        roa_prev is not None,
        cfo_t is not None,
        leverage_t is not None,
        leverage_prev is not None,
        current_ratio_t is not None,
        current_ratio_prev is not None,
        shares_t is not None,
        shares_prev is not None,
        gross_margin_t is not None,
        gross_margin_prev is not None,
        asset_turnover_t is not None,
        asset_turnover_prev is not None,
    ]
    if not all(components):
        return None

    score = 0
    score += int((roa_t or 0) > 0)
    score += int((cfo_t or 0) > 0)
    score += int(roa_prev is not None and roa_t is not None and roa_t > roa_prev)
    score += int(ni_t is not None and cfo_t is not None and cfo_t > ni_t)
    score += int(leverage_prev is not None and leverage_t is not None and leverage_t < leverage_prev)
    score += int(current_ratio_prev is not None and current_ratio_t is not None and current_ratio_t > current_ratio_prev)
    score += int(shares_prev is not None and shares_t is not None and shares_t <= shares_prev)
    score += int(gross_margin_prev is not None and gross_margin_t is not None and gross_margin_t > gross_margin_prev)
    score += int(asset_turnover_prev is not None and asset_turnover_t is not None and asset_turnover_t > asset_turnover_prev)
    return score


def _altman_z_score(current: FactorPeriod) -> float | None:
    assets = _total_assets(current)
    if assets in (None, 0):
        return None
    working_capital = None
    current_assets = _current_assets(current)
    current_liabilities = _current_liabilities(current)
    if current_assets is not None and current_liabilities is not None:
        working_capital = current_assets - current_liabilities
    retained_earnings = _retained_earnings(current)
    ebit = _ebit(current)
    book_equity = _book_equity(current)
    liabilities = _total_liabilities(current)
    x1 = _safe_divide(working_capital, assets)
    x2 = _safe_divide(retained_earnings, assets)
    x3 = _safe_divide(ebit, assets)
    x4 = _safe_divide(book_equity, liabilities)
    if any(value is None for value in (x1, x2, x3, x4)):
        return None
    return (6.56 * x1) + (3.26 * x2) + (6.72 * x3) + (1.05 * x4)


def _sloan_accrual_ratio(current: FactorPeriod, prior: FactorPeriod | None) -> float | None:
    ni = _net_income(current)
    cfo = _cash_from_ops(current)
    assets_t = _total_assets(current)
    assets_prev = _total_assets(prior) if prior else None
    average_assets = _avg(assets_t, assets_prev) if prior else assets_t
    return _safe_divide((ni - cfo) if ni is not None and cfo is not None else None, average_assets)


def _cash_based_operating_profitability(current: FactorPeriod, prior: FactorPeriod | None) -> float | None:
    if prior is None:
        return None
    revenue = _revenue(current)
    cogs = _cost_of_revenue(current)
    sga = _sga(current) or 0.0
    receivables_delta = None
    inventory_delta = None
    prepaid_delta = None
    deferred_revenue_delta = None
    payables_delta = None
    accrued_expense_delta = None
    current_assets = _total_assets(current)
    prior_assets = _total_assets(prior)
    average_assets = _avg(current_assets, prior_assets)

    ar_t = _accounts_receivable(current)
    ar_prev = _accounts_receivable(prior)
    if ar_t is not None and ar_prev is not None:
        receivables_delta = ar_t - ar_prev
    inv_t = _inventory(current)
    inv_prev = _inventory(prior)
    if inv_t is not None and inv_prev is not None:
        inventory_delta = inv_t - inv_prev
    pre_t = _prepaids(current)
    pre_prev = _prepaids(prior)
    if pre_t is not None and pre_prev is not None:
        prepaid_delta = pre_t - pre_prev
    defrev_t = _deferred_revenue(current)
    defrev_prev = _deferred_revenue(prior)
    if defrev_t is not None and defrev_prev is not None:
        deferred_revenue_delta = defrev_t - defrev_prev
    ap_t = _accounts_payable(current)
    ap_prev = _accounts_payable(prior)
    if ap_t is not None and ap_prev is not None:
        payables_delta = ap_t - ap_prev
    accr_t = _accrued_expenses(current)
    accr_prev = _accrued_expenses(prior)
    if accr_t is not None and accr_prev is not None:
        accrued_expense_delta = accr_t - accr_prev

    if average_assets in (None, 0) or revenue is None or cogs is None:
        return None
    return (
        revenue
        - cogs
        - sga
        - (receivables_delta or 0.0)
        - (inventory_delta or 0.0)
        - (prepaid_delta or 0.0)
        + (deferred_revenue_delta or 0.0)
        + (payables_delta or 0.0)
        + (accrued_expense_delta or 0.0)
    ) / average_assets


def _gross_profitability(current: FactorPeriod, prior: FactorPeriod | None) -> float | None:
    gross_profit = _gross_profit(current)
    assets_t = _total_assets(current)
    assets_prev = _total_assets(prior) if prior else None
    average_assets = _avg(assets_t, assets_prev) if prior else assets_t
    return _safe_divide(gross_profit, average_assets)


def _net_operating_assets_ratio(current: FactorPeriod) -> float | None:
    assets = _total_assets(current)
    cash = _cash(current) or 0.0
    liabilities = _total_liabilities(current)
    debt = _total_debt(current) or 0.0
    if assets in (None, 0) or liabilities is None:
        return None
    noa = (assets - cash) - (liabilities - debt)
    return noa / assets


def _asset_growth_pct(current: FactorPeriod, prior: FactorPeriod | None) -> float | None:
    if prior is None:
        return None
    return _pct_change(_total_assets(current), _total_assets(prior))


def _external_financing_ratio(current: FactorPeriod, prior: FactorPeriod | None) -> float | None:
    if prior is None:
        return None
    debt_delta = None
    shares_delta = None
    debt_t = _total_debt(current)
    debt_prev = _total_debt(prior)
    shares_t = _shares_outstanding(current)
    shares_prev = _shares_outstanding(prior)
    if debt_t is not None and debt_prev is not None:
        debt_delta = debt_t - debt_prev
    if shares_t is not None and shares_prev is not None:
        shares_delta = shares_t - shares_prev
    assets_t = _total_assets(current)
    assets_prev = _total_assets(prior)
    average_assets = _avg(assets_t, assets_prev)
    return _safe_divide((debt_delta or 0.0) + (shares_delta or 0.0), average_assets)


def _factor_quality_score(
    *,
    piotroski_f_score: int | None,
    cash_based_operating_profitability: float | None,
    gross_profitability: float | None,
    altman_z_score: float | None,
    sloan_accrual_ratio: float | None,
    asset_growth_pct: float | None,
) -> float | None:
    components: list[float] = []
    if piotroski_f_score is not None:
        components.append((piotroski_f_score / 9.0) * 100.0)
    if cash_based_operating_profitability is not None:
        components.append(_clamp(50.0 + (cash_based_operating_profitability * 180.0), 0.0, 100.0))
    if gross_profitability is not None:
        components.append(_clamp(50.0 + (gross_profitability * 220.0), 0.0, 100.0))
    if altman_z_score is not None:
        components.append(_clamp((altman_z_score / 3.0) * 100.0, 0.0, 100.0))
    if sloan_accrual_ratio is not None:
        components.append(_clamp(60.0 - (sloan_accrual_ratio * 350.0), 0.0, 100.0))
    if asset_growth_pct is not None:
        components.append(_clamp(70.0 - max(0.0, asset_growth_pct - 8.0), 0.0, 100.0))
    if not components:
        return None
    return sum(components) / len(components)


def _factor_forensic_risk_score(
    *,
    beneish_m_score: float | None,
    sloan_accrual_ratio: float | None,
    net_operating_assets_ratio: float | None,
    external_financing_ratio: float | None,
) -> float | None:
    components: list[float] = []
    if beneish_m_score is not None:
        if beneish_m_score > -1.78:
            components.append(90.0)
        elif beneish_m_score > -2.22:
            components.append(70.0)
        else:
            components.append(20.0)
    if sloan_accrual_ratio is not None:
        components.append(_clamp(50.0 + (sloan_accrual_ratio * 400.0), 0.0, 100.0))
    if net_operating_assets_ratio is not None:
        components.append(_clamp(35.0 + (net_operating_assets_ratio * 120.0), 0.0, 100.0))
    if external_financing_ratio is not None:
        components.append(_clamp(40.0 + (external_financing_ratio * 300.0), 0.0, 100.0))
    if not components:
        return None
    return sum(components) / len(components)
