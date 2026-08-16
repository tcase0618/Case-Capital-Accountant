from __future__ import annotations

import hashlib
from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from accountant.db.models import Company, CompanyReport, Filing, ReportCard, Security
from accountant.research.factor_engine import AccountingFactorPack


def persist_report_card(
    session: Session,
    *,
    company: Company,
    ticker: str,
    report: CompanyReport,
    latest_filing: Filing | None,
    factor_pack: AccountingFactorPack,
    standardized_financials: dict[str, object],
    growth_trend_deltas: dict[str, object],
    accrual_cash_quality: dict[str, object],
    forensic_scores: dict[str, object],
    positive_quality: dict[str, object],
    event_red_flags: dict[str, object],
    textual_signals: dict[str, object],
    non_gaap_forensics: dict[str, object],
    governance_ownership: dict[str, object],
    market_data_linkage: dict[str, object],
    universe_tradability: dict[str, object],
    final_verdict: dict[str, object],
    gics_sector: str | None = None,
    gics_industry: str | None = None,
    tag_map_version: str = "CANONICAL_MAPPING_V1",
) -> ReportCard | None:
    if latest_filing is None or latest_filing.filing_date is None:
        return None

    period_of_report = latest_filing.report_date
    report_card_id = _build_report_card_id(
        cik=company.cik,
        filing_type=latest_filing.form_type,
        period_of_report=period_of_report,
        filed_date=latest_filing.filing_date,
    )
    existing = session.execute(
        select(ReportCard).where(ReportCard.report_card_id == report_card_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    prior = session.execute(
        select(ReportCard)
        .where(ReportCard.company_id == company.id, ReportCard.filed_date < latest_filing.filing_date)
        .order_by(desc(ReportCard.filed_date), desc(ReportCard.created_at))
        .limit(1)
    ).scalar_one_or_none()
    security = session.execute(
        select(Security).where(Security.company_id == company.id).order_by(Security.ticker.asc()).limit(1)
    ).scalar_one_or_none()
    card = ReportCard(
        company_id=company.id,
        report_card_id=report_card_id,
        cik=company.cik,
        ticker=ticker,
        company_name=company.name,
        sic_code=company.sic,
        gics_sector=str(gics_sector) if gics_sector is not None else None,
        gics_industry=str(gics_industry) if gics_industry is not None else None,
        exchange=security.exchange if security else None,
        filing_type=latest_filing.form_type,
        period_of_report=period_of_report,
        filed_date=latest_filing.filing_date,
        accepted_at=latest_filing.accepted_at,
        accession_number=latest_filing.accession_number,
        source_url=latest_filing.source_url,
        raw_filing_sha256=_pointer_hash(latest_filing.accession_number, latest_filing.source_url),
        is_restatement=bool(latest_filing.is_amendment),
        restates_report_card_id=prior.report_card_id if latest_filing.is_amendment and prior else None,
        tag_map_version=tag_map_version,
        prior_report_card_id=prior.report_card_id if prior else None,
        standardized_financials=standardized_financials,
        growth_trend_deltas=growth_trend_deltas,
        accrual_cash_quality=accrual_cash_quality,
        forensic_scores={**forensic_scores, "factor_version": factor_pack.factor_version},
        positive_quality=positive_quality,
        event_red_flags=event_red_flags,
        textual_signals=textual_signals,
        non_gaap_forensics=non_gaap_forensics,
        governance_ownership=governance_ownership,
        market_data_linkage=market_data_linkage,
        universe_tradability=universe_tradability,
        final_verdict=final_verdict,
    )
    session.add(card)
    session.flush()
    return card


def latest_report_cards(session: Session, *, limit: int = 200) -> list[ReportCard]:
    rows = session.execute(
        select(ReportCard)
        .order_by(ReportCard.cik.asc(), ReportCard.filed_date.desc(), ReportCard.created_at.desc())
    ).scalars().all()
    latest_by_cik: dict[str, ReportCard] = {}
    for row in rows:
        latest_by_cik.setdefault(row.cik, row)
        if len(latest_by_cik) >= limit:
            break
    return sorted(latest_by_cik.values(), key=lambda item: item.ticker)[:limit]


def latest_report_card_for_ticker(session: Session, ticker: str) -> ReportCard | None:
    rows = session.execute(
        select(ReportCard)
        .where(ReportCard.ticker == ticker.upper())
        .order_by(ReportCard.filed_date.desc(), ReportCard.created_at.desc())
        .limit(1)
    ).scalars().all()
    return rows[0] if rows else None


def _build_report_card_id(*, cik: str, filing_type: str, period_of_report: date | None, filed_date: date) -> str:
    period_token = period_of_report.isoformat() if period_of_report else "unknown-period"
    filing_token = filing_type.replace("/", "-")
    return f"{cik}_{filing_token}_{period_token}_{filed_date.isoformat()}"


def _pointer_hash(accession_number: str, source_url: str | None) -> str:
    payload = f"{accession_number}|{source_url or ''}".encode()
    return hashlib.sha256(payload).hexdigest()
