from __future__ import annotations

import argparse
import threading
from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from accountant.config import get_settings
from accountant.db import create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import Company, Filing, SecIndexCheckpoint, Security
from accountant.ingest.filings import FilingFetchPayload, ingest_company_filings_payload
from accountant.ops.storage_gate import StorageGate
from accountant.sec import SecClient
from accountant.sec.exceptions import SecHttpError
from accountant.sec.forms import CORE_REPORT_FORMS
from accountant.sec.rate_limit import RateLimiter

USEFUL_FORMS = CORE_REPORT_FORMS | {
    "8-K",
    "8-K/A",
    "4",
    "4/A",
    "3",
    "3/A",
    "5",
    "5/A",
    "144",
    "SC 13D",
    "SC 13D/A",
    "SC 13G",
    "SC 13G/A",
    "13F-HR",
    "13F-HR/A",
    "DEF 14A",
    "DEFA14A",
    "PRE 14A",
    "S-3",
    "S-3/A",
    "S-1",
    "S-1/A",
    "424B2",
    "424B3",
    "424B4",
    "424B5",
    "FWP",
    "NT 10-K",
    "NT 10-Q",
}


@dataclass(frozen=True)
class IndexFiling:
    cik: str
    company_name: str
    form_type: str
    filing_date: date
    filename: str


@dataclass
class ImportCounters:
    companies_processed: int = 0
    filings_inserted: int = 0
    filings_skipped: int = 0
    errors: int = 0


def main() -> None:
    args = _parse_args()
    engine = create_db_engine()
    factory = create_session_factory(engine)
    settings = get_settings()
    today = date.today()
    from_date = _parse_date_arg(args.from_date) or _next_index_date(factory, today)
    to_date = _parse_date_arg(args.to_date) or today
    if from_date > to_date:
        print(f"no import needed from_date={from_date.isoformat()} to_date={to_date.isoformat()}", flush=True)
        return

    universe = _load_universe(factory)
    forms = _selected_forms(args.forms)
    fetched_days: list[date] = []
    matched = _load_matching_daily_index_filings(
        from_date, to_date, universe, forms=forms, factory=factory, fetched_days=fetched_days,
    )
    affected_ciks = sorted({row.cik for row in matched})
    if args.limit:
        affected_ciks = affected_ciks[: max(0, args.limit)]
    form_counts = Counter(row.form_type for row in matched)
    print(
        f"[{datetime.now(UTC).isoformat()}] stale SEC import starting "
        f"from={from_date.isoformat()} to={to_date.isoformat()} "
        f"index_matches={len(matched)} affected_companies={len(affected_ciks)} "
        f"forms={','.join(f'{form}:{count}' for form, count in form_counts.most_common(12))}",
        flush=True,
    )

    counters = ImportCounters()
    _import_affected_submissions(
        factory,
        affected_ciks,
        universe,
        workers=args.workers,
        counters=counters,
        min_interval_seconds=settings.sec_min_interval_seconds,
    )
    _print_summary(factory, counters, matched)
    # Never advance completion for partial/failed company imports or a narrower
    # form selection. A crash after commits merely causes an idempotent replay.
    if not counters.errors and not args.limit and args.forms in {"useful", "all"}:
        with factory() as session:
            for day in fetched_days:
                checkpoint = session.get(SecIndexCheckpoint, day)
                checkpoint.status = "completed"
            session.commit()
    engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import stale SEC filings for universe companies from daily indexes.")
    parser.add_argument("--from-date", help="First SEC filing date to inspect, YYYY-MM-DD.")
    parser.add_argument("--to-date", help="Last SEC filing date to inspect, YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--workers", type=int, default=8, help="Parallel SEC submissions workers.")
    parser.add_argument("--limit", type=int, help="Limit affected companies, for smoke tests.")
    parser.add_argument(
        "--forms",
        choices=["core", "useful", "all"],
        default="useful",
        help="Daily-index forms used to choose affected companies. Submissions ingestion remains full recent metadata.",
    )
    return parser.parse_args()


