from __future__ import annotations

import argparse
import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from accountant.config import get_settings
from accountant.db import create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import Company, CompanyReport, Filing, RawFact, Security
from accountant.ingest.companyfacts import ingest_company_facts_payload
from accountant.ingest.filings import fetch_company_filings_payload, ingest_company_filings_payload
from accountant.research.report_machine import MACHINE
from accountant.sec import SecClient
from accountant.sec.companyfacts import CompanyFactsClient
from accountant.sec.rate_limit import RateLimiter


@dataclass
class RunCounters:
    coverage_processed: int = 0
    coverage_errors: int = 0
    reports_processed: int = 0
    reports_errors: int = 0


def main() -> None:
    args = _parse_args()
    engine = create_db_engine()
    factory = create_session_factory(engine)
    counters = RunCounters()
    started = datetime.now(UTC)

    coverage_rows = _load_missing_report_rows(factory, limit=args.limit)
    print(
        f"[{started.isoformat()}] accelerated catch-up starting "
        f"coverage_companies={len(coverage_rows)} workers={args.workers} "
        f"report_workers={args.report_workers}",
        flush=True,
    )

    if coverage_rows:
        _run_coverage_stage(factory, coverage_rows, workers=args.workers, counters=counters)

    report_rows = _load_missing_report_rows(factory, limit=args.limit)
    if report_rows:
        _run_report_stage(factory, report_rows, workers=args.report_workers, counters=counters)

    ended = datetime.now(UTC)
    print(
        f"[{ended.isoformat()}] accelerated catch-up completed "
        f"coverage_processed={counters.coverage_processed} coverage_errors={counters.coverage_errors} "
        f"reports_processed={counters.reports_processed} reports_errors={counters.reports_errors} "
        f"duration_seconds={(ended - started).total_seconds():.1f}",
        flush=True,
    )
    engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Accelerated staged catch-up for missing company reports."
    )
    parser.add_argument("--workers", type=int, default=6, help="Worker count for raw SEC coverage.")
    parser.add_argument(
        "--report-workers",
        type=int,
        default=3,
        help="Worker count for downstream report builds.",
    )
    parser.add_argument("--limit", type=int, help="Maximum companies to process.")
    return parser.parse_args()


def _load_missing_report_rows(factory, limit: int | None) -> list[tuple[object, str]]:
    session = factory()
    try:
        primary_ticker = (
            select(
                Security.company_id.label("company_id"),
                func.min(Security.ticker).label("ticker"),
            )
            .group_by(Security.company_id)
            .subquery()
        )
        stmt = (
            select(Company.id, primary_ticker.c.ticker)
            .join(primary_ticker, primary_ticker.c.company_id == Company.id)
            .outerjoin(CompanyReport, CompanyReport.company_id == Company.id)
            .where(CompanyReport.id.is_(None))
            .order_by(primary_ticker.c.ticker.asc())
        )
        rows = [(company_id, ticker) for company_id, ticker in session.execute(stmt).all()]
        if limit is not None:
            return rows[: max(0, limit)]
        return rows
    finally:
        session.close()


