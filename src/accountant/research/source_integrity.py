from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from accountant.db.models import Filing

SOURCE_INTEGRITY_VERSION = "SOURCE_INTEGRITY_V1"


def build_source_integrity_snapshot(session: Session) -> dict[str, Any]:
    """Fast source-trust snapshot for the command center.

    Large fact tables use Postgres planner estimates to avoid command-center stalls.
    Smaller coverage/source tables use exact counts.
    """

    bind = session.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    generated_at = datetime.now(UTC)

    company_count = _exact_scalar(session, "select count(*) from companies")
    filings_count = _estimated_count(session, "filings") if is_postgres else _exact_scalar(session, "select count(*) from filings")
    raw_fact_count = _estimated_count(session, "raw_facts") if is_postgres else _exact_scalar(session, "select count(*) from raw_facts")
    canonical_fact_count = (
        _estimated_count(session, "canonical_facts")
        if is_postgres
        else _exact_scalar(session, "select count(*) from canonical_facts")
    )
    statement_snapshot_count = _exact_scalar(session, "select count(*) from statement_snapshots")
    report_count = _exact_scalar(session, "select count(*) from company_reports")
    report_card_count = _exact_scalar(session, "select count(*) from report_cards")
    bottleneck_count = _exact_scalar(session, "select count(*) from company_bottleneck_snapshots")

    latest = session.execute(
        select(Filing.filing_date, Filing.accepted_at)
        .order_by(Filing.filing_date.desc(), Filing.accepted_at.desc())
        .limit(1)
    ).first()
    latest_filing_date = latest[0].isoformat() if latest and latest[0] else None
    latest_accepted_at = latest[1].isoformat() if latest and latest[1] else None
    days_since_latest = _days_since(latest_filing_date)

    raw_source_sample = _raw_fact_source_sample(session)
    price_sources = _group_count(
        session,
        """
        select coalesce(last_price_source, 'NONE') as key, count(*) as count
        from buy_board_candidates
        group by coalesce(last_price_source, 'NONE')
        order by count desc
        """,
    )
    market_quality = _group_count(
        session,
        """
        select coalesce(current_market_data_quality, 'NONE') as key, count(*) as count
        from buy_board_candidates
        group by coalesce(current_market_data_quality, 'NONE')
        order by count desc
        """,
    )

    report_coverage_pct = _pct(report_count, company_count)
    bottleneck_coverage_pct = _pct(bottleneck_count, report_count)
    canonical_to_raw_pct = _pct(canonical_fact_count, raw_fact_count)
    statement_to_report_pct = _pct(statement_snapshot_count, report_count)

    warnings: list[str] = []
    if latest_filing_date is None:
        warnings.append("No SEC filings are present.")
    elif days_since_latest is not None and days_since_latest > 2:
        warnings.append(f"Latest SEC filing date is {days_since_latest} days old.")
    if raw_source_sample and any(item["source"] != "companyfacts" for item in raw_source_sample):
        warnings.append("Raw fact sample includes non-CompanyFacts source types.")
    if report_coverage_pct < 95:
        warnings.append("Company report coverage is below 95%.")
    if bottleneck_coverage_pct < 95:
        warnings.append("Bottleneck cache coverage is below 95% of reports.")
    if canonical_to_raw_pct < 10:
        warnings.append("Canonical mapping coverage is below 10% of raw facts.")
    if not price_sources or all(item["source"] == "NONE" for item in price_sources):
        warnings.append("No buy-board market price source is currently populated.")

    source_grade = _source_grade(
        latest_days=days_since_latest,
        report_coverage_pct=report_coverage_pct,
        bottleneck_coverage_pct=bottleneck_coverage_pct,
        canonical_to_raw_pct=canonical_to_raw_pct,
        warnings=warnings,
    )

    return {
        "version": SOURCE_INTEGRITY_VERSION,
        "generated_at": generated_at.isoformat(),
        "source_grade": source_grade,
        "warnings": warnings,
        "sec": {
            "authority": "SEC EDGAR CompanyFacts / filings",
            "latest_filing_date": latest_filing_date,
            "latest_accepted_at": latest_accepted_at,
            "days_since_latest_filing": days_since_latest,
            "filings_count_estimate": filings_count,
            "raw_facts_count_estimate": raw_fact_count,
            "raw_fact_source_sample": raw_source_sample,
            "sec_first": bool(raw_source_sample and all(item["source"] == "companyfacts" for item in raw_source_sample)),
        },
        "coverage": {
            "companies": company_count,
            "canonical_facts_count_estimate": canonical_fact_count,
            "statement_snapshots": statement_snapshot_count,
            "company_reports": report_count,
            "report_cards": report_card_count,
            "bottleneck_snapshots": bottleneck_count,
            "report_coverage_pct": round(report_coverage_pct, 2),
            "bottleneck_coverage_pct": round(bottleneck_coverage_pct, 2),
            "canonical_to_raw_pct": round(canonical_to_raw_pct, 2),
            "statement_to_report_pct": round(statement_to_report_pct, 2),
        },
        "market_data": {
            "role": "supporting price/tradability data; not accountant source of truth",
            "price_sources": price_sources,
            "market_quality": market_quality,
        },
        "truth_policy": {
            "accounting_source_of_truth": "SEC EDGAR filings and SEC CompanyFacts/XBRL facts",
            "market_source_of_truth": "Alpaca Accountant where populated; otherwise unavailable",
            "execution_authority": "none in Accountant; trading terminal owns execution",
        },
    }


def _source_grade(
    *,
    latest_days: int | None,
    report_coverage_pct: float,
    bottleneck_coverage_pct: float,
    canonical_to_raw_pct: float,
    warnings: list[str],
) -> str:
    if latest_days is None or report_coverage_pct < 70 or bottleneck_coverage_pct < 70:
        return "FAILED"
    if latest_days > 7 or report_coverage_pct < 90 or canonical_to_raw_pct < 5:
        return "DEGRADED"
    if warnings:
        return "WATCH"
    return "STRONG"


def _exact_scalar(session: Session, sql: str) -> int:
    return int(session.execute(text(sql)).scalar() or 0)


def _estimated_count(session: Session, table_name: str) -> int:
    value = session.execute(
        text(
            """
            select greatest(reltuples::bigint, 0)
            from pg_class
            where relname = :table_name
            """
        ),
        {"table_name": table_name},
    ).scalar()
    return int(value or 0)


def _raw_fact_source_sample(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        text(
            """
            select source_type, count(*) as count
            from (
                select source_type
                from raw_facts
                limit 250000
            ) sample
            group by source_type
            order by count desc
            """
        )
    ).all()
    return [{"source": row[0] or "UNKNOWN", "sample_count": int(row[1])} for row in rows]


def _group_count(session: Session, sql: str) -> list[dict[str, Any]]:
    return [{"source": row[0], "count": int(row[1])} for row in session.execute(text(sql)).all()]


def _pct(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator) * 100.0


def _days_since(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return (datetime.now(UTC).date() - parsed).days
