"""Extend raw_facts with CompanyFacts fields.

Revision ID: 002_extend_raw_facts
Revises: 001_initial_schema
Create Date: 2026-08-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "002_extend_raw_facts"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("raw_facts", sa.Column("accession_number", sa.String(24), nullable=True))
    op.add_column("raw_facts", sa.Column("fiscal_year", sa.Integer(), nullable=True))
    op.add_column("raw_facts", sa.Column("fiscal_period", sa.String(16), nullable=True))
    op.add_column("raw_facts", sa.Column("frame", sa.String(32), nullable=True))
    op.add_column("raw_facts", sa.Column("form", sa.String(32), nullable=True))
    op.add_column("raw_facts", sa.Column("filed_date", sa.Date(), nullable=True))
    op.add_column("raw_facts", sa.Column("label", sa.String(512), nullable=True))
    op.add_column("raw_facts", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "raw_facts",
        sa.Column("source_type", sa.String(32), nullable=False, server_default="xbrl"),
    )
    op.create_index("ix_raw_facts_accession_number", "raw_facts", ["accession_number"])


def downgrade() -> None:
    op.drop_index("ix_raw_facts_accession_number", table_name="raw_facts")
    op.drop_column("raw_facts", "source_type")
    op.drop_column("raw_facts", "description")
    op.drop_column("raw_facts", "label")
    op.drop_column("raw_facts", "filed_date")
    op.drop_column("raw_facts", "form")
    op.drop_column("raw_facts", "frame")
    op.drop_column("raw_facts", "fiscal_period")
    op.drop_column("raw_facts", "fiscal_year")
    op.drop_column("raw_facts", "accession_number")
