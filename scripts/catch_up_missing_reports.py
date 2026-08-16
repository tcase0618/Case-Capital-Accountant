from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from accountant.db import create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import Company, CompanyReport, Security
from accountant.research.report_machine import MACHINE


def main() -> None:
    engine = create_db_engine()
    factory = create_session_factory(engine)
    session = factory()
    try:
        rows = session.execute(
            select(Company.id, Security.ticker)
            .join(Security, Security.company_id == Company.id)
            .outerjoin(CompanyReport, CompanyReport.company_id == Company.id)
            .where(CompanyReport.id.is_(None))
            .order_by(Security.ticker.asc())
        ).all()
    finally:
        session.close()

    started = datetime.now(UTC)
    processed = 0
    errors = 0
    print(f"[{started.isoformat()}] catch-up missing reports companies={len(rows)}", flush=True)

    for index, (company_id, ticker) in enumerate(rows, start=1):
        session = factory()
        try:
            company = session.get(Company, company_id)
            if company is None:
                continue
            with sqlite_write_guard():
                MACHINE._process_company(session, company, ticker, worker_index=0)
                session.commit()
            processed += 1
            if index % 10 == 0 or index == len(rows):
                print(f"[{index}/{len(rows)}] processed={processed} errors={errors} last={ticker}", flush=True)
        except Exception as exc:
            session.rollback()
            errors += 1
            print(f"[{index}/{len(rows)}] error ticker={ticker} message={str(exc)[:240]}", flush=True)
        finally:
            session.close()

    ended = datetime.now(UTC)
    print(
        f"[{ended.isoformat()}] completed processed={processed} errors={errors} "
        f"duration_seconds={(ended - started).total_seconds():.1f}",
        flush=True,
    )
    engine.dispose()


if __name__ == "__main__":
    main()
