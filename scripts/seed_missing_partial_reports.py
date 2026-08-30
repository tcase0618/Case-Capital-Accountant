from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from accountant.db import create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import Company, CompanyReport, Security


def main() -> None:
    engine = create_db_engine()
    factory = create_session_factory(engine)
    session = factory()
    try:
        rows = (
            session.execute(
                select(
                    Company.id,
                    Company.name,
                    func.min(Security.ticker),
                )
                .join(Security, Security.company_id == Company.id)
                .outerjoin(CompanyReport, CompanyReport.company_id == Company.id)
                .where(CompanyReport.id.is_(None))
                .group_by(Company.id, Company.name)
                .order_by(func.min(Security.ticker).asc())
            )
            .all()
        )
    finally:
        session.close()

    started = datetime.now(UTC)
    processed = 0
    errors = 0
    print(f"[{started.isoformat()}] skeletal report seeding starting companies={len(rows)}", flush=True)

    for index, (company_id, company_name, ticker) in enumerate(rows, start=1):
        session = factory()
        try:
            report = CompanyReport(
                company_id=company_id,
                ticker=ticker,
                company_name=company_name,
                as_of_date=datetime.now(UTC).date().isoformat(),
                stance="NEUTRAL",
                bullish_score=35.0,
                bearish_score=65.0,
                composite_score=35.0,
                data_quality_tier="PARTIAL",
                pipeline_stage="seeded",
                latest_filing_date=None,
                current_price=None,
                key_stats={
                    "filings_count": 0,
                    "raw_facts_count": 0,
                    "canonical_facts_count": 0,
                    "overall_coverage_pct": 5.0,
                    "accounting_quality_score": 35.0,
                    "future_bucket": "HOLD",
                    "future_reason": "Awaiting accountant deep pass.",
                },
                highlights=[
                    "Universe coverage row seeded for deadline-driven catch-up.",
                    "Deep accountant enrichment will continue in the background.",
                ],
                report_markdown=(
                    f"# {ticker} SEEDED REPORT\n\n"
                    f"{company_name} has been seeded for pipeline coverage. "
                    "The deeper accountant pass will upgrade this row."
                ),
                source_versions={"report_machine": "V2_SKELETAL_SEED"},
            )
            with sqlite_write_guard():
                session.add(report)
                session.commit()
            processed += 1
            if processed % 100 == 0 or processed == len(rows):
                print(
                    f"[{index}/{len(rows)}] seeded={processed} errors={errors} last={ticker}",
                    flush=True,
                )
        except Exception as exc:
            session.rollback()
            errors += 1
            print(f"[{index}/{len(rows)}] error ticker={ticker} message={str(exc)[:300]}", flush=True)
        finally:
            session.close()

    ended = datetime.now(UTC)
    print(
        f"[{ended.isoformat()}] skeletal report seeding completed "
        f"processed={processed} errors={errors} duration_seconds={(ended - started).total_seconds():.1f}",
        flush=True,
    )
    engine.dispose()


if __name__ == "__main__":
    main()
