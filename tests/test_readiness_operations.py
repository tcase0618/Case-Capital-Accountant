"""Offline operations evidence, shell classification, and monitor contracts."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def readiness():
    return load("vps_readiness_check")


def write(path, payload):
    path.write_text(json.dumps(payload))
    return path


def test_paused_cycle_keeps_last_success(readiness, tmp_path):
    now = datetime.now(UTC)
    old = (now - timedelta(hours=2)).isoformat()
    status = write(
        tmp_path / "status.json", {
            "status": "complete", "exit_code": 0, "last_cycle_at": old, "last_success_at": old,
        }
    )
    summary = write(
        tmp_path / "summary.json",
        {
            "generated_at": now.isoformat(),
            "storage": {"blocked": True, "reason": "database_cap_reached"},
        },
    )
    result = readiness.record_cycle(status, summary, 0, now.isoformat(), now.isoformat(), "cycle-2")
    assert result["status"] == "paused_storage"
    assert result["reason"] == "database_cap_reached"
    assert result["last_success_at"] == old
    assert result["generation"] == "cycle-2"
    write(status, result)
    assert not readiness.scheduler_status(status, now=now)["ok"]


def test_legacy_exit_zero_does_not_establish_success(readiness, tmp_path):
    now = datetime.now(UTC).isoformat()
    status = write(tmp_path / "status.json", {"status": "complete", "exit_code": 0, "last_cycle_at": now})
    summary = write(tmp_path / "summary.json", {
        "generated_at": now, "storage": {"blocked": True, "reason": "database_cap_reached"},
    })
    result = readiness.record_cycle(status, summary, 0, now, now, "new-generation")
    assert result["status"] == "paused_storage"
    assert result["last_success_at"] is None


@pytest.mark.parametrize(
    "hours, expected, missed",
    [
        (0, True, False),
        (1, False, True),
        (-1, False, False),
        (40, False, True),
    ],
)
def test_scheduler_age_and_active_poll(readiness, tmp_path, monkeypatch, hours, expected, missed):
    monkeypatch.setenv("ACCOUNTANT_POLL_WINDOWS", "06:00-09:30,16:00-22:00")
    monkeypatch.setenv("ACCOUNTANT_ACTIVE_POLL_INTERVAL_SECONDS", "900")
    now = datetime(2026, 10, 21, 12, tzinfo=UTC)  # 08:00 Eastern
    path = write(
        tmp_path / "status.json",
        {
            "status": "complete",
            "exit_code": 0,
            "last_cycle_at": (now - timedelta(hours=hours)).isoformat(),
        },
    )
    result = readiness.scheduler_status(path, now=now)
    assert result["ok"] is expected
    assert result["missed_active_poll"] is missed


def test_closed_window_is_not_a_missed_poll(readiness, tmp_path, monkeypatch):
    monkeypatch.setenv("ACCOUNTANT_POLL_WINDOWS", "06:00-09:30,16:00-22:00")
    monkeypatch.setenv("ACCOUNTANT_ACTIVE_POLL_INTERVAL_SECONDS", "900")
    path = write(
        tmp_path / "status.json",
        {
            "status": "complete",
            "exit_code": 0,
            "last_cycle_at": "2026-10-21T01:55:00Z",
        },
    )  # 21:55 previous evening
    assert readiness.scheduler_status(path, now=datetime(2026, 10, 21, 9, tzinfo=UTC))["ok"]
    assert not readiness.scheduler_status(path, now=datetime(2026, 10, 21, 11, tzinfo=UTC))["ok"]


def test_missing_or_stale_automation_never_completes(readiness, tmp_path):
    now = datetime.now(UTC).isoformat()
    summary = tmp_path / "summary.json"
    assert (
        readiness.record_cycle(tmp_path / "status", summary, 0, now, now, "x")["status"] == "failed"
    )
    write(summary, {"generated_at": "2000-01-01T00:00:00Z"})
    assert (
        readiness.record_cycle(tmp_path / "status", summary, 0, now, now, "x")["status"] == "failed"
    )
    write(
        summary,
        {
            "generated_at": now,
            "status": "complete",
            "storage": {"blocked": False},
            "steps": [{"returncode": 0}],
        },
    )
    result = readiness.record_cycle(tmp_path / "status", summary, 0, now, now, "x")
    assert result["status"] == "complete"
    assert result["last_success_at"] == now


def test_backup_local_evidence_and_unverified_legacy(readiness, tmp_path):
    now = datetime.now(UTC) - timedelta(seconds=1)
    payload = {"last_success_at": now.isoformat(), "last_error": "", "backup_bytes": 4}
    path = write(tmp_path / "status.json", payload)
    assert readiness.backup_status(path)["recovery_evidence"] == "unverified"
    payload["backup_bytes"] = 0
    assert not readiness.backup_status(write(path, payload))["ok"]
    payload.update(
        backup_bytes=4,
        archive_path="copy.dump",
        checksum_path="copy.sha256",
        restore_evidence_path="copy.restore",
    )
    assert not readiness.backup_status(write(path, payload))["ok"]
    (tmp_path / "copy.dump").write_bytes(b"dump")
    (tmp_path / "copy.sha256").write_text(hashlib.sha256(b"dump").hexdigest() + "  copy.dump\n")
    (tmp_path / "copy.restore").write_text("restore_verified_at=" + datetime.now(UTC).isoformat())
    assert readiness.backup_status(path)["recovery_evidence"] == "verified"
    (tmp_path / "copy.dump").write_bytes(b"tampered")
    assert not readiness.backup_status(path)["ok"]


def test_monitor_health_is_not_ready_and_no_secret_output(readiness, tmp_path):
    monitor = load("accountant_monitor")

    def handle(request):
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(404, text="SECRET endpoint unavailable")

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = monitor.collect(
            client, "http://fixture", tmp_path / "backup", tmp_path / "scheduler"
        )
        assert result["healthy"] is True
        assert result["ready"] is False
        assert "SECRET" not in json.dumps(result)
        assert monitor.notify(result, None, client) == "not_configured"
        assert monitor.notify(result, "http://fixture/SECRET", client) == "invalid_configuration"
        assert monitor.notify(result, "https://fixture/SECRET", client) == "failed"


@pytest.mark.parametrize("payload", [[], None, "secret", {"status": "ok"}])
def test_malformed_monitor_payload_fails_closed(readiness, tmp_path, payload):
    monitor = load("accountant_monitor")
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        assert not monitor.collect(client, "http://fixture", tmp_path / "b", tmp_path / "s")[
            "ready"
        ]


def test_shell_exit_zero_storage_blocked_is_paused(tmp_path):
    bash = shutil.which("bash") or (
        "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else None
    )
    if not bash or not Path(bash).exists():
        pytest.skip("Bash unavailable")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("run_vps_scheduler.sh", "vps_readiness_check.py"):
        (scripts / name).write_text((ROOT / "scripts" / name).read_text(), newline="\n")
    (scripts / "scheduler_timing.py").write_text(
        "import os, sys\nfrom pathlib import Path\n"
        "sys.exit(99) if Path(os.environ['DATA_DIR'], 'scheduler_cycle_status.json').exists() else print(0)\n"
    )
    (scripts / "run_accountant_automation.py").write_text(
        "import os, json\nfrom pathlib import Path\nfrom datetime import datetime, UTC\n"
        "Path(os.environ['ACCOUNTANT_CYCLE_SUMMARY_FILE']).write_text(json.dumps({"
        "'generated_at': datetime.now(UTC).isoformat(), 'storage': {'blocked': True, 'reason': 'database_cap_reached'}}))\n"
    )
    result = subprocess.run(
        [bash, "scripts/run_vps_scheduler.sh"],
        cwd=tmp_path,
        env={
            **os.environ,
            "ACCOUNTANT_PYTHON_BIN": sys.executable.replace("\\", "/"),
            "ACCOUNTANT_ACTIVE_POLL_INTERVAL_SECONDS": "0",
            "DATA_DIR": tmp_path.as_posix(),
            "PYTHONPATH": str(ROOT / "src"),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 99, result.stderr
    payload = json.loads((tmp_path / "scheduler_cycle_status.json").read_text())
    assert payload["status"] == "paused_storage", result.stdout + result.stderr
    assert payload["exit_code"] == 0
    assert "cycle complete" not in result.stdout
