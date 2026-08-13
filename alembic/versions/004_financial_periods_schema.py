"""Add financial periods table for period classification and resolution."""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create financial_periods table
    op.create_table(
        "financial_periods",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("period_type", sa.String(32), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("instant_date", sa.Date(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("fiscal_year_end", sa.String(4), nullable=True),
        sa.Column("is_ytd", sa.Boolean(), nullable=False),
        sa.Column("is_derived", sa.Boolean(), nullable=False),
        sa.Column("source_form", sa.String(32), nullable=True),
        sa.Column("source_accession", sa.String(24), nullable=True),
        sa.Column("source_fact_ids", sa.JSON(), nullable=True),
        sa.Column("derivation_method", sa.String(64), nullable=True),
        sa.Column("derivation_formula", sa.Text(), nullable=True),
        sa.Column("resolver_version", sa.String(32), nullable=False),
        sa.Column("confidence", sa.String(32), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("originally_reported", sa.Boolean(), nullable=False),
        sa.Column("restated_by_accession", sa.String(24), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_financial_periods_company_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_financial_periods_company_id",
        "financial_periods",
        ["company_id"],
    )
    op.create_index(
        "ix_financial_periods_company_fiscal",
        "financial_periods",
        ["company_id", "fiscal_year", "fiscal_quarter"],
    )
    op.create_index(
        "ix_financial_periods_company_dates",
        "financial_periods",
        ["company_id", "start_date", "end_date"],
    )
    op.create_unique_constraint(
        "uq_financial_periods_unique_period",
        "financial_periods",
        ["company_id", "period_type", "fiscal_year", "fiscal_quarter", "instant_date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_financial_periods_unique_period",
        "financial_periods",
        type_="unique",
    )
    op.drop_index("ix_financial_periods_company_dates", "financial_periods")
    op.drop_index("ix_financial_periods_company_fiscal", "financial_periods")
    op.drop_index("ix_financial_periods_company_id", "financial_periods")
    op.drop_table("financial_periods")
