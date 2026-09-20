from __future__ import annotations

import argparse
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select, text

from accountant.config import get_settings
from accountant.db import create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import Company, CompanyReport
from accountant.financial.snapshot_service import build_company_statement_snapshots
from accountant.ingest.companyfacts import ingest_company_facts_payload
from accountant.logging import configure_logging, get_logger
from accountant.research.buy_board import sync_buy_board_candidate
from accountant.research.report_machine import MACHINE
from accountant.sec import SecClient
from accountant.sec.companyfacts import CompanyFactsClient
from accountant.sec.exceptions import SecHttpError
from accountant.sec.rate_limit import RateLimiter

log = get_logger(__name__)

CORE_FORMS = (
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
    "20-F",
    "20-F/A",
    "40-F",
    "40-F/A",
    "6-K",
    "6-K/A",
)


@dataclass(frozen=True)
class StaleReportJob:
    company_id: uuid.UUID
    ticker: str
    latest_core_at: datetime
    latest_card_at: datetime | None


@dataclass
class RefreshCounters:
    processed: int = 0
    facts_refreshed: int = 0
    facts_skipped_404: int = 0
    canonicalized: int = 0
    statements: int = 0
    reports: int = 0
    strategy: int = 0
    errors: int = 0


def _load_stale_jobs(session_factory: Any, *, limit: int | None, ticker: str | None) -> list[StaleReportJob]:
    limit_sql = "limit :limit" if limit else ""
    ticker_sql = "and upper(s.ticker) = upper(:ticker)" if ticker else ""
    sql = text(
        f"""
        with latest_core as (
            select
                company_id,
                max(coalesce(accepted_at, filing_date::timestamp with time zone)) as latest_core_at
            from filings
            where form_type in (
                '10-K','10-K/A','10-Q','10-Q/A','20-F','20-F/A','40-F','40-F/A','6-K','6-K/A'
            )
            group by company_id
        ),
        latest_card as (
            select
                company_id,
                max(coalesce(accepted_at, filed_date::timestamp with time zone, created_at)) as latest_card_at
            from report_cards
            group by company_id
        ),
        primary_ticker as (
            select company_id, min(ticker) as ticker
            from securities
            group by company_id
        )
        select
            c.id::text as company_id,
            pt.ticker,
            lc.latest_core_at,
            lrc.latest_card_at
        from latest_core lc
        join companies c on c.id = lc.company_id
        join primary_ticker pt on pt.company_id = c.id
        join securities s on s.company_id = c.id and s.ticker = pt.ticker
        left join latest_card lrc on lrc.company_id = c.id
        where lc.latest_core_at > coalesce(lrc.latest_card_at, 'epoch'::timestamp with time zone)
        {ticker_sql}
        order by lc.latest_core_at desc, pt.ticker asc
        {limit_sql}
        """
    )
    params: dict[str, object] = {}
    if limit:
        params["limit"] = limit
    if ticker:
        params["ticker"] = ticker
    with session_factory() as session:
        rows = session.execute(sql, params).mappings().all()
    return [
        StaleReportJob(
            company_id=uuid.UUID(str(row["company_id"])),
            ticker=str(row["ticker"]),
            latest_core_at=row["latest_core_at"],
            latest_card_at=row["latest_card_at"],
        )
        for row in rows
    ]


