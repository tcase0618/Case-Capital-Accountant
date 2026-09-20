from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from accountant.analysis.point_in_time_engine import PointInTimeResolver
from accountant.db.models import Company, Filing, RawFact


def test_resolve_raw_facts_can_return_latest_or_first_reported_version(test_session) -> None:
    company = Company(id=uuid.uuid4(), cik="0000320193", name="Apple Inc.")
    test_session.add(company)
    test_session.flush()

    filing_original = Filing(
        id=uuid.uuid4(),
        company_id=company.id,
        accession_number="0000320193-24-000001",
        form_type="10-K",
        filing_date=date(2024, 2, 1),
        accepted_at=datetime.fromisoformat("2024-02-01T16:30:00"),
    )
    filing_amendment = Filing(
        id=uuid.uuid4(),
        company_id=company.id,
        accession_number="0000320193-24-000002",
        form_type="10-K/A",
        filing_date=date(2024, 3, 15),
        accepted_at=datetime.fromisoformat("2024-03-15T16:30:00"),
        is_amendment=True,
    )
    test_session.add_all([filing_original, filing_amendment])
    test_session.flush()

    lineage_hash = "lineage-assets-2023"
    first_reported_at = filing_original.accepted_at

    test_session.add_all(
        [
            RawFact(
                id=uuid.uuid4(),
                filing_id=filing_original.id,
                company_id=company.id,
                concept="Assets",
                taxonomy="us-gaap",
                unit="USD",
                period_end=date(2023, 12, 31),
                value_numeric=Decimal("100.0"),
                fact_hash="hash-original",
                accession_number=filing_original.accession_number,
                accepted_at=filing_original.accepted_at,
                filed_date=filing_original.filing_date,
                lineage_hash=lineage_hash,
                lineage_version=1,
                prior_version_fact_id=None,
                first_reported_at=first_reported_at,
                first_reported_accession_number=filing_original.accession_number,
                is_amendment_fact=False,
                source_type="companyfacts",
            ),
            RawFact(
                id=uuid.uuid4(),
                filing_id=filing_amendment.id,
                company_id=company.id,
                concept="Assets",
                taxonomy="us-gaap",
                unit="USD",
                period_end=date(2023, 12, 31),
                value_numeric=Decimal("110.0"),
                fact_hash="hash-amended",
                accession_number=filing_amendment.accession_number,
                accepted_at=filing_amendment.accepted_at,
                filed_date=filing_amendment.filing_date,
                lineage_hash=lineage_hash,
                lineage_version=2,
                prior_version_fact_id=None,
                first_reported_at=first_reported_at,
                first_reported_accession_number=filing_original.accession_number,
                is_amendment_fact=True,
                source_type="companyfacts",
            ),
        ]
    )
    test_session.commit()

    latest = PointInTimeResolver.resolve_raw_facts(
        test_session,
        "0000320193",
        "2024-03-20",
        concept="Assets",
        prefer="latest_available",
    )
    first = PointInTimeResolver.resolve_raw_facts(
        test_session,
        "0000320193",
        "2024-03-20",
        concept="Assets",
        prefer="first_reported",
    )

    assert len(latest) == 1
    assert len(first) == 1
    assert latest[0].value == Decimal("110.0000000000")
    assert first[0].value == Decimal("100.0000000000")
    assert latest[0].first_reported_accession_number == filing_original.accession_number
    assert latest[0].lineage_version == 2
    assert first[0].lineage_version == 1
