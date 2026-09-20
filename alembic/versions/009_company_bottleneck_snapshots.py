"""Add cached company bottleneck snapshots.

Revision ID: 009
Revises: 008
Create Date: 2026-09-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_bottleneck_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("sic", sa.String(length=8), nullable=True),
        sa.Column("sic_description", sa.Text(), nullable=True),
        sa.Column("focus_family", sa.String(length=64), nullable=False),
        sa.Column("model_family", sa.String(length=64), nullable=False),
        sa.Column("model_family_reason", sa.Text(), nullable=True),
        sa.Column("stance", sa.String(length=32), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("model_family_score", sa.Float(), nullable=True),
        sa.Column("data_quality_tier", sa.String(length=32), nullable=True),
        sa.Column("latest_filing_date", sa.String(length=10), nullable=True),
        sa.Column("bottlenecks", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("management_bottlenecks", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_company_bottleneck_snapshots_company"),
    )
    op.create_index("ix_company_bottleneck_snapshots_ticker", "company_bottleneck_snapshots", ["ticker"])
    op.create_index("ix_company_bottleneck_snapshots_focus_family", "company_bottleneck_snapshots", ["focus_family"])
    op.create_index("ix_company_bottleneck_snapshots_model_family", "company_bottleneck_snapshots", ["model_family"])
    op.create_index("ix_company_bottleneck_snapshots_updated_at", "company_bottleneck_snapshots", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_company_bottleneck_snapshots_updated_at", table_name="company_bottleneck_snapshots")
    op.drop_index("ix_company_bottleneck_snapshots_model_family", table_name="company_bottleneck_snapshots")
    op.drop_index("ix_company_bottleneck_snapshots_focus_family", table_name="company_bottleneck_snapshots")
    op.drop_index("ix_company_bottleneck_snapshots_ticker", table_name="company_bottleneck_snapshots")
    op.drop_table("company_bottleneck_snapshots")
