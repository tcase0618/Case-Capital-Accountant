from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from accountant.analysis.point_in_time_engine import PointInTimeResolver
from accountant.api.schemas import (
    ActionResultResponse,
    AvailableStatementResponse,
    BuyBoardCandidateResponse,
    BuyBoardStatusResponse,
    CacheWarmStatusResponse,
    CanonicalFactResponse,
    CompanyListItemResponse,
    CompanyReportResponse,
    CompanyResponse,
    DashboardResponse,
    DashboardStatsResponse,
    FilingDocumentResponse,
    FilingFeedItemResponse,
    FilingResponse,
    FutureCandidateResponse,
    HistoricalSnapshotResponse,
    IntegrationStatusResponse,
    MarketQuoteResponse,
    RawFactResponse,
    ReportCardResponse,
    ReportMachineStatusResponse,
    ResearchRecordResponse,
    StatementSnapshotResponse,
    TaxonomyConceptResponse,
    UniverseImportRequest,
    UniverseImportResponse,
)
from accountant.config import get_settings
from accountant.db import Base, create_db_engine, create_session_factory
from accountant.db.models import (
    BuyBoardCandidate,
    CanonicalConcept,
    CanonicalFact,
    Company,
    CompanyReport,
    Filing,
    RawFact,
    ReportCard,
    ResearchRecord,
    Security,
    StatementSnapshot,
)
from accountant.ingest.canonical_ingestion import CanonicalFactIngestion
from accountant.ingest.companies import import_companies_from_tickers, import_watchlist_tickers
from accountant.ingest.companyfacts import ingest_company_facts_for_company
from accountant.ingest.filings import ingest_company_filings
from accountant.market.alpaca_research import quote as alpaca_quote
from accountant.market.alpaca_research import status as alpaca_status
from accountant.research.buy_board import (
    BUY_BOARD,
    _best_price,
    _sector_from_description,
    _upside_pct,
    future_upside_candidates,
)
from accountant.research.cache_warmer import CACHE_WARMER
from accountant.research.report_cards import latest_report_card_for_ticker, latest_report_cards
from accountant.research.report_machine import MACHINE
from accountant.sec import SecClient
from accountant.sec.companyfacts import CompanyFactsClient
from accountant.sec.exceptions import SecConfigError
from accountant.taxonomy import get_canonical_registry
from accountant.taxonomy.seed import ensure_canonical_taxonomy_seeded
from accountant.xbrl.arelle_adapter import ArelleFacade

app = FastAPI(title="THE ACCOUNTANT", version="0.2.0")
ibkr_quote = alpaca_quote

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DASHBOARD_FACT_CACHE_PATH = _REPO_ROOT / ".run" / "dashboard_fact_totals.json"
_DASHBOARD_FACT_CACHE_LOCK = threading.Lock()
_DASHBOARD_FACT_CACHE: dict[str, int | str | bool | None] = {
    "total_raw_facts": 0,
    "total_canonical_facts": 0,
    "updated_at": None,
    "refresh_running": False,
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3002",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
_FRONTEND_ASSETS = _FRONTEND_DIST / "assets"
if _FRONTEND_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_ASSETS), name="frontend-assets")


def _load_dashboard_fact_cache() -> None:
    if not _DASHBOARD_FACT_CACHE_PATH.exists():
        return
    try:
        payload = json.loads(_DASHBOARD_FACT_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    with _DASHBOARD_FACT_CACHE_LOCK:
        _DASHBOARD_FACT_CACHE.update(
            {
                "total_raw_facts": int(payload.get("total_raw_facts", 0) or 0),
                "total_canonical_facts": int(payload.get("total_canonical_facts", 0) or 0),
                "updated_at": payload.get("updated_at"),
                "refresh_running": False,
            }
        )


def _write_dashboard_fact_cache(payload: dict[str, int | str | None]) -> None:
    _DASHBOARD_FACT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _DASHBOARD_FACT_CACHE_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload), encoding="utf-8")
    temp_path.replace(_DASHBOARD_FACT_CACHE_PATH)


