from __future__ import annotations

import argparse
import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Select, exists, func, select

from accountant.db import Base, create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import CanonicalFact, Company, CompanyReport, RawFact, ReportCard, Security, StatementSnapshot
from accountant.financial.snapshot_service import build_company_statement_snapshots
from accountant.research.report_machine import MACHINE


@dataclass(frozen=True)
class SweepRow:
    company_id: Any
    ticker: str
    raw_facts_count: int
    canonical_facts_count: int
    statement_snapshots_count: int
    has_report: bool
    has_report_card: bool
    pipeline_stage: str | None


def main() -> None:
    args = _parse_args()
    engine = create_db_engine()
    Base.metadata.create_all(bind=engine)
    factory = create_session_factory(engine)

    rows = _load_rows(
        factory,
        limit=args.limit,
        refresh_all=args.refresh_all,
        ticker=args.ticker,
    )
    started = datetime.now(UTC)
    print(
        f"[{started.isoformat()}] second sweep starting companies={len(rows)} "
        f"workers={args.workers} refresh_all={args.refresh_all}",
        flush=True,
    )

    queue = deque(rows)
    queue_lock = threading.Lock()
    counter_lock = threading.Lock()
    processed = 0
    canonicalized = 0
    statements_built = 0
    reports_refreshed = 0
    blocked = 0
    errors = 0

    def _worker(worker_id: int) -> None:
        nonlocal processed, canonicalized, statements_built, reports_refreshed, blocked, errors
        while True:
            with queue_lock:
                if not queue:
                    return
                row = queue.popleft()

            session = factory()
            try:
                company = session.get(Company, row.company_id)
                if company is None:
                    with counter_lock:
                        errors += 1
                    print(f"missing company ticker={row.ticker} worker={worker_id}", flush=True)
                    continue

                did_canonicalize = False
                did_build_statements = False
                did_refresh_report = False

                canonical_before = _count(session, CanonicalFact, row.company_id)
                statements_before = _count(session, StatementSnapshot, row.company_id)

                if canonical_before == 0 and row.raw_facts_count > 0:
                    with sqlite_write_guard():
                        MACHINE._normalize_company(session, company)
                        session.commit()
                    did_canonicalize = _count(session, CanonicalFact, row.company_id) > 0

                canonical_after = _count(session, CanonicalFact, row.company_id)
                if canonical_after > 0 and (statements_before == 0 or args.refresh_all):
                    with sqlite_write_guard():
                        build_company_statement_snapshots(session, row.company_id)
                        session.commit()
                    did_build_statements = _count(session, StatementSnapshot, row.company_id) > 0

                statements_after = _count(session, StatementSnapshot, row.company_id)
                needs_report_refresh = (
                    args.refresh_all
                    or not row.has_report
                    or not row.has_report_card
                    or row.pipeline_stage != "reports-ready"
                    or did_canonicalize
                    or did_build_statements
                )

                if canonical_after > 0 and needs_report_refresh:
                    with sqlite_write_guard():
                        MACHINE._build_report(session, company, row.ticker)
                        session.commit()
                    did_refresh_report = True

                was_blocked = canonical_after == 0 or statements_after == 0
                with counter_lock:
                    processed += 1
                    canonicalized += int(did_canonicalize)
                    statements_built += int(did_build_statements)
                    reports_refreshed += int(did_refresh_report)
                    blocked += int(was_blocked)
                    current_processed = processed
                    current_errors = errors
                    current_blocked = blocked

                if current_processed % 10 == 0 or current_processed == len(rows):
                    print(
                        f"[{current_processed}/{len(rows)}] last={row.ticker} worker={worker_id} "
                        f"canonicalized={canonicalized} statements={statements_built} "
                        f"reports={reports_refreshed} blocked={current_blocked} errors={current_errors}",
                        flush=True,
                    )
            except Exception as exc:
                session.rollback()
                with counter_lock:
                    errors += 1
                    current_processed = processed
                    current_errors = errors
                print(
                    f"[{current_processed}/{len(rows)}] error ticker={row.ticker} worker={worker_id} "
                    f"message={str(exc)[:300]} errors={current_errors}",
                    flush=True,
                )
            finally:
                session.close()

    threads = [
        threading.Thread(target=_worker, args=(index + 1,), daemon=True, name=f"second-sweep-worker-{index + 1}")
        for index in range(max(1, args.workers))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    ended = datetime.now(UTC)
    print(
        f"[{ended.isoformat()}] second sweep completed processed={processed} "
        f"canonicalized={canonicalized} statements={statements_built} reports={reports_refreshed} "
        f"blocked={blocked} errors={errors} duration_seconds={(ended - started).total_seconds():.1f}",
        flush=True,
    )
    engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upgrade partial accountant coverage into canonical facts, statement snapshots, and final reports."
    )
    parser.add_argument("--workers", type=int, default=4, help="Worker count for the second sweep.")
    parser.add_argument("--limit", type=int, help="Maximum companies to process.")
    parser.add_argument("--ticker", type=str, help="Only run the second sweep for one ticker.")
    parser.add_argument("--refresh-all", action="store_true", help="Rebuild reports/statements even if they already exist.")
    return parser.parse_args()


