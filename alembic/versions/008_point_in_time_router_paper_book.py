"""Add raw fact point-in-time lineage fields and paper book positions.

Revision ID: 008
Revises: 007
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create extension if not exists pgcrypto")
    op.add_column("raw_facts", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("raw_facts", sa.Column("lineage_hash", sa.String(length=64), nullable=True))
    op.add_column("raw_facts", sa.Column("lineage_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("raw_facts", sa.Column("prior_version_fact_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("raw_facts", sa.Column("first_reported_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "raw_facts",
        sa.Column("first_reported_accession_number", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "raw_facts",
        sa.Column("is_amendment_fact", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_raw_facts_accepted_at", "raw_facts", ["accepted_at"])
    op.create_index("ix_raw_facts_lineage_hash", "raw_facts", ["lineage_hash"])
    op.create_index(
        "ix_raw_facts_lineage_accepted",
        "raw_facts",
        ["company_id", "lineage_hash", "accepted_at"],
    )

    op.execute(
        """
        update raw_facts rf
        set accepted_at = f.accepted_at
        from filings f
        where rf.filing_id = f.id
          and rf.accepted_at is null
        """
    )
    op.execute(
        """
        update raw_facts
        set lineage_hash = encode(
            digest(
                coalesce(company_id::text, '') || '|' ||
                coalesce(taxonomy, '') || '|' ||
                coalesce(concept, '') || '|' ||
                coalesce(unit, '') || '|' ||
                coalesce(period_start::text, '') || '|' ||
                coalesce(period_end::text, '') || '|' ||
                coalesce(instant_date::text, ''),
                'sha256'
            ),
            'hex'
        )
        where lineage_hash is null
        """
    )
    op.execute(
        """
        with ranked as (
            select
                rf.id,
                rf.lineage_hash,
                rf.accession_number,
                rf.accepted_at,
                row_number() over (
                    partition by rf.company_id, rf.lineage_hash
                    order by rf.accepted_at asc nulls last, rf.filed_date asc nulls last, rf.created_at asc, rf.id asc
                ) as version_rank,
                first_value(rf.accepted_at) over (
                    partition by rf.company_id, rf.lineage_hash
                    order by rf.accepted_at asc nulls last, rf.filed_date asc nulls last, rf.created_at asc, rf.id asc
                ) as first_reported_at_value,
                first_value(rf.accession_number) over (
                    partition by rf.company_id, rf.lineage_hash
                    order by rf.accepted_at asc nulls last, rf.filed_date asc nulls last, rf.created_at asc, rf.id asc
                ) as first_reported_accession_value,
                lag(rf.id) over (
                    partition by rf.company_id, rf.lineage_hash
                    order by rf.accepted_at asc nulls last, rf.filed_date asc nulls last, rf.created_at asc, rf.id asc
                ) as prior_fact_id
            from raw_facts rf
        )
        update raw_facts rf
        set
            lineage_version = ranked.version_rank,
            prior_version_fact_id = ranked.prior_fact_id,
            first_reported_at = ranked.first_reported_at_value,
            first_reported_accession_number = ranked.first_reported_accession_value
        from ranked
        where rf.id = ranked.id
        """
    )
    op.execute(
        """
        update raw_facts rf
        set is_amendment_fact = coalesce(f.is_amendment, false)
        from filings f
        where rf.filing_id = f.id
        """
    )
    op.alter_column("raw_facts", "lineage_version", server_default=None)
    op.alter_column("raw_facts", "is_amendment_fact", server_default=None)

    op.create_table(
        "paper_book_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("book_name", sa.String(length=96), nullable=False),
        sa.Column("launch_date", sa.Date(), nullable=False),
        sa.Column("lane", sa.String(length=32), nullable=False),
        sa.Column("route_family", sa.String(length=48), nullable=False),
        sa.Column("route_reason", sa.Text(), nullable=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("report_card_id", sa.String(length=96), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("target_weight", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("thesis_snapshot", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_name", "ticker", name="uq_paper_book_positions_book_ticker"),
    )
    op.create_index("ix_paper_book_positions_book_name", "paper_book_positions", ["book_name"])
    op.create_index("ix_paper_book_positions_launch_date", "paper_book_positions", ["launch_date"])
    op.create_index("ix_paper_book_positions_status", "paper_book_positions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_paper_book_positions_status", table_name="paper_book_positions")
    op.drop_index("ix_paper_book_positions_launch_date", table_name="paper_book_positions")
    op.drop_index("ix_paper_book_positions_book_name", table_name="paper_book_positions")
    op.drop_table("paper_book_positions")

    op.drop_index("ix_raw_facts_lineage_accepted", table_name="raw_facts")
    op.drop_index("ix_raw_facts_lineage_hash", table_name="raw_facts")
    op.drop_index("ix_raw_facts_accepted_at", table_name="raw_facts")
    op.drop_column("raw_facts", "is_amendment_fact")
    op.drop_column("raw_facts", "first_reported_accession_number")
    op.drop_column("raw_facts", "first_reported_at")
    op.drop_column("raw_facts", "prior_version_fact_id")
    op.drop_column("raw_facts", "lineage_version")
    op.drop_column("raw_facts", "lineage_hash")
    op.drop_column("raw_facts", "accepted_at")
