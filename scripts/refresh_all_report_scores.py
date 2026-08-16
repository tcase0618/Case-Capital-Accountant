from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import func, select

from accountant.db import create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import Company, CompanyReport, Security
from accountant.research.report_machine import MACHINE


def main() -> None:
    engine = create_db_engine()
    factory = create_session_factory(engine)
    today = date.today().isoformat()
    started = datetime.now(UTC)

    session = factory()
    try:
        total_reports = int(session.execute(select(func.count()).select_from(CompanyReport)).scalar_one())
        stale_company_ids = session.execute(
            select(CompanyReport.company_id)
            .where(func.date(CompanyReport.updated_at) < today)
            .order_by(CompanyReport.updated_at.asc())
        ).scalars().all()
        rows: list[tuple[object, str]] = []
        seen_company_ids: set[object] = set()
        for company_id in stale_company_ids:
            if company_id in seen_company_ids:
                continue
            ticker = session.execute(
                select(Security.ticker)
                .where(Security.company_id == company_id)
                .order_by(Security.ticker.asc())
                .limit(1)
            ).scalar_one_or_none()
            if ticker is None:
                continue
            seen_company_ids.add(company_id)
            rows.append((company_id, ticker))
    finally:
        session.close()

    print(
        f"[{datetime.now(UTC).isoformat()}] starting resumable report refresh "
        f"remaining={len(rows)} total_reports={total_reports}",
        flush=True,
    )

    processed = 0
    errors = 0
    for index, (company_id, ticker) in enumerate(rows, start=1):
        session = factory()
        try:
            company = session.get(Company, company_id)
            if company is None:
                errors += 1
                print(f"[{index}/{len(rows)}] missing company ticker={ticker}", flush=True)
                continue
            with sqlite_write_guard():
                MACHINE._build_report(session, company, ticker)
                session.commit()
            processed += 1
            if index % 25 == 0 or index == len(rows):
                print(
                    f"[{index}/{len(rows)}] refreshed={processed} errors={errors} last={ticker}",
                    flush=True,
                )
        except Exception as exc:
            session.rollback()
            errors += 1
            print(f"[{index}/{len(rows)}] error ticker={ticker} message={str(exc)[:300]}", flush=True)
        finally:
            session.close()

    ended = datetime.now(UTC)
    duration = (ended - started).total_seconds()
    print(
        f"[{ended.isoformat()}] completed processed={processed} errors={errors} "
        f"duration_seconds={duration:.1f}",
        flush=True,
    )
    engine.dispose()


if __name__ == "__main__":
    main()
