"""Scheduler and report workers must honor the same storage reserve."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


def test_scheduler_blocks_before_import_when_worker_reserve_exceeds_cap(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "scheduler_reserve_fixture",
        Path(__file__).parents[1] / "scripts/run_accountant_automation.py",
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    gib = 1024**3
    monkeypatch.setattr(module, "AUTOMATION_DIR", tmp_path)
    monkeypatch.setattr(module, "_parse_args", SimpleNamespace)
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+psycopg://offline-fixture",
            storage_max_database_gb=14,
            storage_min_free_disk_gb=25,
            storage_max_cycle_growth_gb=1,
            storage_worker_reserve_mb=128,
            data_dir=tmp_path,
        ),
    )
    monkeypatch.setattr(module, "_database_snapshot", lambda _: {})
    monkeypatch.setattr(
        module,
        "_storage_snapshot",
        lambda *_: {"database_bytes": 14 * gib - 64 * 1024**2, "disk_free_bytes": 30 * gib},
    )

    def forbidden_import(*_):
        raise AssertionError("Storage-blocked scheduler must not launch a data job")

    monkeypatch.setattr(module, "_run_step", forbidden_import)
    assert module.main() == 75  # Controlled pause is distinct from completed work.
    payload = json.loads(next(tmp_path.glob("accountant_automation_*.json")).read_text())
    assert payload["storage"]["blocked"] is True
    assert payload["storage"]["reason"] == "database_cap_reached"
    assert payload["steps"] == []
