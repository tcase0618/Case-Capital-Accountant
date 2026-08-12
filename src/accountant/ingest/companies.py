from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from accountant.db.models import Company, Security
from accountant.domain.cik import normalize_cik
from accountant.domain.ticker import normalize_ticker
from accountant.logging import get_logger

log = get_logger(__name__)


def upsert_company_and_securities(
    session: Session,
    submissions: dict[str, Any],
    *,
    fallback_ticker: str | None = None,
    fallback_name: str | None = None,
) -> Company:
    """Insert or update a company from SEC submissions JSON. Tickers become securities."""
    cik = normalize_cik(submissions.get("cik"))
    name = _first_text(submissions.get("name"), fallback_name)
    if not name:
        raise ValueError(f"SEC submissions for CIK {cik} has no company name")

    company = session.execute(select(Company).where(Company.cik == cik)).scalar_one_or_none()
    created = company is None
    if company is None:
        company = Company(cik=cik, name=name)
        session.add(company)
        session.flush()

    company.name = name
    company.entity_type = _optional_text(submissions.get("entityType"))
    company.sic = _optional_text(submissions.get("sic"))
    company.sic_description = _optional_text(submissions.get("sicDescription"))
    company.ein = _optional_text(submissions.get("ein"))
    company.fiscal_year_end = _optional_text(submissions.get("fiscalYearEnd"))
    company.state_of_incorporation = _optional_text(
        submissions.get("stateOfIncorporation") or submissions.get("stateOfIncorporationDescription")
    )

    tickers = _as_str_list(submissions.get("tickers"))
    exchanges = _as_str_list(submissions.get("exchanges"))
    if fallback_ticker:
        symbol = normalize_ticker(fallback_ticker)
        if symbol not in tickers:
            tickers.append(symbol)

    for index, raw_ticker in enumerate(tickers):
        try:
            symbol = normalize_ticker(raw_ticker)
        except Exception:
            log.warning("ingest.security_skip_malformed_ticker", cik=cik, ticker=raw_ticker)
            continue
        exchange = exchanges[index] if index < len(exchanges) else None
        _upsert_security(session, company, symbol, exchange)

    session.flush()
    log.info("ingest.company_upserted", cik=cik, name=company.name, created=created)
    return company


def _upsert_security(
    session: Session,
    company: Company,
    ticker: str,
    exchange: str | None,
) -> Security:
    security = session.execute(select(Security).where(Security.ticker == ticker)).scalar_one_or_none()
    if security is None:
        security = Security(
            company_id=company.id,
            ticker=ticker,
            exchange=_optional_text(exchange),
            security_type="common_stock",
        )
        session.add(security)
        return security
    security.company_id = company.id
    if exchange:
        security.exchange = _optional_text(exchange)
    return security


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None and str(item).strip()]
    return []


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = _optional_text(value)
        if text:
            return text
    return None
