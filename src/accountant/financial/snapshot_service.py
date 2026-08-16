from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from accountant.db.models import (
    CanonicalConcept,
    CanonicalFact,
    RawFact,
    StatementLine,
    StatementSnapshot,
)


@dataclass(frozen=True)
class StatementBuildSummary:
    snapshots_upserted: int = 0
    lines_written: int = 0


_INCOME_CONCEPTS = [
    "CC_REVENUE",
    "CC_COST_OF_REVENUE",
    "CC_GROSS_PROFIT",
    "CC_OPERATING_EXPENSES",
    "CC_OPERATING_INCOME",
    "CC_INTEREST_EXPENSE",
    "CC_INCOME_TAX_EXPENSE",
    "CC_NET_INCOME",
    "CC_WEIGHTED_SHARES_BASIC",
    "CC_WEIGHTED_SHARES_DILUTED",
    "CC_EPS",
    "CC_EPS_DILUTED",
]

_BALANCE_CONCEPTS = [
    "CC_ASSETS",
    "CC_CURRENT_ASSETS",
    "CC_CASH",
    "CC_SHORT_TERM_INVESTMENTS",
    "CC_ACCOUNTS_RECEIVABLE",
    "CC_INVENTORY",
    "CC_PPE",
    "CC_GOODWILL",
    "CC_INTANGIBLE_ASSETS",
    "CC_LIABILITIES",
    "CC_CURRENT_LIABILITIES",
    "CC_SHORT_TERM_DEBT",
    "CC_LONG_TERM_DEBT",
    "CC_LEASE_LIABILITIES",
    "CC_SHAREHOLDERS_EQUITY",
]

_CASHFLOW_CONCEPTS = [
    "CC_OPERATING_CASH_FLOW",
    "CC_INVESTING_CASH_FLOW",
    "CC_FINANCING_CASH_FLOW",
    "CC_CAPITAL_EXPENDITURES",
    "CC_DEPRECIATION_AMORTIZATION",
    "CC_STOCK_BASED_COMPENSATION",
    "CC_DIVIDENDS",
    "CC_SHARE_REPURCHASES",
]


def build_company_statement_snapshots(session: Session, company_id: Any) -> StatementBuildSummary:
    summaries = [
        _upsert_statement_snapshot(
            session,
            company_id,
            statement_type="income",
            concept_codes=_INCOME_CONCEPTS,
            required_codes=["CC_REVENUE", "CC_NET_INCOME"],
            builder_version="INCOME_STATEMENT_BUILDER_V1",
            resolver_version="CANONICAL_PERIOD_PICKER_V1",
            use_instant=False,
        ),
        _upsert_statement_snapshot(
            session,
            company_id,
            statement_type="balance",
            concept_codes=_BALANCE_CONCEPTS,
            required_codes=["CC_ASSETS", "CC_LIABILITIES", "CC_SHAREHOLDERS_EQUITY"],
            builder_version="BALANCE_SHEET_BUILDER_V1",
            resolver_version="CANONICAL_PERIOD_PICKER_V1",
            use_instant=True,
        ),
        _upsert_statement_snapshot(
            session,
            company_id,
            statement_type="cashflow",
            concept_codes=_CASHFLOW_CONCEPTS,
            required_codes=["CC_OPERATING_CASH_FLOW"],
            builder_version="CASH_FLOW_STATEMENT_BUILDER_V1",
            resolver_version="CANONICAL_PERIOD_PICKER_V1",
            use_instant=False,
        ),
    ]
    return StatementBuildSummary(
        snapshots_upserted=sum(item.snapshots_upserted for item in summaries),
        lines_written=sum(item.lines_written for item in summaries),
    )


