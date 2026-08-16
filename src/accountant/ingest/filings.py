from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from accountant.db.models import Company, Filing, FilingDocument
from accountant.domain.cik import normalize_cik
from accountant.ingest.companies import upsert_company_and_securities
from accountant.ingest.dates import column_at, is_amendment, parse_date, parse_datetime
from accountant.logging import get_logger
from accountant.sec.client import SecClient

log = get_logger(__name__)


@dataclass
class FilingIngestResult:
    cik: str
    ticker: str
    company_name: str
    inserted: int = 0
    skipped: int = 0
    documents_inserted: int = 0
    accession_numbers: list[str] = field(default_factory=list)

    @property
    def considered(self) -> int:
        return self.inserted + self.skipped


@dataclass(frozen=True)
class FilingFetchPayload:
    resolution_ticker: str
    resolution_name: str
    submissions: dict[str, Any]
    historical_shards: list[dict[str, Any]]


def ingest_company_filings(
    session: Session,
    client: SecClient,
    ticker: str,
    *,
    include_historical_files: bool = True,
) -> FilingIngestResult:
    """Fetch SEC company submissions and persist filing metadata idempotently."""
    payload = fetch_company_filings_payload(
        client,
        ticker,
        include_historical_files=include_historical_files,
    )
    return ingest_company_filings_payload(session, payload)


def fetch_company_filings_payload(
    client: SecClient,
    ticker: str,
    *,
    include_historical_files: bool = True,
) -> FilingFetchPayload:
    """Fetch SEC submissions and historical shards without touching the database."""
    resolution = client.resolve_ticker(ticker)
    submissions = client.get_submissions(resolution.cik)
    historical_shards: list[dict[str, Any]] = []
    if include_historical_files:
        files = submissions.get("filings", {}).get("files") or []
        for entry in files:
            name = entry.get("name") if isinstance(entry, dict) else None
            if not name:
                continue
            historical_shards.append(client.get_submissions_file(str(name)))
    return FilingFetchPayload(
        resolution_ticker=resolution.ticker,
        resolution_name=resolution.name,
        submissions=submissions,
        historical_shards=historical_shards,
    )


def ingest_company_filings_payload(
    session: Session,
    payload: FilingFetchPayload,
) -> FilingIngestResult:
    """Persist an already-fetched submissions payload."""
    company = upsert_company_and_securities(
        session,
        payload.submissions,
        fallback_ticker=payload.resolution_ticker,
        fallback_name=payload.resolution_name,
    )

    result = FilingIngestResult(
        cik=company.cik,
        ticker=payload.resolution_ticker,
        company_name=company.name,
    )
    _ingest_recent_block(
        session,
        None,
        company,
        payload.submissions.get("filings", {}).get("recent"),
        result,
        source_url_builder=_archive_document_url_builder(company.cik),
    )
    for shard in payload.historical_shards:
        _ingest_recent_block(
            session,
            None,
            company,
            shard,
            result,
            source_url_builder=_archive_document_url_builder(company.cik),
        )

    session.flush()
    log.info(
        "ingest.filings_complete",
        ticker=result.ticker,
        cik=result.cik,
        inserted=result.inserted,
        skipped=result.skipped,
    )
    return result


def ingest_filings_from_submissions(
    session: Session,
    company: Company,
    submissions: dict[str, Any],
    *,
    source_url_builder=None,
) -> FilingIngestResult:
    """Persist filings from an already-fetched submissions payload (tests / offline)."""
    result = FilingIngestResult(
        cik=company.cik,
        ticker="",
        company_name=company.name,
    )
    _ingest_recent_block(
        session,
        None,
        company,
        submissions.get("filings", {}).get("recent"),
        result,
        source_url_builder=source_url_builder,
    )
    return result


