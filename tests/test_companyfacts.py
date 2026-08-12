"""Tests for CompanyFacts ingestion and XBRL facts."""

from datetime import date
from unittest.mock import patch

import pytest

from accountant.db.models import Company, Filing, RawFact
from accountant.ingest.companyfacts import (
    compute_fact_hash,
    ingest_company_facts_for_company,
    query_facts,
)
from accountant.sec.companyfacts import CompanyFactsClient


class TestFactHashing:
    """Test fact hash computation for deduplication."""

    def test_identical_facts_same_hash(self):
        """Identical facts should produce same hash."""
        hash1 = compute_fact_hash(
            company_id="company-1",
            taxonomy="us-gaap",
            concept="Assets",
            accession="0000320193-24-000001",
            unit="USD",
            start=None,
            end="2023-12-31",
            instant=None,
            value=1000000,
        )
        hash2 = compute_fact_hash(
            company_id="company-1",
            taxonomy="us-gaap",
            concept="Assets",
            accession="0000320193-24-000001",
            unit="USD",
            start=None,
            end="2023-12-31",
            instant=None,
            value=1000000,
        )
        assert hash1 == hash2

    def test_different_concepts_different_hash(self):
        """Different concepts should produce different hashes."""
        hash1 = compute_fact_hash(
            company_id="company-1",
            taxonomy="us-gaap",
            concept="Assets",
            accession="0000320193-24-000001",
            unit="USD",
            start=None,
            end="2023-12-31",
            instant=None,
            value=1000000,
        )
        hash2 = compute_fact_hash(
            company_id="company-1",
            taxonomy="us-gaap",
            concept="Liabilities",
            accession="0000320193-24-000001",
            unit="USD",
            start=None,
            end="2023-12-31",
            instant=None,
            value=1000000,
        )
        assert hash1 != hash2

    def test_different_units_different_hash(self):
        """Different units should produce different hashes."""
        hash1 = compute_fact_hash(
            company_id="company-1",
            taxonomy="us-gaap",
            concept="SharesOutstanding",
            accession="0000320193-24-000001",
            unit="shares",
            start=None,
            end="2023-12-31",
            instant=None,
            value=1000000,
        )
        hash2 = compute_fact_hash(
            company_id="company-1",
            taxonomy="us-gaap",
            concept="SharesOutstanding",
            accession="0000320193-24-000001",
            unit="USD",
            start=None,
            end="2023-12-31",
            instant=None,
            value=1000000,
        )
        assert hash1 != hash2

    def test_different_values_different_hash(self):
        """Different values should produce different hashes."""
        hash1 = compute_fact_hash(
            company_id="company-1",
            taxonomy="us-gaap",
            concept="Assets",
            accession="0000320193-24-000001",
            unit="USD",
            start=None,
            end="2023-12-31",
            instant=None,
            value=1000000,
        )
        hash2 = compute_fact_hash(
            company_id="company-1",
            taxonomy="us-gaap",
            concept="Assets",
            accession="0000320193-24-000001",
            unit="USD",
            start=None,
            end="2023-12-31",
            instant=None,
            value=2000000,
        )
        assert hash1 != hash2


class TestCompanyFactsClient:
    """Test CompanyFacts client."""

    def test_client_initialization(self, test_settings):
        """Client initializes with settings."""
        client = CompanyFactsClient(test_settings)
        assert client is not None
        client.close()

    def test_client_context_manager(self, test_settings):
        """Client works as context manager."""
        with CompanyFactsClient(test_settings) as client:
            assert client is not None

    def test_cik_without_leading_zeros(self, test_settings):
        """SecClient converts CIK without leading zeros correctly."""
        from accountant.sec.client import SecClient

        client = SecClient(settings=test_settings)
        assert client.cik_without_leading_zeros("0000320193") == "320193"
        assert client.cik_without_leading_zeros(320193) == "320193"
        client.close()


