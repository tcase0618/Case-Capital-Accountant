import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def migration():
    path = Path(__file__).parents[1] / "alembic/versions/014_schema_drift.py"
    spec = importlib.util.spec_from_file_location("schema_drift", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def foreign_key(name, action):
    return {
        "name": name,
        "constrained_columns": ["raw_fact_id"],
        "referred_table": "raw_facts",
        "referred_columns": ["id"],
        "options": {"ondelete": action},
    }


def test_redundant_cascade_fk_removed_only_after_set_null_protection_verified(monkeypatch):
    module = migration()
    module.op = MagicMock()
    inspector = MagicMock()
    monkeypatch.setattr(module.sa, "inspect", lambda _: inspector)
    old = foreign_key("fk_canonical_facts_raw_fact_id", "CASCADE")
    intended = foreign_key("canonical_facts_raw_fact_id_fkey", "SET NULL")
    inspector.get_foreign_keys.return_value = [old]
    with pytest.raises(RuntimeError, match="existing SET NULL"):
        module._repair_legacy_lineage_fk()
    module.op.drop_constraint.assert_not_called()
    inspector.get_foreign_keys.return_value = [old, intended]
    module._repair_legacy_lineage_fk()
    module.op.drop_constraint.assert_called_once_with(
        old["name"], "canonical_facts", type_="foreignkey"
    )


def test_unexpected_lineage_constraint_fails_closed(monkeypatch):
    module = migration()
    module.op = MagicMock()
    inspector = MagicMock()
    inspector.get_foreign_keys.return_value = [
        foreign_key("fk_canonical_facts_raw_fact_id", "RESTRICT")
    ]
    monkeypatch.setattr(module.sa, "inspect", lambda _: inspector)
    with pytest.raises(RuntimeError, match="manual schema review"):
        module._repair_legacy_lineage_fk()
    module.op.drop_constraint.assert_not_called()


def test_forward_only_and_existing_uniqueness_protections_preserved():
    from sqlalchemy import UniqueConstraint

    from accountant.db.models import CanonicalConcept, Company

    for model, name in (
        (Company, "uq_companies_cik"),
        (CanonicalConcept, "uq_canonical_concepts_code"),
    ):
        assert any(
            isinstance(c, UniqueConstraint) and c.name == name for c in model.__table__.constraints
        )
    with pytest.raises(RuntimeError, match="protections must be preserved"):
        migration().downgrade()