def _ingest_recent_block(
    session: Session,
    client: SecClient | None,
    company: Company,
    block: Any,
    result: FilingIngestResult,
    *,
    source_url_builder=None,
) -> None:
    if not isinstance(block, dict):
        return
    accessions = block.get("accessionNumber") or []
    if not isinstance(accessions, list):
        return

    for index, raw_accession in enumerate(accessions):
        accession = _clean(raw_accession)
        if not accession:
            log.warning("ingest.filing_missing_accession", cik=company.cik, index=index)
            continue

        existing = session.execute(
            select(Filing).where(Filing.accession_number == accession)
        ).scalar_one_or_none()
        if existing is not None:
            result.skipped += 1
            continue

        form_type = _clean(column_at(block, "form", index)) or "UNKNOWN"
        filing_date = parse_date(_clean(column_at(block, "filingDate", index)))
        if filing_date is None:
            log.warning(
                "ingest.filing_missing_filing_date",
                cik=company.cik,
                accession=accession,
            )
            result.skipped += 1
            continue

        primary_document = _clean(column_at(block, "primaryDocument", index))
        source_url = None
        if source_url_builder:
            source_url = source_url_builder(company.cik, accession, primary_document)
        elif client is not None and primary_document:
            source_url = client.archive_document_url(company.cik, accession, primary_document)

        is_xbrl = _optional_bool(column_at(block, "isXBRL", index))
        is_inline = _optional_bool(column_at(block, "isInlineXBRL", index))
        size = column_at(block, "size", index)
        size_bytes = int(size) if isinstance(size, int) or (isinstance(size, str) and size.isdigit()) else None

        filing = Filing(
            company_id=company.id,
            accession_number=accession,
            form_type=form_type,
            filing_date=filing_date,
            report_date=parse_date(_clean(column_at(block, "reportDate", index))),
            accepted_at=parse_datetime(_clean(column_at(block, "acceptanceDateTime", index))),
            primary_document=primary_document,
            primary_doc_description=_clean(column_at(block, "primaryDocDescription", index)),
            is_amendment=is_amendment(form_type),
            file_number=_clean(column_at(block, "fileNumber", index)),
            film_number=_clean(column_at(block, "filmNumber", index)),
            act=_clean(column_at(block, "act", index)),
            size_bytes=size_bytes,
            is_xbrl=is_xbrl,
            is_inline_xbrl=is_inline,
            source_system="sec_submissions",
            source_url=source_url,
        )
        session.add(filing)
        session.flush()

        if primary_document:
            document = FilingDocument(
                filing_id=filing.id,
                sequence=1,
                document_name=primary_document,
                document_type=form_type,
                description=filing.primary_doc_description,
                size_bytes=size_bytes,
                url=source_url,
            )
            session.add(document)
            result.documents_inserted += 1

        result.inserted += 1
        result.accession_numbers.append(accession)


def latest_filing_for_ticker(session: Session, ticker: str) -> Filing | None:
    from accountant.db.models import Security

    security = session.execute(select(Security).where(Security.ticker == ticker)).scalar_one_or_none()
    if security is None:
        return None
    return session.execute(
        select(Filing)
        .where(Filing.company_id == security.company_id)
        .order_by(Filing.filing_date.desc(), Filing.accepted_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    return None


def _archive_document_url_builder(cik: str):
    cik_nolead = str(int(normalize_cik(cik)))

    def _build(_company_cik: str, accession_number: str, document: str | None) -> str | None:
        if not document:
            return None
        accession_nodash = accession_number.replace("-", "")
        return f"https://www.sec.gov/Archives/edgar/data/{cik_nolead}/{accession_nodash}/{document}"

    return _build


# Re-export for tests that construct companies from submissions without a client.
__all__ = [
    "FilingIngestResult",
    "FilingFetchPayload",
    "fetch_company_filings_payload",
    "ingest_company_filings",
    "ingest_company_filings_payload",
    "ingest_filings_from_submissions",
    "latest_filing_for_ticker",
    "normalize_cik",
]
