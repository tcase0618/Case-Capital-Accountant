"""Version the four research tables previously created outside Alembic.

Frozen definitions from audit branch a5ba414. Existing tables and rows are
adopted, never replaced. Any pre-existing missing column fails closed.
"""

import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def _create_table(name, *definitions):
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(name):
        op.create_table(name, *definitions)
        return
    expected = {item.name for item in definitions if isinstance(item, sa.Column)}
    actual = {item["name"] for item in inspector.get_columns(name)}
    if expected - actual:
        raise RuntimeError(f"Existing {name} is incomplete; explicit repair migration required")


def _create_index(name, table, columns, **kwargs):
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns, **kwargs)


def upgrade():
    _create_table(
        "buy_board_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_report_date", sa.String(length=10), nullable=True),
        sa.Column("source_report_score", sa.Float(), nullable=True),
        sa.Column("first_qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_price", sa.Float(), nullable=True),
        sa.Column("first_price_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("current_price_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_cc_valuation", sa.Float(), nullable=True),
        sa.Column("first_valuation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_cc_valuation", sa.Float(), nullable=True),
        sa.Column("current_valuation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cc_valuation_growth_forecast_pct", sa.Float(), nullable=True),
        sa.Column("synopsis", sa.Text(), nullable=False),
        sa.Column("why_buy", sa.JSON(), nullable=False),
        sa.Column("accounting_basis", sa.JSON(), nullable=False),
        sa.Column("battle_card", sa.JSON(), nullable=False),
        sa.Column("last_price_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_price_source", sa.String(length=32), nullable=True),
        sa.Column("current_market_data_quality", sa.String(length=32), nullable=True),
        sa.Column("last_price_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_buy_board_candidates_company"),
    )
    _create_index(
        "ix_buy_board_candidates_current_cc_valuation",
        "buy_board_candidates",
        ["current_cc_valuation"],
        unique=False,
    )
    _create_index(
        "ix_buy_board_candidates_status", "buy_board_candidates", ["status"], unique=False
    )
    _create_index(
        "ix_buy_board_candidates_ticker", "buy_board_candidates", ["ticker"], unique=False
    )
    _create_table(
        "company_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("as_of_date", sa.String(length=10), nullable=False),
        sa.Column("stance", sa.String(length=32), nullable=False),
        sa.Column("bullish_score", sa.Float(), nullable=False),
        sa.Column("bearish_score", sa.Float(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("data_quality_tier", sa.String(length=32), nullable=True),
        sa.Column("pipeline_stage", sa.String(length=32), nullable=False),
        sa.Column("latest_filing_date", sa.String(length=10), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("key_stats", sa.JSON(), nullable=False),
        sa.Column("highlights", sa.JSON(), nullable=False),
        sa.Column("report_markdown", sa.Text(), nullable=False),
        sa.Column("source_versions", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_company_reports_company"),
    )
    _create_index(
        "ix_company_reports_composite_score", "company_reports", ["composite_score"], unique=False
    )
    _create_index("ix_company_reports_stance", "company_reports", ["stance"], unique=False)
    _create_index("ix_company_reports_ticker", "company_reports", ["ticker"], unique=False)
    _create_index("ix_company_reports_updated_at", "company_reports", ["updated_at"], unique=False)
    _create_table(
        "report_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("report_card_id", sa.String(length=96), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("sic_code", sa.String(length=8), nullable=True),
        sa.Column("gics_sector", sa.String(length=64), nullable=True),
        sa.Column("gics_industry", sa.String(length=128), nullable=True),
        sa.Column("exchange", sa.String(length=32), nullable=True),
        sa.Column("filing_type", sa.String(length=32), nullable=False),
        sa.Column("period_of_report", sa.Date(), nullable=True),
        sa.Column("filed_date", sa.Date(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accession_number", sa.String(length=24), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_filing_sha256", sa.String(length=64), nullable=True),
        sa.Column("is_restatement", sa.Boolean(), nullable=False),
        sa.Column("restates_report_card_id", sa.String(length=96), nullable=True),
        sa.Column("tag_map_version", sa.String(length=64), nullable=False),
        sa.Column("prior_report_card_id", sa.String(length=96), nullable=True),
        sa.Column("standardized_financials", sa.JSON(), nullable=False),
        sa.Column("growth_trend_deltas", sa.JSON(), nullable=False),
        sa.Column("accrual_cash_quality", sa.JSON(), nullable=False),
        sa.Column("forensic_scores", sa.JSON(), nullable=False),
        sa.Column("positive_quality", sa.JSON(), nullable=False),
        sa.Column("event_red_flags", sa.JSON(), nullable=False),
        sa.Column("textual_signals", sa.JSON(), nullable=False),
        sa.Column("non_gaap_forensics", sa.JSON(), nullable=False),
        sa.Column("governance_ownership", sa.JSON(), nullable=False),
        sa.Column("market_data_linkage", sa.JSON(), nullable=False),
        sa.Column("universe_tradability", sa.JSON(), nullable=False),
        sa.Column("final_verdict", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_card_id", name="uq_report_cards_report_card_id"),
    )
    _create_index(
        "ix_report_cards_accession_number", "report_cards", ["accession_number"], unique=False
    )
    _create_index("ix_report_cards_cik", "report_cards", ["cik"], unique=False)
    _create_index(
        "ix_report_cards_cik_filed_date", "report_cards", ["cik", "filed_date"], unique=False
    )
    _create_index(
        "ix_report_cards_company_filed_date",
        "report_cards",
        ["company_id", "filed_date"],
        unique=False,
    )
    _create_index("ix_report_cards_company_id", "report_cards", ["company_id"], unique=False)
    _create_index("ix_report_cards_filed_date", "report_cards", ["filed_date"], unique=False)
    _create_index("ix_report_cards_ticker", "report_cards", ["ticker"], unique=False)
    _create_index(
        "ix_report_cards_ticker_filed_date", "report_cards", ["ticker", "filed_date"], unique=False
    )
    _create_table(
        "buy_board_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("session_label", sa.String(length=32), nullable=False),
        sa.Column("refresh_reason", sa.String(length=64), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("cc_valuation", sa.Float(), nullable=True),
        sa.Column("upside_pct", sa.Float(), nullable=True),
        sa.Column("data_quality", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["buy_board_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index(
        "ix_buy_board_snapshots_candidate_id", "buy_board_snapshots", ["candidate_id"], unique=False
    )
    _create_index(
        "ix_buy_board_snapshots_captured_at", "buy_board_snapshots", ["captured_at"], unique=False
    )


def downgrade():
    raise RuntimeError("Research/report history must be preserved; migration 013 is forward-only")