def _load_rows(factory, *, limit: int | None, refresh_all: bool, ticker: str | None) -> list[SweepRow]:
    session = factory()
    try:
        raw_counts = (
            select(RawFact.company_id.label("company_id"), func.count(RawFact.id).label("raw_facts_count"))
            .group_by(RawFact.company_id)
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
        report_card_exists = exists(select(1).where(ReportCard.company_id == Company.id))

        stmt: Select = (
            select(
                Company.id,
                primary_ticker.c.ticker,
                raw_counts.c.raw_facts_count,
                func.coalesce(canonical_counts.c.canonical_facts_count, 0),
                func.coalesce(statement_counts.c.statement_snapshots_count, 0),
                CompanyReport.id.is_not(None),
                report_card_exists,
                CompanyReport.pipeline_stage,
            )
            .join(raw_counts, raw_counts.c.company_id == Company.id)
            .join(primary_ticker, primary_ticker.c.company_id == Company.id)
            .outerjoin(canonical_counts, canonical_counts.c.company_id == Company.id)
            .outerjoin(statement_counts, statement_counts.c.company_id == Company.id)
            .outerjoin(CompanyReport, CompanyReport.company_id == Company.id)
            .where(raw_counts.c.raw_facts_count > 0)
            .order_by(
                func.coalesce(canonical_counts.c.canonical_facts_count, 0).asc(),
                func.coalesce(statement_counts.c.statement_snapshots_count, 0).asc(),
                primary_ticker.c.ticker.asc(),
            )
        )
        if ticker:
            stmt = stmt.where(primary_ticker.c.ticker == ticker.upper())
        if not refresh_all:
            stmt = stmt.where(
                (func.coalesce(canonical_counts.c.canonical_facts_count, 0) == 0)
                | (func.coalesce(statement_counts.c.statement_snapshots_count, 0) == 0)
                | (CompanyReport.id.is_(None))
                | (CompanyReport.pipeline_stage != "reports-ready")
                | (~report_card_exists)
            )

        rows = [
            SweepRow(
                company_id=company_id,
                ticker=symbol,
                raw_facts_count=int(raw_facts_count or 0),
                canonical_facts_count=int(canonical_facts_count or 0),
                statement_snapshots_count=int(statement_snapshots_count or 0),
                has_report=bool(has_report),
                has_report_card=bool(has_report_card),
                pipeline_stage=pipeline_stage,
            )
            for company_id, symbol, raw_facts_count, canonical_facts_count, statement_snapshots_count, has_report, has_report_card, pipeline_stage in session.execute(stmt).all()
            if symbol
        ]
        if limit is not None:
            return rows[: max(0, limit)]
        return rows
    finally:
        session.close()


def _count(session, model, company_id: Any) -> int:
    return int(
        session.execute(
            select(func.count()).select_from(model).where(model.company_id == company_id)
        ).scalar_one()
    )


if __name__ == "__main__":
    main()
