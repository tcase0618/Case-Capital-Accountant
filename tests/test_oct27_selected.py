"""Independently selected audit regressions adapted to current main."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from accountant.config import Settings

ROOT = Path(__file__).parents[1]
LIMITS = {
    "storage_max_database_gb": 14,
    "storage_min_free_disk_gb": 25,
    "storage_max_cycle_growth_gb": 1,
}


def load_script(name):
    spec = importlib.util.spec_from_file_location(f"oct27_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("field", LIMITS)
@pytest.mark.parametrize("value", [None, 0, -1, float("nan"), float("inf")])
def test_production_requires_each_finite_positive_storage_limit(monkeypatch, field, value):
    for key in LIMITS:
        monkeypatch.delenv(f"ACCOUNTANT_{key.upper()}", raising=False)
        monkeypatch.delenv(key.upper(), raising=False)
    values = dict(LIMITS)
    if value is None:
        values.pop(field)
    else:
        values[field] = value
    with pytest.raises(ValidationError, match="storage"):
        Settings(_env_file=None, accountant_env="production", **values)


def test_production_accepts_explicit_limits_and_test_mode_keeps_offline_defaults():
    assert Settings(_env_file=None, accountant_env="production", **LIMITS).is_production
    assert Settings(_env_file=None, accountant_env="test").storage_max_database_gb == 0


@pytest.mark.parametrize("environment", ["production", " PRODUCTION "])
def test_whitespace_cannot_bypass_production_guard(environment):
    with pytest.raises(ValidationError, match="storage"):
        Settings(_env_file=None, accountant_env=environment)


@pytest.mark.parametrize("environment", ["prod", "staging", "typo", ""])
def test_unknown_environment_does_not_disable_production_auth(environment):
    with pytest.raises(ValidationError, match="ACCOUNTANT_ENV"):
        Settings(_env_file=None, accountant_env=environment, **LIMITS)


def test_invalid_production_settings_do_not_print_credentials():
    secret = "DO_NOT_LOG_THIS_TOKEN"
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, accountant_env="production", api_token=secret)
    assert secret not in str(error.value)


@pytest.mark.parametrize("path", ["/health/db", "/health/typo", "/api", "/companies", "/assets"])
def test_reserved_paths_cannot_return_spa_success(monkeypatch, tmp_path, path):
    import accountant.api.app as module

    (tmp_path / "index.html").write_text("<html>fixture dashboard</html>")
    monkeypatch.setattr(module, "_FRONTEND_DIST", tmp_path)
    client = TestClient(module.app)
    assert client.get(path).status_code == 404
    assert client.get("/dashboard").status_code == 200


@pytest.mark.parametrize("database_gib", [14, 15])
def test_storage_pause_is_distinct_from_success_and_never_starts_steps(
    monkeypatch, tmp_path, database_gib
):
    import json
    from unittest.mock import Mock

    module = load_script("run_accountant_automation")
    monkeypatch.setattr(module, "AUTOMATION_DIR", tmp_path)
    monkeypatch.setattr(module, "_parse_args", lambda: SimpleNamespace())
    monkeypatch.setattr(module, "get_settings", lambda: Settings(accountant_env="test", **LIMITS))
    monkeypatch.setattr(module, "_database_snapshot", lambda _: {})
    monkeypatch.setattr(
        module,
        "_storage_snapshot",
        lambda *_: {
            "database_bytes": database_gib * 1024**3,
            "disk_free_bytes": 30 * 1024**3,
        },
    )
    step = Mock()
    monkeypatch.setattr(module, "_run_step", step)
    assert module.main() == 75
    step.assert_not_called()
    summary = json.loads(next(tmp_path.glob("accountant_automation_*.json")).read_text())
    assert summary["status"] == "paused_storage"
    assert summary["storage"]["reason"] == "database_cap_reached"