def _upsert_statement_snapshot(
    session: Session,
    company_id: Any,
    *,
    statement_type: str,
    concept_codes: list[str],
    required_codes: list[str],
    builder_version: str,
    resolver_version: str,
    use_instant: bool,
) -> StatementBuildSummary:
    rows = session.execute(
        select(CanonicalFact, CanonicalConcept, RawFact)
        .join(CanonicalConcept, CanonicalConcept.id == CanonicalFact.canonical_concept_id)
        .join(RawFact, RawFact.id == CanonicalFact.raw_fact_id)
        .where(
            CanonicalFact.company_id == company_id,
            CanonicalConcept.code.in_(concept_codes),
            CanonicalFact.value_numeric.is_not(None),
        )
        .order_by(
            RawFact.fiscal_year.desc(),
            RawFact.period_end.desc(),
            RawFact.instant_date.desc(),
            RawFact.filed_date.desc(),
            CanonicalFact.created_at.desc(),
        )
    ).all()
    if not rows:
        return StatementBuildSummary()

    selected_period = _pick_period(rows, use_instant=use_instant)
    if selected_period is None:
        return StatementBuildSummary()

    fiscal_year, fiscal_quarter, period_type, end_or_instant = selected_period
    filtered = [
        row for row in rows
        if _row_matches_period(row[2], use_instant, fiscal_year, fiscal_quarter, period_type, end_or_instant)
    ]
    if not filtered:
        return StatementBuildSummary()

    existing = session.execute(
        select(StatementSnapshot).where(
            StatementSnapshot.company_id == company_id,
            StatementSnapshot.statement_type == statement_type,
            StatementSnapshot.fiscal_year == fiscal_year,
            StatementSnapshot.fiscal_quarter == fiscal_quarter,
        )
    ).scalar_one_or_none()
    if existing is None:
        snapshot = StatementSnapshot(
            company_id=company_id,
            statement_type=statement_type,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            builder_version=builder_version,
            mapping_version=1,
            resolver_version=resolver_version,
        )
        session.add(snapshot)
        session.flush()
    else:
        snapshot = existing
        session.execute(delete(StatementLine).where(StatementLine.snapshot_id == snapshot.id))

    if use_instant:
        snapshot.period_type = "INSTANT"
        snapshot.instant_date = end_or_instant
        snapshot.start_date = None
        snapshot.end_date = None
    else:
        snapshot.period_type = period_type
        snapshot.end_date = end_or_instant
        snapshot.instant_date = None
        snapshot.start_date = None

    lines_written = 0
    seen_codes: set[str] = set()
    source_accessions: list[str] = []
    for canonical_fact, concept, raw_fact in filtered:
        if concept.code in seen_codes:
            continue
        seen_codes.add(concept.code)
        if raw_fact.accession_number and raw_fact.accession_number not in source_accessions:
            source_accessions.append(raw_fact.accession_number)
        session.add(
            StatementLine(
                snapshot_id=snapshot.id,
                company_id=company_id,
                canonical_concept=concept.code,
                canonical_concept_id=concept.id,
                value_numeric=float(canonical_fact.value_numeric) if canonical_fact.value_numeric is not None else None,
                value_text=canonical_fact.value,
                unit=canonical_fact.unit,
                canonical_fact_id=canonical_fact.id,
                raw_fact_id=raw_fact.id,
                filing_id=raw_fact.filing_id,
                accession_number=raw_fact.accession_number,
                raw_taxonomy=raw_fact.taxonomy,
                raw_concept=raw_fact.concept,
                mapping_version=canonical_fact.mapping_version,
                resolver_version=resolver_version,
                reported_or_derived=canonical_fact.reported_or_derived,
                mapping_confidence=canonical_fact.mapping_confidence,
                selection_status="SELECTED",
            )
        )
        lines_written += 1

    completeness = (sum(1 for code in required_codes if code in seen_codes) / len(required_codes)) if required_codes else 1.0
    snapshot.source_accessions = source_accessions
    snapshot.primary_accession = source_accessions[0] if source_accessions else None
    snapshot.completeness = round(completeness, 4)
    snapshot.quality_status = "PASS" if completeness >= 1.0 else "WARNING" if completeness > 0 else "INSUFFICIENT_DATA"
    snapshot.warnings = None if completeness >= 1.0 else [f"Missing required concepts for {statement_type} snapshot."]
    return StatementBuildSummary(snapshots_upserted=1, lines_written=lines_written)


def _pick_period(rows: list[tuple[CanonicalFact, CanonicalConcept, RawFact]], *, use_instant: bool) -> tuple[int, int | None, str, date | None] | None:
    for _, _, raw_fact in rows:
        fiscal_year = raw_fact.fiscal_year
        if fiscal_year is None:
            continue
        if use_instant:
            instant_date = raw_fact.instant_date or raw_fact.period_end
            if instant_date is None:
                continue
            return fiscal_year, _parse_fiscal_quarter(raw_fact.fiscal_period), "INSTANT", instant_date
        period_end = raw_fact.period_end
        if period_end is None:
            continue
        fiscal_period = raw_fact.fiscal_period or "FY"
        return fiscal_year, _parse_fiscal_quarter(fiscal_period), fiscal_period, period_end
    return None


def _row_matches_period(
    raw_fact: RawFact,
    use_instant: bool,
    fiscal_year: int,
    fiscal_quarter: int | None,
    period_type: str,
    end_or_instant: date | None,
) -> bool:
    if raw_fact.fiscal_year != fiscal_year:
        return False
    if _parse_fiscal_quarter(raw_fact.fiscal_period) != fiscal_quarter:
        return False
    if use_instant:
        return (raw_fact.instant_date or raw_fact.period_end) == end_or_instant
    return raw_fact.period_end == end_or_instant and (raw_fact.fiscal_period or "FY") == period_type


def _parse_fiscal_quarter(fiscal_period: str | None) -> int | None:
    if not fiscal_period:
        return None
    upper = fiscal_period.upper()
    if upper.startswith("Q") and len(upper) >= 2 and upper[1].isdigit():
        return int(upper[1])
    return None
