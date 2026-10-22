from __future__ import annotations

import argparse
import re
import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import func, select

from accountant.config import get_settings
from accountant.db import create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import Company, Filing, Security
from accountant.ingest.filings import FilingFetchPayload, ingest_company_filings_payload
from accountant.sec import SecClient
from accountant.sec.discovery_state import DiscoveryState, checkpoint_lock
from accountant.sec.rate_limit import RateLimiter

CORE_REPORT_FORMS = {
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
}
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


def main() -> int:
    args = _parse_args()
    engine = create_db_engine()
    factory = create_session_factory(engine)
    settings = get_settings()
    today = date.today()
    try:
        path = settings.data_dir / f"sec_discovery_{args.forms}.json"
        with checkpoint_lock(path):
            state = DiscoveryState(path)
            return _run_discovery(factory, state, args, today)
    finally:
        engine.dispose()


def _run_discovery(factory, state, args, today) -> int:
    settings = get_settings()
    dates = state.dates(
        today, _parse_date_arg(args.from_date), _parse_date_arg(args.to_date) or today
    )
    universe = _load_universe(factory)
    counters = ImportCounters()
    matched = []
    for day in dates:
        entry = state.entry(day)
        entry["attempts"] += 1
        entry["ok"] = False
        state.save(today)
        try:
            rows = _load_matching_daily_index_filings(
                day, day, universe, forms=_selected_forms(args.forms)
            )
            for row in rows:
                accession = _index_accession(row.filename)
                if accession not in entry["done"].get(row.cik, []):
                    pending = entry["pending"].setdefault(row.cik, [])
                    if accession not in pending:
                        pending.append(accession)
            entry["ok"] = True
            matched.extend(rows)
        except Exception as exc:
            counters.errors += 1
            print(f"daily-index failed date={day} error={str(exc)[:160]}", flush=True)
        state.save(today)

    expected: dict[str, set[str]] = {}
    for day, entry in state.days.items():
        if date.fromisoformat(day) > today:
            raise ValueError("future date in checkpoint")
        for cik, accessions in entry["pending"].items():
            expected.setdefault(cik, set()).update(accessions)
    attempts = state.data.setdefault("company_attempts", {})
    affected = sorted(expected, key=lambda cik: (attempts.get(cik, 0), cik))
    if args.limit is not None:
        affected = affected[: max(0, args.limit)]
    state.data["company_attempts"] = {
        cik: attempts.get(cik, 0) + int(cik in affected) for cik in expected
    }
    state.save(today)
    # All checkpoint writes are serialized, including worker completion callbacks.
    state_lock = threading.Lock()

    def completed(cik):
        with state_lock:
            for entry in state.days.values():
                accessions = entry["pending"].pop(cik, [])
                if accessions:
                    entry["done"][cik] = sorted(set(entry["done"].get(cik, [])) | set(accessions))
            state.data["company_attempts"].pop(cik, None)
            state.save(today)

    _import_affected_submissions(
        factory,
        affected,
        universe,
        workers=args.workers,
        counters=counters,
        min_interval_seconds=settings.sec_min_interval_seconds,
        expected=expected,
        completed=completed,
    )
    _print_summary(factory, counters, matched)
    failed_indexes = sum(not e["ok"] for e in state.days.values())
    pending_companies = sum(len(e["pending"]) for e in state.days.values())
    partial = bool(counters.errors or failed_indexes or pending_companies)
    print(
        f"discovery status={'PARTIAL' if partial else 'SUCCESS'} "
        f"failed_indexes={failed_indexes} pending_company_dates={pending_companies}",
        flush=True,
    )
    return int(partial)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import stale SEC filings for universe companies from daily indexes."
    )
    parser.add_argument("--from-date", help="First SEC filing date to inspect, YYYY-MM-DD.")
    parser.add_argument(
        "--to-date", help="Last SEC filing date to inspect, YYYY-MM-DD. Defaults to today."
    )
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
            universe.setdefault(
                str(cik).zfill(10), {"ticker": str(ticker).upper(), "name": str(name or ticker)}
            )
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
) -> list[IndexFiling]:
    settings = get_settings()
    headers = {
        "User-Agent": settings.sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "text/plain,*/*",
    }
    rows: list[IndexFiling] = []
    with httpx.Client(
        timeout=httpx.Timeout(settings.sec_timeout_seconds), headers=headers, follow_redirects=True
    ) as client:
        current = from_date
        while current <= to_date:
            url = _daily_master_url(current)
            try:
                response = client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise RuntimeError(f"daily index unavailable: {current}") from exc
            if "CIK|Company Name|Form Type|Date Filed|Filename" not in response.text:
                raise ValueError(f"invalid daily index: {current}")
            for row in _parse_master_idx(response.text):
                if row.filing_date != current or row.filing_date > date.today():
                    raise ValueError(f"invalid filing date in index: {row.filing_date}")
                if row.cik not in universe:
                    continue
                if forms is not None and row.form_type not in forms:
                    continue
                rows.append(row)
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
            raise ValueError("malformed daily index row")
        cik_raw, company_name, form_type, filed_raw, filename = [part.strip() for part in parts]
        if not cik_raw.isdigit():
            raise ValueError("invalid daily index CIK")
        filed = date.fromisoformat(filed_raw)
        _index_accession(filename)
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


