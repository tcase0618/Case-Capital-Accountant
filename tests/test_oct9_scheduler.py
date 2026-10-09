import json
import os
import subprocess

from test_oct9_backups import BASH, ROOT


def test_failed_scheduler_cycle_persists_failure_and_reaches_next_poll(tmp_path):
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
*run_accountant_automation.py) touch "$CYCLE_MARKER"; exit 7;;
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
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 99, result.stderr
    assert "cycle failed" in result.stdout
    assert "cycle complete" not in result.stdout
    status = json.loads((tmp_path / "scheduler_cycle_status.json").read_text())
    assert status["status"] == "failed"
    assert status["exit_code"] == 7
    assert status["last_cycle_at"].endswith("Z")
