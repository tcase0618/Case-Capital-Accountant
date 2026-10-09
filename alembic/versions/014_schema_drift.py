"""Reconcile source-validated legacy drift without deleting rows or protections.

The old named CASCADE FK survived 011 alongside its intended SET NULL FK.
Remove ONLY that duplicate, after proving the intended FK is already present.
"""

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

INDEXES = (
    ("canonical_facts", "source_fact_hash"),
    ("paper_book_positions", "company_id"),
    ("paper_book_positions", "report_card_id"),
    ("paper_book_positions", "ticker"),
    ("statement_lines", "company_id"),
    ("statement_lines", "snapshot_id"),
    ("statement_snapshots", "company_id"),
)
COMMENTS = {
    "financial_periods": {
        "period_type": "INSTANT, Q1-Q4, FY, YTD_Q1-YTD_Q3, TTM, UNKNOWN",
        "derivation_method": "e.g., YTD_MINUS_YTD, FY_MINUS_YTD, DIRECT_REPORT",
        "derivation_formula": "Human-readable derivation, e.g., '6M YTD - Q1 = Q2'",
        "confidence": "HIGH, MEDIUM, LOW, UNKNOWN",
    },
    "statement_snapshots": {
        "statement_type": "income, balance, cashflow",
        "period_type": "Q1-Q4, FY, INSTANT",
        "source_accessions": "Array of accession numbers used",
        "builder_version": "e.g., INCOME_STATEMENT_BUILDER_V1",
        "quality_status": "PASS, WARNING, FAIL, INSUFFICIENT_DATA",
        "completeness": "0.0-1.0, % of required concepts",
    },
    "statement_lines": {
        "canonical_concept": "e.g., CC_REVENUE",
        "reported_or_derived": "reported or derived",
        "mapping_confidence": "HIGH, MEDIUM, LOW, UNKNOWN",
        "selection_status": "SELECTED, MULTIPLE_EQUIVALENT, CONFLICT, AMBIGUOUS, MISSING",
    },
}


def _repair_legacy_lineage_fk():
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys("canonical_facts")
    old = next((fk for fk in foreign_keys if fk["name"] == "fk_canonical_facts_raw_fact_id"), None)
    if old is None:
        return

    def targets_raw_fact(fk):
        return (
            fk["constrained_columns"] == ["raw_fact_id"]
            and fk["referred_table"] == "raw_facts"
            and fk["referred_columns"] == ["id"]
        )

    if not targets_raw_fact(old) or old.get("options", {}).get("ondelete") != "CASCADE":
        raise RuntimeError("Unexpected legacy lineage FK; manual schema review required")
    if not any(
        targets_raw_fact(fk) and fk.get("options", {}).get("ondelete") == "SET NULL"
        for fk in foreign_keys
    ):
        raise RuntimeError("Refusing to remove lineage FK without existing SET NULL protection")
    op.drop_constraint(old["name"], "canonical_facts", type_="foreignkey")


def upgrade():
    _repair_legacy_lineage_fk()
    for table, column in INDEXES:
        name = f"ix_{table}_{column}"
        indexes = {item["name"]: item for item in sa.inspect(op.get_bind()).get_indexes(table)}
        if name not in indexes:
            op.create_index(name, table, [column])
        elif indexes[name]["column_names"] != [column] or indexes[name]["unique"]:
            raise RuntimeError(f"Unexpected index definition: {name}")
    for table, comments in COMMENTS.items():
        columns = {item["name"]: item for item in sa.inspect(op.get_bind()).get_columns(table)}
        for column, comment in comments.items():
            if columns[column].get("comment") != comment:
                op.alter_column(table, column, comment=comment)


def downgrade():
    raise RuntimeError("Schema/lineage protections must be preserved; 014 is forward-only")
