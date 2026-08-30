from __future__ import annotations

import argparse
import threading
from collections import deque
from datetime import UTC, datetime

from sqlalchemy import delete, func, select

from accountant.db import Base, create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import Company, CompanyReport, ReportCard, Security
from accountant.research.report_machine import MACHINE


def main() -> None:
    args = _parse_args()
    engine = create_db_engine()
    Base.metadata.create_all(bind=engine)
    factory = create_session_factory(engine)

    if args.reset:
        _reset_report_cards(factory)
    elif args.replace_ticker:
        _reset_report_cards_for_ticker(factory, args.replace_ticker)

    rows = _load_company_rows(
        factory,
        ticker=args.ticker or args.replace_ticker,
        limit=args.limit,
        missing_only=not args.reset and not args.replace_ticker,
    )
    started = datetime.now(UTC)
    processed = 0
    skipped = 0
    errors = 0
    print(
        f"[{started.isoformat()}] report-card rebuild starting "
        f"companies={len(rows)} reset={args.reset} missing_only={not args.reset and not args.replace_ticker} workers={args.workers}",
        flush=True,
    )

    queue = deque(rows)
    queue_lock = threading.Lock()
    counter_lock = threading.Lock()

    def _worker(worker_id: int) -> None:
        nonlocal processed, skipped, errors
        while True:
            with queue_lock:
                if not queue:
                    return
                company_id, ticker = queue.popleft()
            session = factory()
            try:
                company = session.get(Company, company_id)
                if company is None:
                    with counter_lock:
                        skipped += 1
                        current_processed = processed
                        current_skipped = skipped
                        current_errors = errors
                    print(
                        f"[{current_processed}/{len(rows)}] missing company ticker={ticker} worker={worker_id} skipped={current_skipped} errors={current_errors}",
                        flush=True,
                    )
                    continue
                with sqlite_write_guard():
                    MACHINE._build_report(session, company, ticker)
                    session.commit()
                with counter_lock:
                    processed += 1
                    current_processed = processed
                    current_skipped = skipped
                    current_errors = errors
                if current_processed % 25 == 0 or current_processed == len(rows):
                    print(
                        f"[{current_processed}/{len(rows)}] rebuilt={current_processed} skipped={current_skipped} errors={current_errors} last={ticker} worker={worker_id}",
                        flush=True,
                    )
            except Exception as exc:
                session.rollback()
                with counter_lock:
                    errors += 1
                    current_processed = processed
                    current_skipped = skipped
                    current_errors = errors
                print(
                    f"[{current_processed}/{len(rows)}] error ticker={ticker} worker={worker_id} message={str(exc)[:300]} skipped={current_skipped} errors={current_errors}",
                    flush=True,
                )
            finally:
                session.close()

    threads = [
        threading.Thread(target=_worker, args=(index + 1,), daemon=True, name=f"report-card-worker-{index + 1}")
        for index in range(max(1, args.workers))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    ended = datetime.now(UTC)
    print(
        f"[{ended.isoformat()}] report-card rebuild completed "
        f"processed={processed} skipped={skipped} errors={errors} "
        f"duration_seconds={(ended - started).total_seconds():.1f}",
        flush=True,
    )
    engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill report_cards using the current report builder instead of the legacy thin-card mapper."
    )
    parser.add_argument("--reset", action="store_true", help="Delete existing report_cards first and fully rebuild them.")
    parser.add_argument("--ticker", type=str, help="Only rebuild one ticker.")
    parser.add_argument("--replace-ticker", type=str, help="Delete existing report_cards for one ticker, then rebuild it.")
    parser.add_argument("--limit", type=int, help="Maximum companies to rebuild.")
    parser.add_argument("--workers", type=int, default=3, help="Worker count for report-card rebuild.")
    return parser.parse_args()


def _reset_report_cards(factory) -> None:
    session = factory()
    try:
        existing = int(session.execute(select(func.count()).select_from(ReportCard)).scalar_one())
        print(f"[{datetime.now(UTC).isoformat()}] deleting existing report_cards rows={existing}", flush=True)
        with sqlite_write_guard():
            session.execute(delete(ReportCard))
            session.commit()
    finally:
        session.close()


def _reset_report_cards_for_ticker(factory, ticker: str) -> None:
    session = factory()
    try:
        normalized = ticker.upper()
        existing = int(
            session.execute(
                select(func.count()).select_from(ReportCard).where(ReportCard.ticker == normalized)
            ).scalar_one()
        )
        print(
            f"[{datetime.now(UTC).isoformat()}] deleting report_cards for ticker={normalized} rows={existing}",
            flush=True,
        )
        with sqlite_write_guard():
            session.execute(delete(ReportCard).where(ReportCard.ticker == normalized))
            session.commit()
    finally:
        session.close()


def _load_company_rows(factory, *, ticker: str | None, limit: int | None, missing_only: bool) -> list[tuple[object, str]]:
    session = factory()
    try:
        stmt = (
            select(Company.id, Security.ticker)
            .join(Security, Security.company_id == Company.id)
            .join(CompanyReport, CompanyReport.company_id == Company.id)
            .order_by(Security.ticker.asc())
        )
        if ticker:
            stmt = stmt.where(Security.ticker == ticker.upper())
        rows = [(company_id, symbol) for company_id, symbol in session.execute(stmt).all()]
        if missing_only:
            existing_company_ids = set(
                session.execute(select(ReportCard.company_id).distinct()).scalars().all()
            )
            rows = [row for row in rows if row[0] not in existing_company_ids]
        deduped: list[tuple[object, str]] = []
        seen_company_ids: set[object] = set()
        for company_id, symbol in rows:
            if company_id in seen_company_ids:
                continue
            seen_company_ids.add(company_id)
            deduped.append((company_id, symbol))
        if limit is not None:
            return deduped[: max(0, limit)]
        return deduped
    finally:
        session.close()


if __name__ == "__main__":
    main()
