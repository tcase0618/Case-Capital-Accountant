"""CompanyFacts ingestion and XBRL fact normalization."""

from __future__ import annotations

import contextlib
import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from accountant.db.models import Company, RawFact
from accountant.ingest.dates import parse_date
from accountant.logging import get_logger
from accountant.sec.companyfacts import CompanyFactsClient

log = get_logger(__name__)


@dataclass
class CompanyFactsIngestResult:
    """Result of CompanyFacts ingestion."""

    cik: str
    ticker: str
    company_name: str
    concepts_processed: int
    facts_inserted: int
    facts_skipped: int
    errors: list[str]


def compute_fact_hash(
    company_id: str,
    taxonomy: str,
    concept: str,
    accession: str,
    unit: str | None,
    start: str | None,
    end: str | None,
    instant: str | None,
    value: str | int | float,
) -> str:
    """Compute deterministic hash for fact identity.

    Distinguishes economically different facts based on:
    - Company
    - Taxonomy/concept
    - Accession (filing)
    - Unit
    - Period (start/end/instant)
    - Value (for amendments, restarts, or different reported values)
    """
    key_parts = [
        str(company_id),
        taxonomy,
        concept,
        accession,
        unit or "no-unit",
        start or "no-start",
        end or "no-end",
        instant or "no-instant",
        str(value),
    ]
    key = "|".join(key_parts)
    return hashlib.sha256(key.encode()).hexdigest()


def ingest_company_facts_for_company(
    session: Session,
    company: Company,
    companyfacts_client: CompanyFactsClient,
    sec_client: Any,
) -> CompanyFactsIngestResult:
    """Ingest CompanyFacts for a company.

    Args:
        session: Database session
        company: Company record
        companyfacts_client: CompanyFacts client
        sec_client: SEC client for metadata

    Returns:
        Ingestion result with counts
    """
    cik = company.cik
    ticker = "unknown"
    errors: list[str] = []
    concepts_processed = 0
    facts_inserted = 0
    facts_skipped = 0

    try:
        # Get ticker if available
        try:
            for sec in company.securities:
                ticker = sec.ticker
                break
        except Exception:
            pass

        # Fetch CompanyFacts
        log.info("companyfacts.ingest_start", cik=cik, ticker=ticker)
        facts_data = companyfacts_client.get_company_facts(cik)

        # Iterate taxonomies
        for taxonomy, concepts in facts_data.items():
            if taxonomy == "cik":
                continue
            if not isinstance(concepts, dict):
                continue

            # Iterate concepts
            for concept, concept_data in concepts.items():
                if not isinstance(concept_data, dict):
                    continue

                concepts_processed += 1
                label = concept_data.get("label", "")
                description = concept_data.get("description")
                units_data = concept_data.get("units", {})

                if not isinstance(units_data, dict):
                    continue

                # Iterate units for this concept
                for unit, facts_list in units_data.items():
                    if not isinstance(facts_list, list):
                        continue

                    for fact in facts_list:
                        try:
                            inserted = _ingest_single_fact(
                                session=session,
                                company_id=str(company.id),
                                company_cik=cik,
                                taxonomy=taxonomy,
                                concept=concept,
                                label=label,
                                description=description,
                                unit=unit,
                                fact_dict=fact,
                            )
                            if inserted:
                                facts_inserted += 1
                            else:
                                facts_skipped += 1
                        except Exception as e:
                            errors.append(
                                f"fact error (tax={taxonomy}, concept={concept}, "
                                f"unit={unit}): {str(e)[:100]}"
                            )

        log.info(
            "companyfacts.ingest_complete",
            cik=cik,
            ticker=ticker,
            concepts=concepts_processed,
            inserted=facts_inserted,
            skipped=facts_skipped,
            errors=len(errors),
        )

    except Exception as e:
        msg = f"CompanyFacts ingestion failed: {str(e)}"
        log.error("companyfacts.ingest_error", cik=cik, error=msg)
        errors.append(msg)

    return CompanyFactsIngestResult(
        cik=cik,
        ticker=ticker,
        company_name=company.name,
        concepts_processed=concepts_processed,
        facts_inserted=facts_inserted,
        facts_skipped=facts_skipped,
        errors=errors,
    )


