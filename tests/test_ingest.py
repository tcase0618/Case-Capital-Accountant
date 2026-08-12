"""Tests for ingestion functionality."""

from datetime import date

import pytest
from sqlalchemy import select

from accountant.db.models import Company, Filing
from accountant.ingest.companies import upsert_company_and_securities
from accountant.ingest.filings import ingest_filings_from_submissions


class TestCompanyUpsert:
    """Test company and security upsert."""

    def test_upsert_new_company(self, test_session):
        """Upsert a new company."""
        submissions = {
            "cik": "320193",
            "name": "Apple Inc.",
            "entityType": "Large accelerated filer",
            "tickers": ["AAPL"],
            "exchanges": ["NASDAQ"],
        }
        company = upsert_company_and_securities(test_session, submissions)

        assert company.cik == "0000320193"
        assert company.name == "Apple Inc."
        assert len(company.securities) == 1
        assert company.securities[0].ticker == "AAPL"

    def test_upsert_existing_company_updates(self, test_session):
        """Upsert existing company updates fields."""
        submissions1 = {
            "cik": "320193",
            "name": "Apple Inc.",
            "entityType": "Large accelerated filer",
            "tickers": ["AAPL"],
            "exchanges": ["NASDAQ"],
        }
        company1 = upsert_company_and_securities(test_session, submissions1)
        company1_id = company1.id

        submissions2 = {
            "cik": "320193",
            "name": "Apple Computer Inc.",
            "entityType": "Accelerated filer",
            "tickers": ["AAPL"],
            "exchanges": ["NASDAQ"],
        }
        company2 = upsert_company_and_securities(test_session, submissions2)

        assert company2.id == company1_id
        assert company2.name == "Apple Computer Inc."
        assert company2.entity_type == "Accelerated filer"

    def test_upsert_with_fallback_ticker(self, test_session):
        """Fallback ticker is added if not in submissions."""
        submissions = {
            "cik": "320193",
            "name": "Apple Inc.",
            "tickers": [],
            "exchanges": [],
        }
        company = upsert_company_and_securities(
            test_session, submissions, fallback_ticker="AAPL"
        )

        assert len(company.securities) == 1
        assert company.securities[0].ticker == "AAPL"

    def test_upsert_missing_name_raises(self, test_session):
        """Missing company name raises error."""
        submissions = {
            "cik": "320193",
            "tickers": ["AAPL"],
        }
        with pytest.raises(ValueError, match="has no company name"):
            upsert_company_and_securities(test_session, submissions)


class TestFilingIngestion:
    """Test filing ingestion."""

    def test_ingest_filings_from_submissions(self, test_session):
        """Ingest filings from submissions data."""
        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        submissions = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-24-000001"],
                    "form": ["10-K"],
                    "filingDate": ["2024-01-15"],
                    "reportDate": ["2023-12-31"],
                    "primaryDocument": ["aapl-20231231.htm"],
                    "primaryDocDescription": ["Form 10-K"],
                    "isXBRL": [1],
                    "isInlineXBRL": [1],
                    "size": [10000],
                }
            }
        }

        result = ingest_filings_from_submissions(test_session, company, submissions)

        assert result.inserted == 1
        assert result.skipped == 0
        assert result.documents_inserted == 1

        filing = test_session.execute(
            select(Filing).where(Filing.accession_number == "0000320193-24-000001")
        ).scalar_one()
        assert filing.form_type == "10-K"
        assert filing.filing_date == date(2024, 1, 15)
        assert filing.is_xbrl is True
        assert filing.is_inline_xbrl is True

    def test_ingest_duplicate_accession_skipped(self, test_session):
        """Duplicate accession numbers are skipped."""
        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        filing1 = Filing(
            company_id=company.id,
            accession_number="0000320193-24-000001",
            form_type="10-K",
            filing_date=date(2024, 1, 15),
        )
        test_session.add(filing1)
        test_session.flush()

        submissions = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-24-000001"],
                    "form": ["10-K"],
                    "filingDate": ["2024-01-15"],
                    "primaryDocument": ["aapl-20231231.htm"],
                }
            }
        }

        result = ingest_filings_from_submissions(test_session, company, submissions)

        assert result.inserted == 0
        assert result.skipped == 1

    def test_ingest_missing_filing_date_skipped(self, test_session):
        """Filing without filing date is skipped."""
        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        submissions = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-24-000001"],
                    "form": ["10-K"],
                    "filingDate": [None],
                    "primaryDocument": ["aapl-20231231.htm"],
                }
            }
        }

        result = ingest_filings_from_submissions(test_session, company, submissions)

        assert result.inserted == 0
        assert result.skipped == 1

    def test_ingest_amendment_marked(self, test_session):
        """Form type with /A is marked as amendment."""
        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        submissions = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-24-000002"],
                    "form": ["10-K/A"],
                    "filingDate": ["2024-02-15"],
                    "primaryDocument": ["aapl-20240215.htm"],
                }
            }
        }

        ingest_filings_from_submissions(test_session, company, submissions)

        filing = test_session.execute(
            select(Filing).where(Filing.accession_number == "0000320193-24-000002")
        ).scalar_one()
        assert filing.is_amendment is True
