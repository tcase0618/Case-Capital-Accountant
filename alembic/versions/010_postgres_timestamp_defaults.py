"""Add database-side timestamp defaults to runtime-written tables."""

import sqlalchemy as sa
from alembic import op


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, columns in {
        "research_records": ("created_at", "updated_at"),
        "statement_snapshots": ("created_at", "updated_at"),
        "statement_lines": ("created_at",),
    }.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )


def downgrade() -> None:
    for table, columns in {
        "research_records": ("created_at", "updated_at"),
        "statement_snapshots": ("created_at", "updated_at"),
        "statement_lines": ("created_at",),
    }.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=None,
            )