def _parse_date_arg(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _next_index_date(factory, today: date) -> date:
    session = factory()
    try:
        latest = session.execute(select(func.max(SecIndexCheckpoint.index_date)).where(
            SecIndexCheckpoint.status == "completed",
        )).scalar_one_or_none()
        pending = session.execute(select(func.min(SecIndexCheckpoint.index_date)).where(
            SecIndexCheckpoint.status != "completed",
        )).scalar_one_or_none()
        start = latest or today - timedelta(days=30)
        # Always replay three business days, even if another writer has inserted
        # a future-dated filing or yesterday's master index was incomplete.
        business_days = 0
        while business_days < 3:
            start -= timedelta(days=1)
            business_days += start.weekday() < 5
        return min(start, pending) if pending else start
    finally:
        session.close()


def _load_universe(factory) -> dict[str, dict[str, str]]:
    session = factory()
    try:
        rows = session.execute(
            select(Company.cik, Company.name, Security.ticker)
            .join(Security, Security.company_id == Company.id)
            .where(Security.ticker.is_not(None))
        ).all()
        universe: dict[str, dict[str, str]] = {}
        for cik, name, ticker in rows:
            if not cik or not ticker:
                continue
            universe.setdefault(str(cik).zfill(10), {"ticker": str(ticker).upper(), "name": str(name or ticker)})
        return universe
    finally:
        session.close()


def _selected_forms(mode: str) -> set[str] | None:
    if mode == "all":
        return None
    if mode == "core":
        return CORE_REPORT_FORMS
    return USEFUL_FORMS


def _load_matching_daily_index_filings(
    from_date: date,
    to_date: date,
    universe: dict[str, dict[str, str]],
    *,
    forms: set[str] | None,
    factory=None,
    fetched_days: list[date] | None = None,
) -> list[IndexFiling]:
    settings = get_settings()
    rows: list[IndexFiling] = []
    with SecClient(settings=settings) as client:
        current = from_date
        while current <= to_date:
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            if factory is not None:
                with factory() as session:
                    checkpoint = session.get(SecIndexCheckpoint, current)
                    if checkpoint is None:
                        checkpoint = SecIndexCheckpoint(index_date=current)
                        session.add(checkpoint)
                    checkpoint.status = "pending"
                    session.commit()
            url = _daily_master_url(current)
            try:
                index_text = client.get_text(url)
                if "CIK|Company Name|Form Type|Date Filed|Filename" not in index_text:
                    raise ValueError("daily index is missing the master header")
            except (SecHttpError, ValueError) as exc:
                print(f"daily-index pending date={current.isoformat()} error={type(exc).__name__}", flush=True)
                current += timedelta(days=1)
                continue
            day_rows = []
            for row in _parse_master_idx(index_text):
                if row.cik not in universe:
                    continue
                if forms is not None and row.form_type not in forms:
                    continue
                day_rows.append(row)
            rows.extend(day_rows)
            if factory is not None:
                with factory() as session:
                    checkpoint = session.get(SecIndexCheckpoint, current)
                    checkpoint.fetched_at = datetime.now(UTC)
                    checkpoint.matched_rows = len(day_rows)
                    session.commit()
            if fetched_days is not None:
                fetched_days.append(current)
            current += timedelta(days=1)
    return rows


def _daily_master_url(day: date) -> str:
    quarter = ((day.month - 1) // 3) + 1
    return f"https://www.sec.gov/Archives/edgar/daily-index/{day.year}/QTR{quarter}/master.{day:%Y%m%d}.idx"


def _parse_master_idx(text: str) -> list[IndexFiling]:
    rows: list[IndexFiling] = []
    for line in text.splitlines():
        if "|" not in line or line.startswith("CIK|"):
            continue
        parts = line.split("|")
        if len(parts) != 5:
            continue
        cik_raw, company_name, form_type, filed_raw, filename = [part.strip() for part in parts]
        if not cik_raw.isdigit():
            continue
        try:
            filed = date.fromisoformat(filed_raw)
        except ValueError:
            continue
        rows.append(
            IndexFiling(
                cik=cik_raw.zfill(10),
                company_name=company_name,
                form_type=form_type,
                filing_date=filed,
                filename=filename,
            )
        )
    return rows


def _import_affected_submissions(
    factory,
    affected_ciks: list[str],
    universe: dict[str, dict[str, str]],
    *,
    workers: int,
    counters: ImportCounters,
    min_interval_seconds: float,
) -> None:
    queue = deque(affected_ciks)
    queue_lock = threading.Lock()
    counter_lock = threading.Lock()
    shared_limiter = RateLimiter(min_interval_seconds, state_path=get_settings().data_dir / "sec_rate_limit.sqlite3")
    storage_gate = StorageGate.from_settings(factory.kw["bind"])
    total = len(affected_ciks)

    def _worker(worker_id: int) -> None:
        with SecClient() as sec_client:
            sec_client._limiter = shared_limiter
            while True:
                with queue_lock:
                    if not queue:
                        return
                    cik = queue.popleft()
                info = universe[cik]
                session = factory()
                admitted = False
                try:
                    if not storage_gate.claim():
                        with counter_lock:
                            counters.errors += 1
                        return
                    admitted = True
                    submissions = sec_client.get_submissions(cik)
                    payload = FilingFetchPayload(
                        resolution_ticker=info["ticker"],
                        resolution_name=info["name"],
                        submissions=submissions,
                        historical_shards=[],
                    )
                    with sqlite_write_guard():
                        result = ingest_company_filings_payload(session, payload)
                        session.commit()
                    with counter_lock:
                        counters.companies_processed += 1
                        counters.filings_inserted += result.inserted
                        counters.filings_skipped += result.skipped
                        processed = counters.companies_processed
                        errors = counters.errors
                    if processed % 25 == 0 or processed == total:
                        print(
                            f"[import {processed}/{total}] inserted={counters.filings_inserted} "
                            f"skipped={counters.filings_skipped} errors={errors} last={info['ticker']} worker={worker_id}",
                            flush=True,
                        )
                except Exception as exc:
                    session.rollback()
                    with counter_lock:
                        counters.errors += 1
                        errors = counters.errors
                        processed = counters.companies_processed
                    print(
                        f"[import {processed}/{total}] error cik={cik} ticker={info['ticker']} "
                        f"worker={worker_id} message={str(exc)[:240]} errors={errors}",
                        flush=True,
                    )
                finally:
                    session.close()
                    if admitted:
                        storage_gate.release()

    threads = [
        threading.Thread(target=_worker, args=(index + 1,), daemon=True, name=f"stale-sec-import-{index + 1}")
        for index in range(max(1, workers))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def _print_summary(factory, counters: ImportCounters, matched: list[IndexFiling]) -> None:
    session = factory()
    try:
        latest_filing_date, latest_accepted_at = session.execute(
            select(func.max(Filing.filing_date), func.max(Filing.accepted_at))
        ).one()
    finally:
        session.close()
    print(
        f"[{datetime.now(UTC).isoformat()}] stale SEC import completed "
        f"index_matches={len(matched)} companies_processed={counters.companies_processed} "
        f"filings_inserted={counters.filings_inserted} filings_skipped={counters.filings_skipped} "
        f"errors={counters.errors} latest_filing_date={latest_filing_date} latest_accepted_at={latest_accepted_at}",
        flush=True,
    )


if __name__ == "__main__":
    main()