def _run_coverage_stage(factory, rows: list[tuple[object, str]], *, workers: int, counters: RunCounters) -> None:
    shared_limiter = RateLimiter(get_settings().sec_min_interval_seconds)
    total = len(rows)
    print(
        f"[{datetime.now(UTC).isoformat()}] coverage stage starting companies={total} workers={workers}",
        flush=True,
    )
    queue = deque(rows)
    queue_lock = threading.Lock()
    counter_lock = threading.Lock()

    def _worker(worker_id: int) -> None:
        with SecClient() as sec_client:
            sec_client._limiter = shared_limiter
            companyfacts_client = CompanyFactsClient(get_settings(), sec_client=sec_client)
            try:
                while True:
                    with queue_lock:
                        if not queue:
                            return
                        company_id, ticker = queue.popleft()
                    session = factory()
                    try:
                        company = session.get(Company, company_id)
                        if company is None:
                            continue
                        _ensure_company_coverage(session, company, ticker, sec_client, companyfacts_client)
                        with counter_lock:
                            counters.coverage_processed += 1
                            processed = counters.coverage_processed
                            errors = counters.coverage_errors
                        if processed % 25 == 0 or processed == total:
                            print(
                                f"[coverage {processed}/{total}] errors={errors} last={ticker} worker={worker_id}",
                                flush=True,
                            )
                    except Exception as exc:
                        with counter_lock:
                            counters.coverage_errors += 1
                            errors = counters.coverage_errors
                            processed = counters.coverage_processed
                        print(
                            f"[coverage {processed}/{total}] error ticker={ticker} worker={worker_id} message={str(exc)[:300]} errors={errors}",
                            flush=True,
                        )
                    finally:
                        session.close()
            finally:
                companyfacts_client.close()

    threads = [
        threading.Thread(target=_worker, args=(index + 1,), daemon=True, name=f"coverage-worker-{index + 1}")
        for index in range(max(1, workers))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print(
        f"[{datetime.now(UTC).isoformat()}] coverage stage completed "
        f"processed={counters.coverage_processed} errors={counters.coverage_errors}",
        flush=True,
    )


def _ensure_company_coverage(
    session: Session,
    company: Company,
    ticker: str,
    sec_client: SecClient,
    companyfacts_client: CompanyFactsClient,
) -> None:
    filings_count = _count(session, Filing, company.id)
    if filings_count == 0:
        filing_payload = fetch_company_filings_payload(sec_client, ticker)
        with sqlite_write_guard():
            ingest_company_filings_payload(session, filing_payload)
            session.commit()

    raw_facts_count = _count(session, RawFact, company.id)
    if raw_facts_count == 0:
        facts_data = companyfacts_client.get_company_facts(company.cik)
        with sqlite_write_guard():
            ingest_company_facts_payload(session, company, facts_data)
            session.commit()


def _run_report_stage(factory, rows: list[tuple[object, str]], *, workers: int, counters: RunCounters) -> None:
    total = len(rows)
    print(
        f"[{datetime.now(UTC).isoformat()}] report stage starting companies={total} workers={workers}",
        flush=True,
    )
    queue = deque(rows)
    queue_lock = threading.Lock()
    counter_lock = threading.Lock()

    def _worker(worker_id: int) -> None:
        while True:
            with queue_lock:
                if not queue:
                    return
                company_id, ticker = queue.popleft()
            session = factory()
            try:
                company = session.get(Company, company_id)
                if company is None:
                    continue
                with sqlite_write_guard():
                    MACHINE._build_report(session, company, ticker)
                    session.commit()
                with counter_lock:
                    counters.reports_processed += 1
                    processed = counters.reports_processed
                    errors = counters.reports_errors
                if processed % 10 == 0 or processed == total:
                    print(
                        f"[reports {processed}/{total}] errors={errors} last={ticker} worker={worker_id}",
                        flush=True,
                    )
            except Exception as exc:
                session.rollback()
                with counter_lock:
                    counters.reports_errors += 1
                    errors = counters.reports_errors
                    processed = counters.reports_processed
                print(
                    f"[reports {processed}/{total}] error ticker={ticker} worker={worker_id} message={str(exc)[:300]} errors={errors}",
                    flush=True,
                )
            finally:
                session.close()

    threads = [
        threading.Thread(target=_worker, args=(index + 1,), daemon=True, name=f"report-worker-{index + 1}")
        for index in range(max(1, workers))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print(
        f"[{datetime.now(UTC).isoformat()}] report stage completed "
        f"processed={counters.reports_processed} errors={counters.reports_errors}",
        flush=True,
    )


def _count(session: Session, model, company_id: object) -> int:
    return len(
        session.execute(
            select(model.id).where(model.company_id == company_id)
        ).scalars().all()
    )


if __name__ == "__main__":
    main()
