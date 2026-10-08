from datetime import datetime

from accountant.db.models import Company, Filing, RawFact
from accountant.ingest.companyfacts import _ingest_single_fact, ingest_company_facts_payload


def test_original_inserted_after_restatement_keeps_own_first_reported_time(test_session):
    company = Company(cik="0000000123", name="Test")
    test_session.add(company)
    test_session.flush()
    original = Filing(company_id=company.id, accession_number="original",
                      form_type="10-K", filing_date=datetime(2025, 2, 1).date(), accepted_at=datetime(2025, 2, 1))
    restated = Filing(company_id=company.id, accession_number="restated",
                      form_type="10-K/A", filing_date=datetime(2025, 3, 1).date(), accepted_at=datetime(2025, 3, 1), is_amendment=True)
    test_session.add_all([original, restated])
    test_session.flush()
    for filing, value in [(restated, 110), (original, 100)]:
        assert _ingest_single_fact(test_session, str(company.id), company.cik, "us-gaap", "Assets", "Assets", "Assets", "USD", {
            "val": value, "accn": filing.accession_number, "filed": filing.filing_date.isoformat(),
            "end": "2024-12-31", "form": filing.form_type,
        })
    row = test_session.query(RawFact).filter(RawFact.accession_number == "original").one()
    assert row.first_reported_at == original.accepted_at
    assert row.first_reported_accession_number == "original"
    assert row.prior_version_fact_id is None


def test_missing_accession_is_explicit_payload_error(test_session):
    company = Company(cik="0000000123", name="Test")
    test_session.add(company)
    test_session.flush()
    _, inserted, _, errors = ingest_company_facts_payload(test_session, company, {
        "facts": {"us-gaap": {"Assets": {"units": {"USD": [
            {"val": 100, "accn": "missing", "end": "2024-12-31"},
        ]}}}},
    })
    assert inserted == 0
    assert len(errors) == 1
    assert "missing filing provenance" in errors[0]
