"""Add canonical concepts, mappings, and facts tables."""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create canonical_concepts table
    op.create_table(
        "canonical_concepts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("unit_hint", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_canonical_concepts_code"),
    )
    op.create_index("ix_canonical_concepts_code", "canonical_concepts", ["code"], unique=True)

    # Create canonical_mappings table
    op.create_table(
        "canonical_mappings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("canonical_concept_id", sa.String(36), nullable=False),
        sa.Column("taxonomy", sa.String(64), nullable=False),
        sa.Column("source_concept", sa.String(255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.String(32), nullable=False),
        sa.Column("industry_applicability", sa.String(64), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("mapping_version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["canonical_concept_id"],
            ["canonical_concepts.id"],
            name="fk_canonical_mappings_canonical_concept_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_canonical_mappings_canonical_concept_id",
        "canonical_mappings",
        ["canonical_concept_id"],
    )

    # Create canonical_facts table
    op.create_table(
        "canonical_facts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("raw_fact_id", sa.String(36), nullable=False),
        sa.Column("canonical_concept_id", sa.String(36), nullable=False),
        sa.Column("value", sa.String(1024), nullable=True),
        sa.Column("value_numeric", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("mapping_rule", sa.String(255), nullable=True),
        sa.Column("mapping_version", sa.Integer(), nullable=False),
        sa.Column("mapping_confidence", sa.String(32), nullable=False),
        sa.Column("reported_or_derived", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_canonical_facts_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["raw_fact_id"],
            ["raw_facts.id"],
            name="fk_canonical_facts_raw_fact_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_concept_id"],
            ["canonical_concepts.id"],
            name="fk_canonical_facts_canonical_concept_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_canonical_facts_company_id", "canonical_facts", ["company_id"])
    op.create_index("ix_canonical_facts_raw_fact_id", "canonical_facts", ["raw_fact_id"])
    op.create_index("ix_canonical_facts_canonical_concept_id", "canonical_facts", ["canonical_concept_id"])


def downgrade() -> None:
    op.drop_index("ix_canonical_facts_canonical_concept_id", table_name="canonical_facts")
    op.drop_index("ix_canonical_facts_raw_fact_id", table_name="canonical_facts")
    op.drop_index("ix_canonical_facts_company_id", table_name="canonical_facts")
    op.drop_table("canonical_facts")

    op.drop_index("ix_canonical_mappings_canonical_concept_id", table_name="canonical_mappings")
    op.drop_table("canonical_mappings")

    op.drop_index("ix_canonical_concepts_code", table_name="canonical_concepts")
    op.drop_table("canonical_concepts")
