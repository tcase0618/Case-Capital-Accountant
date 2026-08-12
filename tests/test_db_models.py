"""Tests for database models."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from accountant.db.models import Company, Filing, FilingDocument, Security


class TestCompanyModel:
    """Test Company model."""

    def test_create_company(self, test_session):
        """Create a company."""
        company = Company(
            cik="0000320193",
            name="Apple Inc.",
            entity_type="Large accelerated filer",
        )
        test_session.add(company)
        test_session.commit()

        retrieved = test_session.execute(
            select(Company).where(Company.cik == "0000320193")
        ).scalar_one()
        assert retrieved.name == "Apple Inc."
        assert retrieved.entity_type == "Large accelerated filer"

    def test_company_cik_unique(self, test_session):
        """CIK is unique."""
        company1 = Company(cik="0000320193", name="Apple Inc.")
        company2 = Company(cik="0000320193", name="Different Name")
        test_session.add(company1)
        test_session.commit()

        test_session.add(company2)
        with pytest.raises(IntegrityError):
            test_session.commit()


class TestSecurityModel:
    """Test Security model."""

    def test_create_security(self, test_session):
        """Create a security."""
        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        security = Security(
            company_id=company.id,
            ticker="AAPL",
            exchange="NASDAQ",
            security_type="common_stock",
        )
        test_session.add(security)
        test_session.commit()

        retrieved = test_session.execute(
            select(Security).where(Security.ticker == "AAPL")
        ).scalar_one()
        assert retrieved.exchange == "NASDAQ"

    def test_ticker_unique(self, test_session):
        """Ticker is unique."""
        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        security1 = Security(company_id=company.id, ticker="AAPL")
        security2 = Security(company_id=company.id, ticker="AAPL")
        test_session.add(security1)
        test_session.commit()

        test_session.add(security2)
        with pytest.raises(IntegrityError):
            test_session.commit()


class TestFilingModel:
    """Test Filing model."""

    def test_create_filing(self, test_session):
        """Create a filing."""
        from datetime import date

        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        filing = Filing(
            company_id=company.id,
            accession_number="0000320193-24-000001",
            form_type="10-K",
            filing_date=date(2024, 1, 15),
        )
        test_session.add(filing)
        test_session.commit()

        retrieved = test_session.execute(
            select(Filing).where(Filing.accession_number == "0000320193-24-000001")
        ).scalar_one()
        assert retrieved.form_type == "10-K"

    def test_accession_unique(self, test_session):
        """Accession number is unique."""
        from datetime import date

        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        filing1 = Filing(
            company_id=company.id,
            accession_number="0000320193-24-000001",
            form_type="10-K",
            filing_date=date(2024, 1, 15),
        )
        filing2 = Filing(
            company_id=company.id,
            accession_number="0000320193-24-000001",
            form_type="10-Q",
            filing_date=date(2024, 2, 15),
        )
        test_session.add(filing1)
        test_session.commit()

        test_session.add(filing2)
        with pytest.raises(IntegrityError):
            test_session.commit()


class TestFilingDocumentModel:
    """Test FilingDocument model."""

    def test_create_filing_document(self, test_session):
        """Create a filing document."""
        from datetime import date

        company = Company(cik="0000320193", name="Apple Inc.")
        test_session.add(company)
        test_session.flush()

        filing = Filing(
            company_id=company.id,
            accession_number="0000320193-24-000001",
            form_type="10-K",
            filing_date=date(2024, 1, 15),
        )
        test_session.add(filing)
        test_session.flush()

        doc = FilingDocument(
            filing_id=filing.id,
            document_name="aapl-20240101.htm",
            document_type="10-K",
        )
        test_session.add(doc)
        test_session.commit()

        retrieved = test_session.execute(
            select(FilingDocument).where(FilingDocument.document_name == "aapl-20240101.htm")
        ).scalar_one()
        assert retrieved.filing_id == filing.id
