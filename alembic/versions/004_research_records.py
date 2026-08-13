"""Create research_records table.

Revision ID: 004
Revises: 003_canonical_schema
Create Date: 2026-08-12 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003_canonical_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create research_records table with all fields."""
    op.create_table(
        "research_records",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("as_of_date", sa.String(10), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("classification_confidence", sa.Float(), nullable=True),
        sa.Column("accounting_quality_score", sa.Float(), nullable=True),
        sa.Column("owner_earnings_yield_pct", sa.Float(), nullable=True),
        sa.Column("owner_earnings_growth_pct", sa.Float(), nullable=True),
        sa.Column("roic_pct", sa.Float(), nullable=True),
        sa.Column("incremental_roic_pct", sa.Float(), nullable=True),
        sa.Column("capital_allocation_score", sa.Float(), nullable=True),
        sa.Column("credit_quality_score", sa.Float(), nullable=True),
        sa.Column("bear_case_risk_score", sa.Float(), nullable=True),
        sa.Column("forensic_risk_score", sa.Float(), nullable=True),
        sa.Column("valuation_range_low", sa.Float(), nullable=True),
        sa.Column("valuation_range_high", sa.Float(), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("margin_of_safety_pct", sa.Float(), nullable=True),
        sa.Column("peer_rank_quality", sa.Integer(), nullable=True),
        sa.Column("peer_rank_growth", sa.Integer(), nullable=True),
        sa.Column("peer_rank_valuation", sa.Integer(), nullable=True),
        sa.Column("peer_rank_safety", sa.Integer(), nullable=True),
        sa.Column("rules_triggered", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("rules_failed", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("warnings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("classification_notes", sa.Text(), nullable=True),
        sa.Column(
            "rule_version",
            sa.String(64),
            nullable=False,
            server_default="FUNDAMENTAL_RESEARCH_CLASSIFICATION_V1",
        ),
        sa.Column("feature_versions", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "as_of_date", name="uq_research_records_company_date"),
    )
    op.create_index(
        "ix_research_records_company_date", "research_records", ["company_id", "as_of_date"]
    )
    op.create_index(
        "ix_research_records_classification", "research_records", ["classification"]
    )
    op.create_index("ix_research_records_created_at", "research_records", ["created_at"])


def downgrade() -> None:
    """Drop research_records table."""
    op.drop_index("ix_research_records_created_at", table_name="research_records")
    op.drop_index("ix_research_records_classification", table_name="research_records")
    op.drop_index("ix_research_records_company_date", table_name="research_records")
    op.drop_table("research_records")
