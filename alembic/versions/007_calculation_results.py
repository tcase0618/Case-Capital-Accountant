"""Add calculation_results table for persisting metric calculations.

Revision ID: 007
Revises: 006
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create calculation_results table."""
    op.create_table(
        "calculation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calculation_id", sa.String(100), nullable=False),
        sa.Column("formula_version", sa.String(50), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("period_type", sa.String(20), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("calculation_status", sa.String(50), nullable=False, server_default="VALID"),
        sa.Column("inputs", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("source_statement_snapshot_ids", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("source_statement_line_ids", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("source_canonical_fact_ids", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("warnings", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "calculation_id",
            "fiscal_year",
            "fiscal_quarter",
            name="uq_calculation_result",
        ),
    )

    # Create indexes for common queries
    op.create_index("ix_calculation_results_calculation_id", "calculation_results", ["calculation_id"])
    op.create_index("ix_calculation_results_company_id", "calculation_results", ["company_id"])
    op.create_index("ix_calculation_results_fiscal_year", "calculation_results", ["fiscal_year"])


def downgrade() -> None:
    """Drop calculation_results table."""
    op.drop_index("ix_calculation_results_fiscal_year", table_name="calculation_results")
    op.drop_index("ix_calculation_results_company_id", table_name="calculation_results")
    op.drop_index("ix_calculation_results_calculation_id", table_name="calculation_results")
    op.drop_table("calculation_results")
