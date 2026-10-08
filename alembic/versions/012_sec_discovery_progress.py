"""Track company polling and durable daily-index completion."""

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("filings_checked_at", sa.DateTime(timezone=True)))
    op.create_table(
        "sec_index_checkpoints",
        sa.Column("index_date", sa.Date(), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True)),
        sa.Column("matched_rows", sa.Integer()),
    )


def downgrade() -> None:
    raise RuntimeError("Discovery progress must be preserved; migration 012 is forward-only")
