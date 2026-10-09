import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from accountant.db import Base


def migration():
    path = Path(__file__).parents[1] / "alembic/versions/013_research_tables.py"
    spec = importlib.util.spec_from_file_location("research_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_research_migration_creates_and_adopts_tables_without_create_all():
    engine = sa.create_engine("sqlite:///:memory:")
    module = migration()
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE companies (id CHAR(32) PRIMARY KEY)")
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        # An immutable sentinel proves adoption does not replace prior tables.
        connection.exec_driver_sql(
            "INSERT INTO buy_board_snapshots "
            "(id, candidate_id, session_label, refresh_reason, captured_at) "
            "VALUES ('sentinel', 'candidate', 'MANUAL', 'test', CURRENT_TIMESTAMP)"
        )
        module.upgrade()
        assert (
            connection.exec_driver_sql("SELECT id FROM buy_board_snapshots").scalar() == "sentinel"
        )
        inspector = sa.inspect(connection)
        for name in (
            "company_reports",
            "report_cards",
            "buy_board_candidates",
            "buy_board_snapshots",
        ):
            model = Base.metadata.tables[name]
            assert {c["name"] for c in inspector.get_columns(name)} == set(model.columns.keys())
            assert {i["name"] for i in inspector.get_indexes(name)} == {
                i.name for i in model.indexes
            }
            connection.execute(sa.select(model).limit(1))


def test_existing_incomplete_table_fails_closed():
    engine = sa.create_engine("sqlite:///:memory:")
    module = migration()
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE buy_board_candidates (id CHAR(32))")
        module.op = Operations(MigrationContext.configure(connection))
        with pytest.raises(RuntimeError, match="explicit repair migration"):
            module.upgrade()


def test_research_migration_refuses_destructive_downgrade():
    with pytest.raises(RuntimeError, match="history must be preserved"):
        migration().downgrade()


def test_production_startup_never_calls_create_all(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import accountant.api.app as module

    monkeypatch.setattr(
        module, "get_settings", lambda: SimpleNamespace(is_production=True, machine_enabled=False)
    )
    monkeypatch.setattr(module, "_API_SESSION_FACTORY", MagicMock())
    monkeypatch.setattr(module, "ensure_canonical_taxonomy_seeded", lambda _: None)
    for name in (
        "_ensure_dashboard_fact_totals_refresh",
        "_ensure_dashboard_metrics_refresh",
        "_ensure_companies_cache_refresh",
    ):
        monkeypatch.setattr(module, name, lambda: None)
    monkeypatch.setattr(module.CACHE_WARMER, "start", lambda: None)

    def forbidden(*_args, **_kwargs):
        pytest.fail("Production must use migrations, not create_all")

    monkeypatch.setattr(Base.metadata, "create_all", forbidden)
    module.startup_machine()
