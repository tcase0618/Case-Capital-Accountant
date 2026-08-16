from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from accountant.db.models import Company, Security
from accountant.domain.cik import normalize_cik
from accountant.domain.ticker import normalize_ticker
from accountant.logging import get_logger
from accountant.sec import SecClient

log = get_logger(__name__)


@dataclass
class BulkCompanyImportResult:
    requested: int
    imported: int
    existing: int
    unresolved: list[str]
    invalid: list[str]
    imported_tickers: list[str]
    mode: str


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


def import_companies_from_tickers(
    session: Session,
    tickers: list[str],
    sec_client: SecClient,
) -> BulkCompanyImportResult:
    """Resolve a bulk list of tickers from SEC and upsert company registry entries."""
    requested = len(tickers)
    imported = 0
    existing = 0
    unresolved: list[str] = []
    invalid: list[str] = []
    imported_tickers: list[str] = []
    seen: set[str] = set()
    mapping = sec_client.get_company_tickers()

    for raw_ticker in tickers:
        try:
            symbol = normalize_ticker(raw_ticker)
        except Exception:
            invalid.append(str(raw_ticker).strip())
            continue
        if symbol in seen:
            continue
        seen.add(symbol)

        resolution = mapping.get(symbol)
        if resolution is None:
            unresolved.append(symbol)
            continue

        company = session.execute(select(Company).where(Company.cik == resolution.cik)).scalar_one_or_none()
        created = company is None
        if company is None:
            company = Company(cik=resolution.cik, name=resolution.name, entity_type="operating")
            session.add(company)
            session.flush()

        company.name = resolution.name
        _upsert_security(session, company, resolution.ticker, None)
        imported_tickers.append(resolution.ticker)
        if created:
            imported += 1
        else:
            existing += 1

    session.flush()
    log.info(
        "ingest.bulk_company_registry",
        requested=requested,
        imported=imported,
        existing=existing,
        unresolved=len(unresolved),
        invalid=len(invalid),
    )
    return BulkCompanyImportResult(
        requested=requested,
        imported=imported,
        existing=existing,
        unresolved=unresolved,
        invalid=invalid,
        imported_tickers=imported_tickers,
        mode="sec_registry",
    )


def import_watchlist_tickers(
    session: Session,
    tickers: list[str],
) -> BulkCompanyImportResult:
    """Create local research-watchlist companies when SEC resolution is unavailable."""
    requested = len(tickers)
    imported = 0
    existing = 0
    unresolved: list[str] = []
    invalid: list[str] = []
    imported_tickers: list[str] = []
    seen: set[str] = set()

    for raw_ticker in tickers:
        try:
            symbol = normalize_ticker(raw_ticker)
        except Exception:
            invalid.append(str(raw_ticker).strip())
            continue
        if symbol in seen:
            continue
        seen.add(symbol)

        security = session.execute(select(Security).where(Security.ticker == symbol)).scalar_one_or_none()
        if security is not None:
            existing += 1
            imported_tickers.append(symbol)
            continue

        company = Company(
            cik=_next_watchlist_cik(session),
            name=symbol,
            entity_type="research-watchlist",
            sic_description="Local watchlist import",
        )
        session.add(company)
        session.flush()
        session.add(
            Security(
                company_id=company.id,
                ticker=symbol,
                exchange=None,
                security_type="common_stock",
            )
        )
        imported += 1
        imported_tickers.append(symbol)

    session.flush()
    log.info(
        "ingest.bulk_watchlist_registry",
        requested=requested,
        imported=imported,
        existing=existing,
        invalid=len(invalid),
    )
    return BulkCompanyImportResult(
        requested=requested,
        imported=imported,
        existing=existing,
        unresolved=unresolved,
        invalid=invalid,
        imported_tickers=imported_tickers,
        mode="local_watchlist",
    )


def _next_watchlist_cik(session: Session) -> str:
    index = 1
    while True:
        candidate = f"WL{index:08d}"
        exists = session.execute(select(Company.id).where(Company.cik == candidate)).scalar_one_or_none()
        if exists is None:
            return candidate
        index += 1


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