def _index_accession(filename: str) -> str:
    match = re.search(r"/(\d{10}-\d{2}-\d{6})\.txt$", filename)
    if not match:
        raise ValueError("invalid index accession filename")
    return match.group(1)


def _existing_accessions(factory, cik, expected):
    with factory() as session:
        return set(
            session.execute(
                select(Filing.accession_number)
                .join(Company, Company.id == Filing.company_id)
                .where(Company.cik == cik, Filing.accession_number.in_(expected))
            ).scalars()
        )


def _required_shards(client, submissions, missing):
    recent = submissions.get("filings", {}).get("recent", {})
    missing = set(missing) - set(recent.get("accessionNumber", []))
    shards = []
    if missing:
        for entry in submissions.get("filings", {}).get("files", []):
            shard = client.get_submissions_file(entry["name"])
            shards.append(shard)
            missing -= set(shard.get("accessionNumber", []))
            if not missing:
                break
    if missing:
        raise ValueError(f"submissions missing {len(missing)} discovered accessions")
    return shards


def _import_affected_submissions(
    factory,
    affected_ciks: list[str],
    universe: dict[str, dict[str, str]],
    *,
    workers: int,
    counters: ImportCounters,
    min_interval_seconds: float,
    expected: dict[str, set[str]],
    completed,
) -> None:
    if not affected_ciks:
        return
    queue = deque(affected_ciks)
    queue_lock = threading.Lock()
    counter_lock = threading.Lock()
    shared_limiter = RateLimiter(min_interval_seconds)
    total = len(affected_ciks)

    def _worker(worker_id: int) -> None:
        with SecClient() as sec_client:
            sec_client._limiter = shared_limiter
            while True:
                with queue_lock:
                    if not queue:
                        return
                    cik = queue.popleft()
                info = universe.get(cik, {"ticker": "", "name": cik})
                session = factory()
                try:
                    missing = expected[cik] - _existing_accessions(factory, cik, expected[cik])
                    if not missing:
                        completed(cik)
                        continue
                    if cik not in universe:
                        raise ValueError("pending company no longer in universe")
                    submissions = sec_client.get_submissions(cik)
                    if str(submissions.get("cik", "")).zfill(10) != cik:
                        raise ValueError("submissions CIK does not match discovered company")
                    payload = FilingFetchPayload(
                        resolution_ticker=info["ticker"],
                        resolution_name=info["name"],
                        submissions=submissions,
                        historical_shards=_required_shards(sec_client, submissions, missing),
                    )
                    with sqlite_write_guard():
                        result = ingest_company_filings_payload(session, payload)
                        session.commit()
                    if expected[cik] - _existing_accessions(factory, cik, expected[cik]):
                        raise ValueError("committed filings do not cover discovered accessions")
                    completed(cik)
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

    threads = [
        threading.Thread(
            target=_worker, args=(index + 1,), daemon=True, name=f"stale-sec-import-{index + 1}"
        )
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
    raise SystemExit(main())
