import json
import os
import subprocess

import pytest

from test_oct9_backups import BASH, ROOT


@pytest.mark.parametrize(
    "exit_code,expected_status", [(7, "failed"), (75, "paused_storage"), (0, "complete")]
)
def test_failed_scheduler_cycle_persists_failure_and_reaches_next_poll(
    tmp_path, exit_code, expected_status
):
    script = tmp_path / "scheduler.sh"
    content = (ROOT / "scripts/run_vps_scheduler.sh").read_text()
    if os.environ.get("OCT9_TEST_BASELINE"):
        content = subprocess.check_output(
            ["git", "show", "a5ba414:scripts/run_vps_scheduler.sh"], cwd=ROOT, text=True
        )
    script.write_text(content, newline="\n")
    python_stub = tmp_path / "python-stub"
    python_stub.write_text(
        """#!/usr/bin/env bash
case "$1" in
*scheduler_timing.py)
  if [ -f "$CYCLE_MARKER" ]; then exit 99; fi
  echo 0;;
*run_accountant_automation.py) touch "$CYCLE_MARKER"; exit "$CYCLE_EXIT";;
esac
""",
        newline="\n",
    )
    python_stub.chmod(0o755)
    result = subprocess.run(
        [BASH, script.as_posix()],
        env={
            **os.environ,
            "ACCOUNTANT_PYTHON_BIN": python_stub.as_posix(),
            "ACCOUNTANT_ACTIVE_POLL_INTERVAL_SECONDS": "0",
            "DATA_DIR": tmp_path.as_posix(),
            "CYCLE_MARKER": (tmp_path / "cycle-marker").as_posix(),
            "CYCLE_EXIT": str(exit_code),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 99, result.stderr
    assert f"cycle {expected_status}" in result.stdout
    if exit_code:
        assert "cycle complete" not in result.stdout
    status = json.loads((tmp_path / "scheduler_cycle_status.json").read_text())
    assert status["status"] == expected_status
    assert status["exit_code"] == exit_code
    assert status["last_cycle_at"].endswith("Z")
    if expected_status == "paused_storage":
        assert status["reason"] == "storage_budget_exhausted"
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "scheduler_readiness", ROOT / "scripts/vps_readiness_check.py"
        )
        readiness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(readiness)
        assert not readiness.scheduler_status(tmp_path / "scheduler_cycle_status.json")["ok"]