def _latest_company_report(session: Any, company_id: uuid.UUID) -> CompanyReport | None:
    return session.execute(
        select(CompanyReport)
        .where(CompanyReport.company_id == company_id)
        .order_by(CompanyReport.updated_at.desc(), CompanyReport.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _worker(
    *,
    worker_id: int,
    queue: deque[StaleReportJob],
    queue_lock: threading.Lock,
    counters: RefreshCounters,
    counters_lock: threading.Lock,
    session_factory: Any,
    shared_limiter: RateLimiter,
    refresh_facts: bool,
) -> None:
    settings = get_settings()
    sec_client = SecClient(settings=settings)
    sec_client._limiter = shared_limiter
    companyfacts_client = CompanyFactsClient(settings, sec_client=sec_client)
    try:
        while True:
            with queue_lock:
                if not queue:
                    return
                job = queue.popleft()
                remaining = len(queue)
            started = time.monotonic()
            session = session_factory()
            try:
                company = session.get(Company, job.company_id)
                if company is None:
                    raise RuntimeError(f"company not found: {job.company_id}")

                facts_ok = False
                if refresh_facts:
                    try:
                        facts_data = companyfacts_client.get_company_facts(company.cik)
                        with sqlite_write_guard():
                            ingest_company_facts_payload(session, company, facts_data)
                            session.commit()
                        facts_ok = True
                    except SecHttpError as exc:
                        session.rollback()
                        if exc.status_code == 404:
                            with counters_lock:
                                counters.facts_skipped_404 += 1
                        else:
                            raise

                with sqlite_write_guard():
                    MACHINE._normalize_company(session, company)
                    session.commit()

                statement_summary = None
                with sqlite_write_guard():
                    statement_summary = build_company_statement_snapshots(session, company.id)
                    session.commit()

                with sqlite_write_guard():
                    MACHINE._build_report(session, company, job.ticker)
                    report = _latest_company_report(session, company.id)
                    if report is not None:
                        sync_buy_board_candidate(session, report)
                    session.commit()

                elapsed = time.monotonic() - started
                with counters_lock:
                    counters.processed += 1
                    counters.facts_refreshed += 1 if facts_ok else 0
                    counters.canonicalized += 1
                    counters.statements += 1 if statement_summary and statement_summary.snapshots_upserted else 0
                    counters.reports += 1
                    counters.strategy += 1
                    processed = counters.processed
                    errors = counters.errors
                print(
                    f"[worker {worker_id}] {job.ticker} refreshed "
                    f"processed={processed} remaining={remaining} errors={errors} elapsed={elapsed:.1f}s",
                    flush=True,
                )
            except Exception as exc:
                session.rollback()
                with counters_lock:
                    counters.errors += 1
                    errors = counters.errors
                log.warning(
                    "stale_refresh.company_failed",
                    worker=worker_id,
                    ticker=job.ticker,
                    error=str(exc)[:500],
                )
                print(
                    f"[worker {worker_id}] {job.ticker} failed errors={errors} error={str(exc)[:180]}",
                    flush=True,
                )
            finally:
                session.close()
    finally:
        companyfacts_client.close()


def _remaining_stale_count(session_factory: Any) -> int:
    with session_factory() as session:
        return int(
            session.execute(
                text(
                    """
                    with latest_core as (
                        select
                            company_id,
                            max(coalesce(accepted_at, filing_date::timestamp with time zone)) as latest_core_at
                        from filings
                        where form_type in (
                            '10-K','10-K/A','10-Q','10-Q/A','20-F','20-F/A','40-F','40-F/A','6-K','6-K/A'
                        )
                        group by company_id
                    ),
                    latest_card as (
                        select
                            company_id,
                            max(coalesce(accepted_at, filed_date::timestamp with time zone, created_at)) as latest_card_at
                        from report_cards
                        group by company_id
                    )
                    select count(*)
                    from latest_core lc
                    left join latest_card lrc on lrc.company_id = lc.company_id
                    where lc.latest_core_at > coalesce(lrc.latest_card_at, 'epoch'::timestamp with time zone)
                    """
                )
            ).scalar_one()
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh report cards for companies with newer core SEC filings.")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ticker", type=str, default=None)
    parser.add_argument("--skip-companyfacts", action="store_true")
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args()

    configure_logging(args.log_level)
    settings = get_settings()
    engine = create_db_engine(settings=settings)
    session_factory = create_session_factory(engine)
    jobs = _load_stale_jobs(session_factory, limit=args.limit, ticker=args.ticker)
    print(
        f"stale_core_report_jobs={len(jobs)} workers={args.workers} "
        f"refresh_facts={not args.skip_companyfacts}",
        flush=True,
    )
    if not jobs:
        engine.dispose()
        return 0

    queue: deque[StaleReportJob] = deque(jobs)
    queue_lock = threading.Lock()
    counters = RefreshCounters()
    counters_lock = threading.Lock()
    shared_limiter = RateLimiter(settings.sec_min_interval_seconds)
    threads = [
        threading.Thread(
            target=_worker,
            kwargs={
                "worker_id": index + 1,
                "queue": queue,
                "queue_lock": queue_lock,
                "counters": counters,
                "counters_lock": counters_lock,
                "session_factory": session_factory,
                "shared_limiter": shared_limiter,
                "refresh_facts": not args.skip_companyfacts,
            },
            daemon=True,
        )
        for index in range(max(1, args.workers))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    remaining = _remaining_stale_count(session_factory)
    print(
        "refresh_complete "
        f"processed={counters.processed} "
        f"facts_refreshed={counters.facts_refreshed} "
        f"facts_skipped_404={counters.facts_skipped_404} "
        f"canonicalized={counters.canonicalized} "
        f"statements={counters.statements} "
        f"reports={counters.reports} "
        f"strategy={counters.strategy} "
        f"errors={counters.errors} "
        f"remaining_stale={remaining}",
        flush=True,
    )
    engine.dispose()
    return 1 if counters.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
