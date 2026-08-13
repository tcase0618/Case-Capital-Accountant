"""Add statement snapshots and lines tables for reconstructed statements."""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create statement_snapshots and statement_lines tables."""
    # Create statement_snapshots table
    op.create_table(
        "statement_snapshots",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("statement_type", sa.String(32), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("period_type", sa.String(32), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("instant_date", sa.Date(), nullable=True),
        sa.Column("source_accessions", sa.JSON(), nullable=True),
        sa.Column("primary_accession", sa.String(24), nullable=True),
        sa.Column("builder_version", sa.String(64), nullable=False),
        sa.Column("mapping_version", sa.Integer(), nullable=False),
        sa.Column("resolver_version", sa.String(64), nullable=False),
        sa.Column("quality_status", sa.String(32), nullable=False),
        sa.Column("completeness", sa.Float(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("quality_notes", sa.Text(), nullable=True),
        sa.Column("is_restated", sa.Boolean(), nullable=False),
        sa.Column("restated_by_snapshot_id", sa.String(36), nullable=True),
        sa.Column("originally_reported", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_statement_snapshots_company_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_statement_snapshots_company_type",
        "statement_snapshots",
        ["company_id", "statement_type"],
    )
    op.create_index(
        "ix_statement_snapshots_company_period",
        "statement_snapshots",
        ["company_id", "fiscal_year", "fiscal_quarter"],
    )

    # Create statement_lines table
    op.create_table(
        "statement_lines",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("canonical_concept", sa.String(64), nullable=False),
        sa.Column("canonical_concept_id", sa.String(36), nullable=True),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("value_text", sa.String(1024), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("canonical_fact_id", sa.String(36), nullable=True),
        sa.Column("raw_fact_id", sa.String(36), nullable=True),
        sa.Column("filing_id", sa.String(36), nullable=True),
        sa.Column("accession_number", sa.String(24), nullable=True),
        sa.Column("raw_taxonomy", sa.String(64), nullable=True),
        sa.Column("raw_concept", sa.String(255), nullable=True),
        sa.Column("mapping_version", sa.Integer(), nullable=False),
        sa.Column("resolver_version", sa.String(64), nullable=False),
        sa.Column("reported_or_derived", sa.String(32), nullable=False),
        sa.Column("derivation_formula", sa.Text(), nullable=True),
        sa.Column("derivation_method", sa.String(64), nullable=True),
        sa.Column("mapping_confidence", sa.String(32), nullable=False),
        sa.Column("selection_status", sa.String(32), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["statement_snapshots.id"],
            name="fk_statement_lines_snapshot_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_statement_lines_company_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_statement_lines_snapshot_concept",
        "statement_lines",
        ["snapshot_id", "canonical_concept"],
    )
    op.create_index(
        "ix_statement_lines_company_concept",
        "statement_lines",
        ["company_id", "canonical_concept"],
    )


def downgrade() -> None:
    """Drop statement tables."""
    op.drop_index("ix_statement_lines_company_concept", "statement_lines")
    op.drop_index("ix_statement_lines_snapshot_concept", "statement_lines")
    op.drop_table("statement_lines")
    op.drop_index("ix_statement_snapshots_company_period", "statement_snapshots")
    op.drop_index("ix_statement_snapshots_company_type", "statement_snapshots")
    op.drop_table("statement_snapshots")