def _sqlite_path_from_url(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw_path = database_url[len(prefix) :]
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def _should_use_background_fact_totals(database_url: str) -> bool:
    sqlite_path = _sqlite_path_from_url(database_url)
    if sqlite_path is None or not sqlite_path.exists():
        return False
    try:
        return sqlite_path.stat().st_size >= 1_000_000_000
    except OSError:
        return False


def _refresh_dashboard_fact_totals() -> None:
    settings = get_settings()
    sqlite_path = _sqlite_path_from_url(settings.database_url)
    if sqlite_path is None:
        with _DASHBOARD_FACT_CACHE_LOCK:
            _DASHBOARD_FACT_CACHE["refresh_running"] = False
        return

    try:
        connection = sqlite3.connect(sqlite_path, timeout=120)
        try:
            cursor = connection.cursor()
            total_raw_facts = int(cursor.execute("select count(*) from raw_facts").fetchone()[0])
            total_canonical_facts = int(
                cursor.execute("select count(*) from canonical_facts").fetchone()[0]
            )
        finally:
            connection.close()
        payload = {
            "total_raw_facts": total_raw_facts,
            "total_canonical_facts": total_canonical_facts,
            "updated_at": datetime.utcnow().isoformat(),
        }
        with _DASHBOARD_FACT_CACHE_LOCK:
            _DASHBOARD_FACT_CACHE.update(payload)
            _DASHBOARD_FACT_CACHE["refresh_running"] = False
        _write_dashboard_fact_cache(payload)
    except Exception:
        with _DASHBOARD_FACT_CACHE_LOCK:
            _DASHBOARD_FACT_CACHE["refresh_running"] = False


def _ensure_dashboard_fact_totals_refresh() -> dict[str, int | str | bool | None]:
    settings = get_settings()
    with _DASHBOARD_FACT_CACHE_LOCK:
        should_start = (
            _should_use_background_fact_totals(settings.database_url)
            and not bool(_DASHBOARD_FACT_CACHE.get("refresh_running"))
            and not _DASHBOARD_FACT_CACHE.get("updated_at")
        )
        if should_start:
            _DASHBOARD_FACT_CACHE["refresh_running"] = True
            thread = threading.Thread(
                target=_refresh_dashboard_fact_totals,
                name="dashboard-fact-totals",
                daemon=True,
            )
            thread.start()
        return dict(_DASHBOARD_FACT_CACHE)


_load_dashboard_fact_cache()


@app.on_event("startup")
def startup_machine() -> None:
    engine = create_db_engine()
    Base.metadata.create_all(bind=engine)
    factory = create_session_factory(engine)
    session = factory()
    try:
        ensure_canonical_taxonomy_seeded(session)
        session.commit()
    finally:
        session.close()
        engine.dispose()
    _ensure_dashboard_fact_totals_refresh()
    CACHE_WARMER.start()
    if get_settings().machine_enabled:
        MACHINE.start()
        BUY_BOARD.start()


@app.on_event("shutdown")
def shutdown_machine() -> None:
    MACHINE.stop()
    BUY_BOARD.stop()
    CACHE_WARMER.stop()


def get_session() -> Iterator[Session]:
    engine = create_db_engine()
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


SessionDep = Annotated[Session, Depends(get_session)]


def _get_company_row(session: Session, ticker: str) -> tuple[Company, str] | None:
    stmt = (
        select(Company, Security.ticker)
        .join(Security, Security.company_id == Company.id)
        .where(Security.ticker == ticker.upper())
        .limit(1)
    )
    return session.execute(stmt).first()


def _get_company_or_404(session: Session, ticker: str) -> tuple[Company, str]:
    row = _get_company_row(session, ticker)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Company not found for ticker {ticker.upper()}")
    return row


def _count_for_company(session: Session, model: Any, company_id: Any) -> int:
    stmt = select(func.count()).select_from(model).where(model.company_id == company_id)
    return int(session.execute(stmt).scalar_one())


def _latest_filing_date(session: Session, company_id: Any):
    stmt = select(func.max(Filing.filing_date)).where(Filing.company_id == company_id)
    return session.execute(stmt).scalar_one_or_none()


def _coverage_status(raw_facts: int, canonical_facts: int, statements: int) -> str:
    if statements > 0:
        return "statements-ready"
    if canonical_facts > 0:
        return "canonicalized"
    if raw_facts > 0:
        return "facts-ingested"
    return "filings-only"


def _distinct_company_count(session: Session, model: Any) -> int:
    return int(session.execute(select(func.count(func.distinct(model.company_id)))).scalar_one())


def _exists_company_count(session: Session, model: Any) -> int:
    exists_stmt = select(model.company_id).where(model.company_id == Company.id).limit(1)
    stmt = select(func.count()).select_from(Company).where(exists_stmt.exists())
    return int(session.execute(stmt).scalar_one())


def _serialize_company(session: Session, company: Company, ticker: str) -> CompanyResponse:
    filings_count = _count_for_company(session, Filing, company.id)
    raw_facts_count = _count_for_company(session, RawFact, company.id)
    canonical_facts_count = _count_for_company(session, CanonicalFact, company.id)
    statement_snapshots_count = _count_for_company(session, StatementSnapshot, company.id)
    research_records_count = _count_for_company(session, ResearchRecord, company.id)
    latest_filing = _latest_filing_date(session, company.id)
    return CompanyResponse(
        id=company.id,
        cik=company.cik,
        ticker=ticker,
        name=company.name,
        entity_type=company.entity_type,
        sic=company.sic,
        sic_description=company.sic_description,
        fiscal_year_end=company.fiscal_year_end,
        state_of_incorporation=company.state_of_incorporation,
        filings_count=filings_count,
        raw_facts_count=raw_facts_count,
        canonical_facts_count=canonical_facts_count,
        statement_snapshots_count=statement_snapshots_count,
        research_records_count=research_records_count,
        latest_filing_date=latest_filing,
    )


def _available_statement_response(statement: Any) -> AvailableStatementResponse:
    return AvailableStatementResponse(
        statement_type=statement.statement_type,
        period=statement.period,
        fiscal_end_date=statement.fiscal_end_date,
        filing_type=statement.filing_type.value,
        filed_date=statement.filed_date,
        accepted_timestamp=statement.accepted_timestamp,
        is_restated=statement.is_restated,
        original_filing_timestamp=statement.original_filing_timestamp,
        latest_amendment_timestamp=statement.latest_amendment_timestamp,
    )


def _parse_ticker_blob(ticker_blob: str) -> list[str]:
    separators = [",", "\n", "\r", "\t", ";", "|"]
    normalized = ticker_blob
    for separator in separators:
        normalized = normalized.replace(separator, " ")
    return [token.strip() for token in normalized.split(" ") if token.strip()]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready(session: SessionDep) -> dict[str, str | int]:
    company_count = int(session.execute(select(func.count()).select_from(Company)).scalar_one())
    return {"status": "ready", "companies": company_count}


@app.get("/companies/{ticker}", response_model=CompanyResponse)
def get_company(ticker: str, session: SessionDep) -> CompanyResponse:
    company, resolved_ticker = _get_company_or_404(session, ticker)
    return _serialize_company(session, company, resolved_ticker)


@app.get("/companies/{ticker}/facts", response_model=list[RawFactResponse])
def get_company_facts(
    ticker: str,
    session: SessionDep,
    concept: str | None = Query(default=None),
    taxonomy: str | None = Query(default=None),
    form: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[RawFactResponse]:
    company, _ = _get_company_or_404(session, ticker)

    stmt = select(RawFact).where(RawFact.company_id == company.id)

    if concept:
        stmt = stmt.where(RawFact.concept == concept)
    if taxonomy:
        stmt = stmt.where(RawFact.taxonomy == taxonomy)
    if form:
        stmt = stmt.where(RawFact.form == form)

    stmt = stmt.order_by(RawFact.period_end.desc(), RawFact.created_at.desc()).limit(limit)
    facts = session.execute(stmt).scalars().all()
    return [RawFactResponse.model_validate(fact) for fact in facts]


@app.get("/api/companies/{ticker}/facts", response_model=list[RawFactResponse])
def api_get_company_facts(
    ticker: str,
    session: SessionDep,
    concept: str | None = Query(default=None),
    taxonomy: str | None = Query(default=None),
    form: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[RawFactResponse]:
    return get_company_facts(
        ticker=ticker,
        session=session,
        concept=concept,
        taxonomy=taxonomy,
        form=form,
        limit=limit,
    )


@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard(session: SessionDep) -> DashboardResponse:
    bind = session.get_bind()
    use_background_fact_totals = _should_use_background_fact_totals(str(bind.url))
    fact_totals = _ensure_dashboard_fact_totals_refresh()
    companies_with_raw_facts = _exists_company_count(session, RawFact)
    companies_with_canonical_facts = _exists_company_count(session, CanonicalFact)
    companies_with_statement_snapshots = _exists_company_count(session, StatementSnapshot)
    companies_with_research_records = _exists_company_count(session, ResearchRecord)
    companies_with_reports = _exists_company_count(session, CompanyReport)
    stats = DashboardStatsResponse(
        total_companies=int(session.execute(select(func.count()).select_from(Company)).scalar_one()),
        total_filings=int(session.execute(select(func.count()).select_from(Filing)).scalar_one()),
        total_raw_facts=(
            int(fact_totals.get("total_raw_facts") or 0)
            if use_background_fact_totals
            else int(session.execute(select(func.count()).select_from(RawFact)).scalar_one())
        ),
        total_canonical_facts=(
            int(fact_totals.get("total_canonical_facts") or 0)
            if use_background_fact_totals
            else int(session.execute(select(func.count()).select_from(CanonicalFact)).scalar_one())
        ),
        total_statement_snapshots=int(session.execute(select(func.count()).select_from(StatementSnapshot)).scalar_one()),
        total_research_records=int(session.execute(select(func.count()).select_from(ResearchRecord)).scalar_one()),
        companies_with_raw_facts=companies_with_raw_facts,
        companies_with_canonical_facts=companies_with_canonical_facts,
        companies_with_statement_snapshots=companies_with_statement_snapshots,
        companies_with_research_records=companies_with_research_records,
        companies_with_reports=companies_with_reports,
    )

    companies = session.execute(
        select(Company, Security.ticker)
        .join(Security, Security.company_id == Company.id)
        .order_by(Company.name.asc())
        .limit(12)
    ).all()

    coverage = []
    for company, ticker in companies:
        filings_count = _count_for_company(session, Filing, company.id)
        raw_facts_count = _count_for_company(session, RawFact, company.id)
        canonical_facts_count = _count_for_company(session, CanonicalFact, company.id)
        statement_snapshots_count = _count_for_company(session, StatementSnapshot, company.id)
        research_records_count = _count_for_company(session, ResearchRecord, company.id)
        coverage.append(
            CompanyListItemResponse(
                ticker=ticker,
                cik=company.cik,
                name=company.name,
                filings_count=filings_count,
                raw_facts_count=raw_facts_count,
                canonical_facts_count=canonical_facts_count,
                statement_snapshots_count=statement_snapshots_count,
                research_records_count=research_records_count,
                latest_filing_date=_latest_filing_date(session, company.id),
                coverage_status=_coverage_status(
                    raw_facts_count,
                    canonical_facts_count,
                    statement_snapshots_count,
                ),
            )
        )

    filings_stmt = (
        select(Filing, Company.name, Security.ticker)
        .join(Company, Company.id == Filing.company_id)
        .join(Security, Security.company_id == Company.id)
        .order_by(Filing.filing_date.desc(), Filing.accepted_at.desc())
        .limit(8)
    )
    recent_filings = [
        FilingFeedItemResponse(
            ticker=ticker,
            company_name=company_name,
            accession_number=filing.accession_number,
            form_type=filing.form_type,
            filing_date=filing.filing_date,
            accepted_at=filing.accepted_at.isoformat() if filing.accepted_at else None,
        )
        for filing, company_name, ticker in session.execute(filings_stmt).all()
    ]

    ticker_tape = [
        f"{item.ticker} | {item.coverage_status} | filings {item.filings_count} | facts {item.raw_facts_count}"
        for item in coverage
    ]

    backlog = [
        "Statement reconstruction remains partial until statement builders consume canonical facts.",
        "Point-in-time metrics still need stricter accepted-timestamp lineage for audit-grade history.",
        "Valuation and peer analysis should stay internal until market data is integrated.",
    ]

    return DashboardResponse(
        generated_at=datetime.utcnow().isoformat(),
        stats=stats,
        coverage=coverage,
        recent_filings=recent_filings,
        ticker_tape=ticker_tape,
        backlog=backlog,
    )


@app.get("/api/companies", response_model=list[CompanyListItemResponse])
def list_companies(
    session: SessionDep,
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CompanyListItemResponse]:
    stmt = select(Company, Security.ticker).join(Security, Security.company_id == Company.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Security.ticker.ilike(like), Company.name.ilike(like), Company.cik.ilike(like)))
    stmt = stmt.order_by(Security.ticker.asc()).limit(limit)

    items = []
    for company, ticker in session.execute(stmt).all():
        filings_count = _count_for_company(session, Filing, company.id)
        raw_facts_count = _count_for_company(session, RawFact, company.id)
        canonical_facts_count = _count_for_company(session, CanonicalFact, company.id)
        statement_snapshots_count = _count_for_company(session, StatementSnapshot, company.id)
        research_records_count = _count_for_company(session, ResearchRecord, company.id)
        items.append(
            CompanyListItemResponse(
                ticker=ticker,
                cik=company.cik,
                name=company.name,
                filings_count=filings_count,
                raw_facts_count=raw_facts_count,
                canonical_facts_count=canonical_facts_count,
                statement_snapshots_count=statement_snapshots_count,
                research_records_count=research_records_count,
                latest_filing_date=_latest_filing_date(session, company.id),
                coverage_status=_coverage_status(
                    raw_facts_count,
                    canonical_facts_count,
                    statement_snapshots_count,
                ),
            )
        )
    return items


@app.get("/api/companies/{ticker}", response_model=CompanyResponse)
def api_get_company(ticker: str, session: SessionDep) -> CompanyResponse:
    company, resolved_ticker = _get_company_or_404(session, ticker)
    return _serialize_company(session, company, resolved_ticker)


@app.get("/api/companies/{ticker}/filings", response_model=list[FilingResponse])
def get_company_filings(
    ticker: str,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[FilingResponse]:
    company, _ = _get_company_or_404(session, ticker)
    stmt = (
        select(Filing)
        .where(Filing.company_id == company.id)
        .options(selectinload(Filing.documents))
        .order_by(Filing.filing_date.desc(), Filing.accepted_at.desc())
        .limit(limit)
    )
    filings = session.execute(stmt).scalars().all()
    responses = []
    for filing in filings:
        responses.append(
            FilingResponse(
                id=filing.id,
                accession_number=filing.accession_number,
                form_type=filing.form_type,
                filing_date=filing.filing_date,
                report_date=filing.report_date,
                accepted_at=filing.accepted_at.isoformat() if filing.accepted_at else None,
                primary_document=filing.primary_document,
                primary_doc_description=filing.primary_doc_description,
                is_amendment=filing.is_amendment,
                is_xbrl=filing.is_xbrl,
                is_inline_xbrl=filing.is_inline_xbrl,
                source_url=filing.source_url,
                documents=[FilingDocumentResponse.model_validate(doc) for doc in filing.documents],
            )
        )
    return responses


@app.get("/api/filings/recent", response_model=list[FilingFeedItemResponse])
def recent_filings(session: SessionDep, limit: int = Query(default=25, ge=1, le=100)) -> list[FilingFeedItemResponse]:
    stmt = (
        select(Filing, Company.name, Security.ticker)
        .join(Company, Company.id == Filing.company_id)
        .join(Security, Security.company_id == Company.id)
        .order_by(Filing.filing_date.desc(), Filing.accepted_at.desc())
        .limit(limit)
    )
    return [
        FilingFeedItemResponse(
            ticker=ticker,
            company_name=company_name,
            accession_number=filing.accession_number,
            form_type=filing.form_type,
            filing_date=filing.filing_date,
            accepted_at=filing.accepted_at.isoformat() if filing.accepted_at else None,
        )
        for filing, company_name, ticker in session.execute(stmt).all()
    ]


@app.get("/api/companies/{ticker}/canonical-facts", response_model=list[CanonicalFactResponse])
def get_company_canonical_facts(
    ticker: str,
    session: SessionDep,
    concept_code: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
) -> list[CanonicalFactResponse]:
    company, _ = _get_company_or_404(session, ticker)
    stmt = (
        select(CanonicalFact, CanonicalConcept, RawFact, Filing)
        .join(CanonicalConcept, CanonicalConcept.id == CanonicalFact.canonical_concept_id)
        .join(RawFact, RawFact.id == CanonicalFact.raw_fact_id)
        .join(Filing, Filing.id == RawFact.filing_id)
        .where(CanonicalFact.company_id == company.id)
    )
    if concept_code:
        stmt = stmt.where(CanonicalConcept.code == concept_code)
    stmt = stmt.order_by(RawFact.period_end.desc(), CanonicalFact.created_at.desc()).limit(limit)

    results = []
    for canonical_fact, canonical_concept, raw_fact, filing in session.execute(stmt).all():
        results.append(
            CanonicalFactResponse(
                id=canonical_fact.id,
                company_id=canonical_fact.company_id,
                raw_fact_id=canonical_fact.raw_fact_id,
                canonical_concept_code=canonical_concept.code,
                canonical_label=canonical_concept.label,
                value=canonical_fact.value,
                value_numeric=canonical_fact.value_numeric,
                unit=canonical_fact.unit,
                mapping_rule=canonical_fact.mapping_rule,
                mapping_version=canonical_fact.mapping_version,
                mapping_confidence=canonical_fact.mapping_confidence,
                reported_or_derived=canonical_fact.reported_or_derived,
                notes=canonical_fact.notes,
                raw_taxonomy=raw_fact.taxonomy,
                raw_concept=raw_fact.concept,
                accession_number=raw_fact.accession_number,
                filing_form=filing.form_type,
                period_end=raw_fact.period_end,
            )
        )
    return results


@app.get("/api/companies/{ticker}/statements", response_model=list[StatementSnapshotResponse])
def get_company_statements(
    ticker: str,
    session: SessionDep,
    statement_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[StatementSnapshotResponse]:
    company, _ = _get_company_or_404(session, ticker)
    stmt = select(StatementSnapshot).where(StatementSnapshot.company_id == company.id)
    if statement_type:
        stmt = stmt.where(StatementSnapshot.statement_type == statement_type)
    stmt = stmt.order_by(
        StatementSnapshot.fiscal_year.desc(),
        StatementSnapshot.fiscal_quarter.desc(),
        StatementSnapshot.created_at.desc(),
    ).limit(limit)
    snapshots = session.execute(stmt).scalars().all()
    return [
        StatementSnapshotResponse(
            id=snapshot.id,
            statement_type=snapshot.statement_type,
            fiscal_year=snapshot.fiscal_year,
            fiscal_quarter=snapshot.fiscal_quarter,
            period_type=snapshot.period_type,
            start_date=snapshot.start_date,
            end_date=snapshot.end_date,
            instant_date=snapshot.instant_date,
            source_accessions=snapshot.source_accessions,
            primary_accession=snapshot.primary_accession,
            builder_version=snapshot.builder_version,
            mapping_version=snapshot.mapping_version,
            resolver_version=snapshot.resolver_version,
            quality_status=snapshot.quality_status,
            completeness=snapshot.completeness,
            warnings=snapshot.warnings,
            is_restated=snapshot.is_restated,
            created_at=snapshot.created_at.isoformat() if snapshot.created_at else None,
        )
        for snapshot in snapshots
    ]


@app.get("/api/companies/{ticker}/research-records", response_model=list[ResearchRecordResponse])
def get_company_research_records(
    ticker: str,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ResearchRecordResponse]:
    company, _ = _get_company_or_404(session, ticker)
    stmt = (
        select(ResearchRecord)
        .where(ResearchRecord.company_id == company.id)
        .order_by(ResearchRecord.as_of_date.desc(), ResearchRecord.created_at.desc())
        .limit(limit)
    )
    records = session.execute(stmt).scalars().all()
    return [
        ResearchRecordResponse(
            id=record.id,
            as_of_date=record.as_of_date,
            classification=record.classification,
            classification_confidence=record.classification_confidence,
            accounting_quality_score=record.accounting_quality_score,
            owner_earnings_yield_pct=record.owner_earnings_yield_pct,
            roic_pct=record.roic_pct,
            capital_allocation_score=record.capital_allocation_score,
            credit_quality_score=record.credit_quality_score,
            forensic_risk_score=record.forensic_risk_score,
            valuation_range_low=record.valuation_range_low,
            valuation_range_high=record.valuation_range_high,
            current_price=record.current_price,
            margin_of_safety_pct=record.margin_of_safety_pct,
            rules_triggered=record.rules_triggered,
            rules_failed=record.rules_failed,
            warnings=record.warnings,
            classification_notes=record.classification_notes,
            created_at=record.created_at.isoformat() if record.created_at else None,
        )
        for record in records
    ]


@app.get("/api/companies/{ticker}/time-machine", response_model=HistoricalSnapshotResponse)
def get_company_time_machine(
    ticker: str,
    session: SessionDep,
    as_of_date: str = Query(...),
) -> HistoricalSnapshotResponse:
    company, _ = _get_company_or_404(session, ticker)
    snapshot = PointInTimeResolver.get_historical_snapshot(
        session=session,
        company_id=company.cik,
        as_of_date=as_of_date,
    )
    return HistoricalSnapshotResponse(
        company_id=snapshot.company_id,
        as_of_date=snapshot.as_of_date,
        as_of_timestamp=snapshot.as_of_timestamp,
        available_annual_filings=[_available_statement_response(item) for item in snapshot.available_annual_filings],
        available_quarterly_filings=[_available_statement_response(item) for item in snapshot.available_quarterly_filings],
        available_amendments=[_available_statement_response(item) for item in snapshot.available_amendments],
        accounting_metrics_available=snapshot.accounting_metrics_available,
        owner_earnings_available=snapshot.owner_earnings_available,
        roic_available=snapshot.roic_available,
        incremental_roic_available=snapshot.incremental_roic_available,
        economic_debt_available=snapshot.economic_debt_available,
        dilution_available=snapshot.dilution_available,
        capital_allocation_available=snapshot.capital_allocation_available,
        forensic_analysis_available=snapshot.forensic_analysis_available,
        accounting_dna_available=snapshot.accounting_dna_available,
        accounting_twin_available=snapshot.accounting_twin_available,
        valuation_inputs_available=snapshot.valuation_inputs_available,
        market_cap_available=snapshot.market_cap_available,
        debt_data_available=snapshot.debt_data_available,
        peer_data_available=snapshot.peer_data_available,
        historical_price_available=snapshot.historical_price_available,
        raw_fact_coverage_pct=snapshot.raw_fact_coverage_pct,
        canonical_mapping_coverage_pct=snapshot.canonical_mapping_coverage_pct,
        statement_completeness_score=snapshot.statement_completeness_score,
        warnings=snapshot.warnings,
        coverage_notes=snapshot.coverage_notes,
    )


@app.get("/api/taxonomy", response_model=list[TaxonomyConceptResponse])
def get_taxonomy(
    session: SessionDep,
    category: str | None = Query(default=None),
    limit: int = Query(default=250, ge=1, le=500),
) -> list[TaxonomyConceptResponse]:
    registry = get_canonical_registry()
    concepts = registry.list_concepts(category) if category else registry.list_concepts()
    db_concepts = {
        concept.code: concept
        for concept in session.execute(select(CanonicalConcept).limit(limit)).scalars().all()
    }
    response = []
    for concept in concepts[:limit]:
        db_concept = db_concepts.get(concept.code)
        response.append(
            TaxonomyConceptResponse(
                code=concept.code,
                label=concept.label,
                description=concept.description,
                category=concept.category,
                unit_hint=concept.unit_hint,
                version=db_concept.version if db_concept else concept.version,
                is_active=db_concept.is_active if db_concept else True,
            )
        )
    return response


@app.post("/api/companies/{ticker}/ingest/filings", response_model=ActionResultResponse)
def ingest_filings_action(ticker: str, session: SessionDep) -> ActionResultResponse:
    client = SecClient()
    try:
        result = ingest_company_filings(session, client, ticker)
        return ActionResultResponse(
            status="ok",
            message=f"Filing ingestion completed for {result.ticker}",
            details={
                "ticker": result.ticker,
                "cik": result.cik,
                "inserted": result.inserted,
                "skipped": result.skipped,
                "documents_inserted": result.documents_inserted,
            },
        )
    finally:
        client.close()


@app.post("/api/companies/{ticker}/ingest/companyfacts", response_model=ActionResultResponse)
def ingest_companyfacts_action(ticker: str, session: SessionDep) -> ActionResultResponse:
    sec_client = SecClient()
    companyfacts_client = CompanyFactsClient(get_settings(), sec_client=sec_client)
    try:
        resolution = sec_client.resolve_ticker(ticker)
        company = session.execute(select(Company).where(Company.cik == resolution.cik)).scalar_one_or_none()
        if company is None:
            raise HTTPException(status_code=404, detail=f"Company not found for ticker {ticker.upper()}. Ingest filings first.")

        result = ingest_company_facts_for_company(session, company, companyfacts_client, sec_client)
        return ActionResultResponse(
            status="ok",
            message=f"CompanyFacts ingestion completed for {ticker.upper()}",
            details={
                "ticker": result.ticker,
                "cik": result.cik,
                "concepts_processed": result.concepts_processed,
                "facts_inserted": result.facts_inserted,
                "facts_skipped": result.facts_skipped,
                "errors": result.errors,
            },
        )
    finally:
        companyfacts_client.close()


@app.post("/api/companies/{ticker}/normalize", response_model=ActionResultResponse)
def normalize_action(
    ticker: str,
    session: SessionDep,
    form: str | None = Query(default=None),
    mapping_version: int = Query(default=1, ge=1),
) -> ActionResultResponse:
    company, _ = _get_company_or_404(session, ticker)
    stmt = select(Filing).where(Filing.company_id == company.id)
    if form:
        stmt = stmt.where(Filing.form_type == form)
    filings = session.execute(stmt.order_by(Filing.filing_date.desc())).scalars().all()
    if not filings:
        raise HTTPException(status_code=404, detail=f"No filings available to normalize for {ticker.upper()}")

    try:
        arelle = ArelleFacade()
    except RuntimeError:
        arelle = None

    total_examined = 0
    total_inserted = 0
    total_existing = 0
    total_unmapped = 0
    all_errors: list[str] = []
    ingestion = CanonicalFactIngestion(session, arelle=arelle)

    for filing in filings:
        result = ingestion.ingest_filing(
            filing=filing,
            company=company,
            instance_url=filing.source_url,
            mapping_version=mapping_version,
        )
        total_examined += result.raw_facts_examined
        total_inserted += result.canonical_facts_inserted
        total_existing += result.canonical_facts_existing
        total_unmapped += result.facts_unmapped
        all_errors.extend(result.errors)

    return ActionResultResponse(
        status="ok",
        message=f"Canonical normalization completed for {ticker.upper()}",
        details={
            "filings_processed": len(filings),
            "raw_facts_examined": total_examined,
            "canonical_facts_inserted": total_inserted,
            "canonical_facts_existing": total_existing,
            "facts_unmapped": total_unmapped,
            "validation_enabled": arelle is not None,
            "errors": all_errors,
        },
    )


@app.post("/api/coverage/import", response_model=UniverseImportResponse)
def import_coverage_universe(
    payload: UniverseImportRequest,
    session: SessionDep,
) -> UniverseImportResponse:
    tickers = _parse_ticker_blob(payload.ticker_blob)
    if not tickers:
        raise HTTPException(status_code=400, detail="No tickers were provided.")

    try:
        sec_client = SecClient()
    except SecConfigError:
        result = import_watchlist_tickers(session, tickers)
        universe_label = payload.universe_name.strip() if payload.universe_name else "ticker import"
        return UniverseImportResponse(
            status="ok",
            message=f"{universe_label} completed in local watchlist mode",
            mode=result.mode,
            requested=result.requested,
            imported=result.imported,
            existing=result.existing,
            unresolved=result.unresolved,
            invalid=result.invalid,
            imported_tickers=result.imported_tickers,
        )

    try:
        result = import_companies_from_tickers(session, tickers, sec_client)
        universe_label = payload.universe_name.strip() if payload.universe_name else "ticker import"
        return UniverseImportResponse(
            status="ok",
            message=f"{universe_label} completed",
            mode=result.mode,
            requested=result.requested,
            imported=result.imported,
            existing=result.existing,
            unresolved=result.unresolved,
            invalid=result.invalid,
            imported_tickers=result.imported_tickers,
        )
    finally:
        sec_client.close()


@app.get("/api/integrations/ibkr", response_model=IntegrationStatusResponse)
def get_ibkr_integration_status() -> IntegrationStatusResponse:
    return IntegrationStatusResponse(**alpaca_status())


@app.get("/api/companies/{ticker}/market-quote", response_model=MarketQuoteResponse)
def get_company_market_quote(ticker: str) -> MarketQuoteResponse:
    return MarketQuoteResponse(**ibkr_quote(ticker))


@app.get("/api/reports", response_model=list[CompanyReportResponse])
def list_reports(
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[CompanyReportResponse]:
    reports = session.execute(
        select(CompanyReport)
        .order_by(CompanyReport.composite_score.desc(), CompanyReport.bearish_score.asc(), CompanyReport.ticker.asc())
        .limit(limit)
    ).scalars().all()
    return [
        CompanyReportResponse(
            ticker=report.ticker,
            company_name=report.company_name,
            as_of_date=report.as_of_date,
            stance=report.stance,
            bullish_score=report.bullish_score,
            bearish_score=report.bearish_score,
            composite_score=report.composite_score,
            data_quality_tier=report.data_quality_tier,
            pipeline_stage=report.pipeline_stage,
            latest_filing_date=report.latest_filing_date,
            current_price=report.current_price,
            key_stats=report.key_stats,
            highlights=report.highlights,
            report_markdown=report.report_markdown,
            updated_at=report.updated_at.isoformat() if report.updated_at else None,
        )
        for report in reports
    ]


def _report_card_response(row: ReportCard) -> ReportCardResponse:
    return ReportCardResponse(
        ticker=row.ticker,
        cik=row.cik,
        company_name=row.company_name,
        sic_code=row.sic_code,
        gics_sector=row.gics_sector,
        gics_industry=row.gics_industry,
        exchange=row.exchange,
        filing_type=row.filing_type,
        period_of_report=row.period_of_report.isoformat() if row.period_of_report else None,
        filed_date=row.filed_date.isoformat(),
        accepted_at=row.accepted_at.isoformat() if row.accepted_at else None,
        accession_number=row.accession_number,
        source_url=row.source_url,
        is_restatement=row.is_restatement,
        prior_report_card_id=row.prior_report_card_id,
        standardized_financials=row.standardized_financials,
        growth_trend_deltas=row.growth_trend_deltas,
        accrual_cash_quality=row.accrual_cash_quality,
        forensic_scores=row.forensic_scores,
        positive_quality=row.positive_quality,
        event_red_flags=row.event_red_flags,
        textual_signals=row.textual_signals,
        non_gaap_forensics=row.non_gaap_forensics,
        governance_ownership=row.governance_ownership,
        market_data_linkage=row.market_data_linkage,
        universe_tradability=row.universe_tradability,
        final_verdict=row.final_verdict,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


@app.get("/api/report-cards/latest", response_model=list[ReportCardResponse])
def list_latest_report_cards(
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[ReportCardResponse]:
    return [_report_card_response(row) for row in latest_report_cards(session, limit=limit)]


@app.get("/api/report-cards/{ticker}", response_model=ReportCardResponse)
def get_latest_report_card(session: SessionDep, ticker: str) -> ReportCardResponse:
    row = latest_report_card_for_ticker(session, ticker)
    if row is None:
        raise HTTPException(status_code=404, detail="Report card not found")
    return _report_card_response(row)


@app.get("/api/reports/status", response_model=ReportMachineStatusResponse)
def report_machine_status() -> ReportMachineStatusResponse:
    return ReportMachineStatusResponse(**MACHINE.snapshot())


@app.post("/api/reports/run-once", response_model=ReportMachineStatusResponse)
def run_report_machine_once() -> ReportMachineStatusResponse:
    return ReportMachineStatusResponse(**MACHINE.run_once())


@app.get("/api/cache/status", response_model=CacheWarmStatusResponse)
def cache_status() -> CacheWarmStatusResponse:
    return CacheWarmStatusResponse(**CACHE_WARMER.snapshot())


@app.get("/api/buy-board", response_model=list[BuyBoardCandidateResponse])
def list_buy_board(session: SessionDep) -> list[BuyBoardCandidateResponse]:
    candidates = session.execute(
        select(BuyBoardCandidate)
        .options(selectinload(BuyBoardCandidate.company))
        .where(BuyBoardCandidate.status == "ACTIVE")
        .order_by(BuyBoardCandidate.current_cc_valuation.desc().nullslast(), BuyBoardCandidate.ticker.asc())
    ).scalars().all()
    return [
        BuyBoardCandidateResponse(
            ticker=row.ticker,
            company_name=row.company_name,
            sector=_sector_from_description(row.company.sic_description if row.company else None),
            status=row.status,
            source_report_date=row.source_report_date,
            source_report_score=row.source_report_score,
            first_price=row.first_price,
            first_price_at=row.first_price_at.isoformat() if row.first_price_at else None,
            current_price=row.current_price,
            current_price_at=row.current_price_at.isoformat() if row.current_price_at else None,
            first_cc_valuation=row.first_cc_valuation,
            first_valuation_at=row.first_valuation_at.isoformat() if row.first_valuation_at else None,
            current_cc_valuation=row.current_cc_valuation,
            current_valuation_at=row.current_valuation_at.isoformat() if row.current_valuation_at else None,
            cc_valuation_growth_forecast_pct=row.cc_valuation_growth_forecast_pct,
            upside_pct=_upside_pct(row.current_cc_valuation, _best_price(row.current_price, row.first_price)),
            synopsis=row.synopsis,
            why_buy=row.why_buy,
            accounting_basis=row.accounting_basis,
            battle_card=row.battle_card,
            last_price_refresh_at=row.last_price_refresh_at.isoformat() if row.last_price_refresh_at else None,
            last_price_source=row.last_price_source,
            current_market_data_quality=row.current_market_data_quality,
            last_price_error=row.last_price_error,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )
        for row in candidates
    ]


@app.get("/api/future-board", response_model=list[FutureCandidateResponse])
def list_future_board(session: SessionDep) -> list[FutureCandidateResponse]:
    return [FutureCandidateResponse(**row) for row in future_upside_candidates(session)]


@app.get("/api/buy-board/status", response_model=BuyBoardStatusResponse)
def buy_board_status() -> BuyBoardStatusResponse:
    return BuyBoardStatusResponse(**BUY_BOARD.snapshot())


@app.post("/api/buy-board/refresh", response_model=BuyBoardStatusResponse)
def refresh_buy_board() -> BuyBoardStatusResponse:
    payload = BUY_BOARD.run_once()
    payload.pop("manual_refresh", None)
    return BuyBoardStatusResponse(**payload)


@app.get("/", response_model=None)
def frontend_entry() -> FileResponse | dict[str, str]:
    index_file = _FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "app": "THE ACCOUNTANT",
        "message": "Frontend bundle not built yet. Run npm install && npm run build in ./frontend or use npm run dev.",
    }


@app.get("/{full_path:path}", response_model=None)
def frontend_routes(full_path: str) -> FileResponse | dict[str, str]:
    if full_path.startswith(("api/", "companies/", "assets/")):
        raise HTTPException(status_code=404, detail="Not found")
    return frontend_entry()
