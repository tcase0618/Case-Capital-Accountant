"""Preserve canonical source lineage when raw facts are archived."""

from alembic import op


revision = "011_archiveable_canonical_lineage"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE canonical_facts ALTER COLUMN raw_fact_id DROP NOT NULL")
    op.execute("ALTER TABLE canonical_facts DROP CONSTRAINT IF EXISTS canonical_facts_raw_fact_id_fkey")
    op.execute(
        "ALTER TABLE canonical_facts ADD CONSTRAINT canonical_facts_raw_fact_id_fkey "
        "FOREIGN KEY (raw_fact_id) REFERENCES raw_facts(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE canonical_facts ADD COLUMN IF NOT EXISTS source_fact_hash VARCHAR(64)")
    op.execute("ALTER TABLE canonical_facts ADD COLUMN IF NOT EXISTS source_accession_number VARCHAR(24)")
    op.execute("ALTER TABLE canonical_facts ADD COLUMN IF NOT EXISTS source_url TEXT")
    op.execute("ALTER TABLE canonical_facts ADD COLUMN IF NOT EXISTS source_accepted_at TIMESTAMPTZ")
    op.execute("ALTER TABLE canonical_facts ADD COLUMN IF NOT EXISTS source_filed_date DATE")
    op.execute("ALTER TABLE canonical_facts ADD COLUMN IF NOT EXISTS source_period_end DATE")
    op.execute("ALTER TABLE canonical_facts ADD COLUMN IF NOT EXISTS source_concept VARCHAR(255)")
    op.execute("ALTER TABLE canonical_facts ADD COLUMN IF NOT EXISTS source_taxonomy VARCHAR(64)")
    op.execute("ALTER TABLE canonical_facts ADD COLUMN IF NOT EXISTS source_filing_form VARCHAR(32)")
    op.execute(
        "ALTER TABLE canonical_facts ADD COLUMN IF NOT EXISTS raw_fact_archived BOOLEAN NOT NULL DEFAULT FALSE"
    )
    # The existing 1.5M-row lineage snapshot is backfilled by the bounded
    # maintenance job, not during API startup. This keeps deploys bounded.


def downgrade() -> None:
    raise RuntimeError("011 is irreversible after raw-fact archives may be created")