class TestFactIngest:
    """Test raw fact ingestion."""

    def test_ingest_company_facts_creates_result(self, test_session, test_settings):
        """Ingestion returns result with counts."""
        # Create company and filing
        company = Company(
            cik="0000320193",
            name="Apple Inc.",
        )
        test_session.add(company)
        test_session.flush()

        filing = Filing(
            company_id=company.id,
            accession_number="0000320193-24-000001",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
        )
        test_session.add(filing)
        test_session.flush()

        # Mock CompanyFacts response
        mock_facts_data = {
            "cik": 320193,
            "us-gaap": {
                "Assets": {
                    "label": "Assets",
                    "description": "Total assets",
                    "units": {
                        "USD": [
                            {
                                "val": 1000000,
                                "accn": "0000320193-24-000001",
                                "form": "10-K",
                                "filed": "2024-01-31",
                                "end": "2023-12-31",
                                "decimals": -6,
                            }
                        ]
                    },
                }
            },
        }

        companyfacts_client = CompanyFactsClient(test_settings)
        sec_client_mock = type("obj", (object,), {"cik_without_leading_zeros": lambda x: "320193"})()

        with patch.object(
            companyfacts_client, "get_company_facts", return_value=mock_facts_data
        ):
            result = ingest_company_facts_for_company(
                test_session, company, companyfacts_client, sec_client_mock
            )

        assert result.cik == "0000320193"
        assert result.company_name == "Apple Inc."
        assert result.concepts_processed > 0
        assert result.facts_inserted >= 0

        companyfacts_client.close()

    def test_fact_query_filters(self, test_session):
        """Query facts supports filtering."""
        # Create test data
        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        filing = Filing(
            company_id=company.id,
            accession_number="0000320193-24-000001",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
        )
        test_session.add(filing)
        test_session.flush()

        # Create facts
        fact1 = RawFact(
            filing_id=filing.id,
            company_id=company.id,
            concept="Assets",
            taxonomy="us-gaap",
            unit="USD",
            period_end=date(2023, 12, 31),
            value_numeric=1000000,
            fact_hash="hash1",
            form="10-K",
            source_type="companyfacts",
        )
        fact2 = RawFact(
            filing_id=filing.id,
            company_id=company.id,
            concept="Liabilities",
            taxonomy="us-gaap",
            unit="USD",
            period_end=date(2023, 12, 31),
            value_numeric=500000,
            fact_hash="hash2",
            form="10-K",
            source_type="companyfacts",
        )
        test_session.add_all([fact1, fact2])
        test_session.flush()

        # Query without filters
        all_facts = query_facts(test_session, company_id=str(company.id))
        assert len(all_facts) == 2

        # Query with concept filter
        assets_facts = query_facts(test_session, company_id=str(company.id), concept="Assets")
        assert len(assets_facts) == 1
        assert assets_facts[0].concept == "Assets"

        # Query with taxonomy filter
        gaap_facts = query_facts(test_session, company_id=str(company.id), taxonomy="us-gaap")
        assert len(gaap_facts) == 2

        # Query with form filter
        form_facts = query_facts(test_session, company_id=str(company.id), form="10-K")
        assert len(form_facts) == 2

    def test_duplicate_facts_skipped(self, test_session):
        """Duplicate facts are not re-inserted."""
        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        filing = Filing(
            company_id=company.id,
            accession_number="0000320193-24-000001",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
        )
        test_session.add(filing)
        test_session.flush()

        # Insert first fact
        fact_hash = compute_fact_hash(
            company_id=str(company.id),
            taxonomy="us-gaap",
            concept="Assets",
            accession="0000320193-24-000001",
            unit="USD",
            start=None,
            end="2023-12-31",
            instant=None,
            value=1000000,
        )

        fact1 = RawFact(
            filing_id=filing.id,
            company_id=company.id,
            concept="Assets",
            taxonomy="us-gaap",
            unit="USD",
            period_end=date(2023, 12, 31),
            value_numeric=1000000,
            fact_hash=fact_hash,
            form="10-K",
            source_type="companyfacts",
        )
        test_session.add(fact1)
        test_session.flush()

        # Verify duplicate is found
        existing = test_session.query(RawFact).filter(RawFact.fact_hash == fact_hash).first()
        assert existing is not None

    def test_facts_immutable(self, test_session):
        """Raw facts cannot be updated."""
        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        filing = Filing(
            company_id=company.id,
            accession_number="0000320193-24-000001",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
        )
        test_session.add(filing)
        test_session.flush()

        fact = RawFact(
            filing_id=filing.id,
            company_id=company.id,
            concept="Assets",
            taxonomy="us-gaap",
            unit="USD",
            period_end=date(2023, 12, 31),
            value_numeric=1000000,
            fact_hash="hash1",
            form="10-K",
            source_type="companyfacts",
        )
        test_session.add(fact)
        test_session.flush()

        # Attempt update should raise
        fact.value_numeric = 2000000
        with pytest.raises(RuntimeError, match="immutable"):
            test_session.flush()
