from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select

from accountant.db import create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import CanonicalFact, Company, CompanyReport, Filing, RawFact, Security, StatementSnapshot
from accountant.financial.snapshot_service import build_company_statement_snapshots
from accountant.research.report_machine import MACHINE


@dataclass(frozen=True)
class BacklogRow:
    company_id: Any
    ticker: str
    pipeline_stage: str
    filings_count: int
    raw_facts_count: int
    canonical_facts_count: int
    statement_snapshots_count: int


def main() -> None:
    started = datetime.now(UTC)
    print(f"[{started.isoformat()}] backlog finalizer starting", flush=True)

    engine = create_db_engine()
    factory = create_session_factory(engine)
    rows = _load_backlog_rows(factory)
    print(
        f"[{datetime.now(UTC).isoformat()}] backlog rows={len(rows)} by_stage={dict(Counter(row.pipeline_stage for row in rows))}",
        flush=True,
    )

    processed = 0
    upgraded = 0
    parked = 0
    errors = 0

    for row in rows:
        session = factory()
        try:
            company = session.get(Company, row.company_id)
            if company is None:
                errors += 1
                print(f"[skip] missing company ticker={row.ticker}", flush=True)
                continue

            outcome = _finalize_company(session, company, row)
            with sqlite_write_guard():
                session.commit()

            processed += 1
            upgraded += int(outcome == "reports-ready")
            parked += int(outcome == "parked")
            print(
                f"[{processed}/{len(rows)}] ticker={row.ticker} stage={row.pipeline_stage} outcome={outcome}",
                flush=True,
            )
        except Exception as exc:
            session.rollback()
            errors += 1
            print(
                f"[{processed}/{len(rows)}] error ticker={row.ticker} stage={row.pipeline_stage} message={str(exc)[:300]}",
                flush=True,
            )
        finally:
            session.close()

    remaining_rows = _load_backlog_rows(factory)
    ended = datetime.now(UTC)
    print(
        f"[{ended.isoformat()}] backlog finalizer completed processed={processed} upgraded={upgraded} parked={parked} "
        f"errors={errors} remaining={len(remaining_rows)} duration_seconds={(ended - started).total_seconds():.1f}",
        flush=True,
    )
    if remaining_rows:
        for row in remaining_rows[:25]:
            print(
                f"[remaining] ticker={row.ticker} stage={row.pipeline_stage} filings={row.filings_count} raw={row.raw_facts_count} "
                f"canonical={row.canonical_facts_count} statements={row.statement_snapshots_count}",
                flush=True,
            )
    engine.dispose()


def _load_backlog_rows(factory) -> list[BacklogRow]:
    session = factory()
    try:
        raw_counts = (
            select(RawFact.company_id.label("company_id"), func.count(RawFact.id).label("raw_facts_count"))
            .group_by(RawFact.company_id)
            .subquery()
        )
        filing_counts = (
            select(Filing.company_id.label("company_id"), func.count(Filing.id).label("filings_count"))
            .group_by(Filing.company_id)
            .subquery()
        )
        canonical_counts = (
            select(CanonicalFact.company_id.label("company_id"), func.count(CanonicalFact.id).label("canonical_facts_count"))
            .group_by(CanonicalFact.company_id)
            .subquery()
        )
        statement_counts = (
            select(StatementSnapshot.company_id.label("company_id"), func.count(StatementSnapshot.id).label("statement_snapshots_count"))
            .group_by(StatementSnapshot.company_id)
            .subquery()
        )
        primary_ticker = (
            select(Security.company_id.label("company_id"), func.min(Security.ticker).label("ticker"))
            .group_by(Security.company_id)
            .subquery()
        )

        stmt: Select[Any] = (
            select(
                Company.id,
                primary_ticker.c.ticker,
                func.coalesce(CompanyReport.pipeline_stage, "missing"),
                func.coalesce(filing_counts.c.filings_count, 0),
                func.coalesce(raw_counts.c.raw_facts_count, 0),
                func.coalesce(canonical_counts.c.canonical_facts_count, 0),
                func.coalesce(statement_counts.c.statement_snapshots_count, 0),
            )
            .join(primary_ticker, primary_ticker.c.company_id == Company.id)
            .outerjoin(CompanyReport, CompanyReport.company_id == Company.id)
            .outerjoin(filing_counts, filing_counts.c.company_id == Company.id)
            .outerjoin(raw_counts, raw_counts.c.company_id == Company.id)
            .outerjoin(canonical_counts, canonical_counts.c.company_id == Company.id)
            .outerjoin(statement_counts, statement_counts.c.company_id == Company.id)
            .where(
                (CompanyReport.id.is_(None))
                | ((CompanyReport.pipeline_stage != "reports-ready") & (CompanyReport.pipeline_stage != "parked"))
            )
            .order_by(
                func.coalesce(CompanyReport.pipeline_stage, "missing").asc(),
                primary_ticker.c.ticker.asc(),
            )
        )
        return [
            BacklogRow(
                company_id=company_id,
                ticker=ticker,
                pipeline_stage=stage,
                filings_count=int(filings_count or 0),
                raw_facts_count=int(raw_facts_count or 0),
                canonical_facts_count=int(canonical_facts_count or 0),
                statement_snapshots_count=int(statement_snapshots_count or 0),
            )
            for company_id, ticker, stage, filings_count, raw_facts_count, canonical_facts_count, statement_snapshots_count in session.execute(stmt).all()
            if ticker
        ]
    finally:
        session.close()


def _finalize_company(session, company: Company, row: BacklogRow) -> str:
    if row.raw_facts_count <= 0:
        MACHINE._build_partial_report(
            session,
            company,
            row.ticker,
            terminal_reason="manual_filings_only_backfill",
        )
        return "parked"

    canonical_before = _count(session, CanonicalFact, company.id)
    if canonical_before == 0:
        try:
            MACHINE._normalize_company(session, company)
            session.flush()
        except Exception:
            MACHINE._build_partial_report(
                session,
                company,
                row.ticker,
                terminal_reason="manual_normalization_failed",
            )
            return "parked"

    canonical_after = _count(session, CanonicalFact, company.id)
    if canonical_after == 0:
        MACHINE._build_partial_report(
            session,
            company,
            row.ticker,
            terminal_reason="manual_zero_canonical_after_normalize",
        )
        return "parked"

    statements_after = _count(session, StatementSnapshot, company.id)
    if statements_after == 0:
        build_company_statement_snapshots(session, company.id)
        session.flush()

    MACHINE._build_report(session, company, row.ticker)
    session.flush()

    report = session.execute(
        select(CompanyReport).where(CompanyReport.company_id == company.id)
    ).scalar_one_or_none()
    if report is not None and report.pipeline_stage == "reports-ready":
        return "reports-ready"

    MACHINE._build_partial_report(
        session,
        company,
        row.ticker,
        terminal_reason="manual_report_not_ready_after_build",
    )
    return "parked"


def _count(session, model, company_id: Any) -> int:
    return int(
        session.execute(
            select(func.count()).select_from(model).where(model.company_id == company_id)
        ).scalar_one()
    )


if __name__ == "__main__":
    main()