def _ingest_single_fact(
    session: Session,
    company_id: str,
    company_cik: str,
    taxonomy: str,
    concept: str,
    label: str | None,
    description: str | None,
    unit: str,
    fact_dict: dict[str, Any],
) -> bool:
    """Ingest a single fact from CompanyFacts.

    Args:
        session: Database session
        company_id: Company UUID as string
        company_cik: Company 10-digit CIK
        taxonomy: Taxonomy (e.g., 'us-gaap')
        concept: Concept name
        label: Concept label
        description: Concept description
        unit: Unit (e.g., 'USD', 'shares')
        fact_dict: Fact data from CompanyFacts API

    Returns:
        True if fact was inserted, False if skipped (duplicate)
    """
    # Extract required fields
    value = fact_dict.get("val")
    accession = fact_dict.get("accn")
    form = fact_dict.get("form")
    filed_str = fact_dict.get("filed")
    frame = fact_dict.get("frame")

    # Extract period information
    start_str = fact_dict.get("start")
    end_str = fact_dict.get("end")
    instant_str = fact_dict.get("fy")  # 'fy' field if available in some responses

    # Parse dates
    start_date = parse_date(start_str) if start_str else None
    end_date = parse_date(end_str) if end_str else None
    instant_date = parse_date(instant_str) if instant_str else None
    filed_date = parse_date(filed_str) if filed_str else None

    # Determine primary period (end or instant)
    period_end = end_date or instant_date

    # Extract optional metadata
    decimals_raw = fact_dict.get("decimals")
    decimals = int(decimals_raw) if decimals_raw is not None else None

    # Parse fiscal year and period from 'fy' field or frame
    fiscal_year = None
    fiscal_period = "FY"  # default to annual

    frame_str = frame or ""
    if frame_str:
        # Frame format: CY2023Q1, CY2023, etc.
        if "Q" in frame_str:
            fiscal_period = frame_str.split("Q")[-1] if "Q" in frame_str else "FY"
            with contextlib.suppress(ValueError):
                fiscal_year = int(frame_str.split("Q")[0].replace("CY", ""))
        else:
            with contextlib.suppress(ValueError):
                fiscal_year = int(frame_str.replace("CY", ""))

    # Compute value fields
    value_numeric = None
    value_text = None
    if value is not None:
        try:
            value_numeric = float(value)
        except (ValueError, TypeError):
            value_text = str(value)

    # Compute fact hash for deduplication
    fact_hash = compute_fact_hash(
        company_id=company_id,
        taxonomy=taxonomy,
        concept=concept,
        accession=accession or "unknown",
        unit=unit,
        start=start_str,
        end=end_str,
        instant=instant_str,
        value=value or "none",
    )

    # Check for duplicate
    existing = session.query(RawFact).filter(RawFact.fact_hash == fact_hash).first()
    if existing:
        return False  # Duplicate, skip

    # Find filing if accession is known
    filing_id = None
    if accession:
        from accountant.db.models import Filing

        filing = (
            session.query(Filing)
            .filter(Filing.accession_number == accession)
            .filter(Filing.company_id == company_id)
            .first()
        )
        if filing:
            filing_id = filing.id

    # Insert fact
    raw_fact = RawFact(
        id=uuid.uuid4(),
        filing_id=filing_id or uuid.uuid4(),  # If no filing, use a temporary UUID (will be RESTRICT anyway)
        company_id=uuid.UUID(company_id),
        concept=concept,
        taxonomy=taxonomy,
        unit=unit,
        period_start=start_date,
        period_end=period_end,
        instant_date=instant_date,
        decimals=decimals,
        value_numeric=value_numeric,
        value_text=value_text,
        fact_hash=fact_hash,
        accession_number=accession,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        frame=frame,
        form=form,
        filed_date=filed_date,
        label=label,
        description=description,
        source_type="companyfacts",
    )

    # Only insert if we have a valid filing_id
    if filing_id:
        raw_fact.filing_id = filing_id
        session.add(raw_fact)
        session.flush()
        return True
    else:
        # Skip fact without a linked filing for now
        return False


def query_facts(
    session: Session,
    company_id: str,
    concept: str | None = None,
    taxonomy: str | None = None,
    form: str | None = None,
    limit: int = 100,
) -> list[RawFact]:
    """Query raw facts with filters.

    Args:
        session: Database session
        company_id: Company UUID
        concept: Optional concept filter
        taxonomy: Optional taxonomy filter
        form: Optional form type filter
        limit: Result limit

    Returns:
        List of RawFact records
    """
    query = session.query(RawFact).filter(RawFact.company_id == uuid.UUID(company_id))

    if concept:
        query = query.filter(RawFact.concept == concept)
    if taxonomy:
        query = query.filter(RawFact.taxonomy == taxonomy)
    if form:
        query = query.filter(RawFact.form == form)

    return query.order_by(RawFact.period_end.desc(), RawFact.created_at.desc()).limit(limit).all()
