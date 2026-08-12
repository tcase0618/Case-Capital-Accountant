"""Initial schema for THE ACCOUNTANT.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("cik", sa.String(10), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("sic", sa.String(8), nullable=True),
        sa.Column("sic_description", sa.Text(), nullable=True),
        sa.Column("ein", sa.String(16), nullable=True),
        sa.Column("fiscal_year_end", sa.String(8), nullable=True),
        sa.Column("state_of_incorporation", sa.String(8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cik", name="uq_companies_cik"),
    )
    op.create_index("ix_companies_cik", "companies", ["cik"], unique=True)

    # Create securities table
    op.create_table(
        "securities",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("company_id", sa.CHAR(36), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=True),
        sa.Column("cusip", sa.String(16), nullable=True),
        sa.Column("isin", sa.String(16), nullable=True),
        sa.Column("security_type", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", name="uq_securities_ticker"),
    )
    op.create_index("ix_securities_company_id", "securities", ["company_id"])
    op.create_index("ix_securities_ticker", "securities", ["ticker"])

    # Create filings table
    op.create_table(
        "filings",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("company_id", sa.CHAR(36), nullable=False),
        sa.Column("accession_number", sa.String(24), nullable=False),
        sa.Column("form_type", sa.String(32), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("primary_document", sa.String(255), nullable=True),
        sa.Column("primary_doc_description", sa.Text(), nullable=True),
        sa.Column("is_amendment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("file_number", sa.String(32), nullable=True),
        sa.Column("film_number", sa.String(32), nullable=True),
        sa.Column("act", sa.String(8), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("is_xbrl", sa.Boolean(), nullable=True),
        sa.Column("is_inline_xbrl", sa.Boolean(), nullable=True),
        sa.Column("source_system", sa.String(32), nullable=False, server_default="sec_submissions"),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accession_number", name="uq_filings_accession_number"),
    )
    op.create_index("ix_filings_company_id", "filings", ["company_id"])
    op.create_index("ix_filings_form_type", "filings", ["form_type"])
    op.create_index("ix_filings_filing_date", "filings", ["filing_date"])
    op.create_index("ix_filings_company_form_date", "filings", ["company_id", "form_type", "filing_date"])

    # Create filing_documents table
    op.create_table(
        "filing_documents",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("filing_id", sa.CHAR(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("document_name", sa.String(255), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("filing_id", "document_name", name="uq_filing_documents_filing_name"),
    )
    op.create_index("ix_filing_documents_filing_id", "filing_documents", ["filing_id"])

    # Create raw_facts table
    op.create_table(
        "raw_facts",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("filing_id", sa.CHAR(36), nullable=False),
        sa.Column("company_id", sa.CHAR(36), nullable=False),
        sa.Column("concept", sa.String(255), nullable=False),
        sa.Column("taxonomy", sa.String(64), nullable=True),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("instant_date", sa.Date(), nullable=True),
        sa.Column("decimals", sa.Integer(), nullable=True),
        sa.Column("value_numeric", sa.Numeric(38, 10), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("dimensions", sa.JSON(), nullable=True),
        sa.Column("context_id", sa.String(128), nullable=True),
        sa.Column("fact_hash", sa.String(64), nullable=False),
        sa.Column("source_document", sa.String(255), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fact_hash", name="uq_raw_facts_fact_hash"),
    )
    op.create_index("ix_raw_facts_filing_id", "raw_facts", ["filing_id"])
    op.create_index("ix_raw_facts_company_id", "raw_facts", ["company_id"])
    op.create_index("ix_raw_facts_company_concept_period", "raw_facts", ["company_id", "concept", "period_end"])
    op.create_index("ix_raw_facts_filing_concept", "raw_facts", ["filing_id", "concept"])


def downgrade() -> None:
    op.drop_table("raw_facts")
    op.drop_table("filing_documents")
    op.drop_table("filings")
    op.drop_table("securities")
    op.drop_table("companies")
