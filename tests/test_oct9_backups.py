import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
BASH = shutil.which("bash") or ("C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else None)


@pytest.fixture
def shell(tmp_path):
    if not BASH or not Path(BASH).exists():
        pytest.skip("Bash unavailable; Linux CI runs shell regressions")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("backup_postgres.sh", "verify_backup_restore.sh", "archive_row_count.sh"):
        content = (ROOT / "scripts" / name).read_text()
        if os.environ.get("OCT9_TEST_BASELINE") and name != "archive_row_count.sh":
            content = subprocess.check_output(
                ["git", "show", f"a5ba414:scripts/{name}"], cwd=ROOT, text=True
            )
        (scripts / name).write_text(content, newline="\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stubs = {
        "psql": """case "$*" in
*current_database*pg_database_size*|*pg_database_size*) echo 1;;
*current_database*) echo accountant_restore_test_fixture;;
*information_schema*) echo 0;;
*"count(*)"*) echo "${RESTORED_COUNT:-1}";;
*) echo SOURCE_WAS_QUERIED >&2; exit 99;;
esac
""",
        "pg_dump": """for arg; do case "$arg" in --file=*) printf dump > "${arg#--file=}";; esac; done
""",
        "pg_restore": """case "$*" in
*--data-only*) printf 'COPY public.table (id) FROM stdin;\\n1\\n\\\\.\\n';;
*) exit 0;;
esac
""",
    }
    for name, body in stubs.items():
        path = bin_dir / name
        path.write_text("#!/usr/bin/env bash\n" + body, newline="\n")
        path.chmod(0o755)
    backup = tmp_path / "backups"
    backup.mkdir()
    # Git Bash uses a POSIX PATH even when invoked from Windows Python.
    env = {
        **os.environ,
        "DATABASE_URL": "dummy-source",
        "ACCOUNTANT_RESTORE_TEST_URL": "dummy-scratch",
        "ACCOUNTANT_BACKUP_DIR": backup.as_posix(),
        "ACCOUNTANT_BACKUP_MIN_FREE_BYTES": "0",
    }

    def run(name, *args, **extra):
        command = (
            'if command -v cygpath >/dev/null; then STUB_BIN=$(cygpath -u "$STUB_BIN"); fi; '
            'export PATH="$STUB_BIN:$PATH"; bash "$SCRIPT" "$@"'
        )
        return subprocess.run(
            [BASH, "-c", command, "fixture", *map(str, args)],
            env={
                **env,
                "STUB_BIN": bin_dir.as_posix(),
                "SCRIPT": (scripts / name).as_posix(),
                **extra,
            },
            capture_output=True,
            text=True,
            timeout=30,
        )

    return backup, run


def old_dump(directory, stamp):
    path = directory / f"accountant_{stamp}.dump"
    path.write_bytes(b"test archive")
    path.with_suffix(".dump.sha256").write_text(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n", newline="\n"
    )
    path.with_suffix(".dump.restore_verified").write_text("verified")
    old = time.time() - 30 * 86400
    os.utime(path, (old, old))
    return path


def test_blocked_backup_prunes_expired_sidecars_but_keeps_two_verified(shell):
    directory, run = shell
    oldest = old_dump(directory, "20260101T000000Z")
    kept = [old_dump(directory, stamp) for stamp in ("20260102T000000Z", "20260103T000000Z")]
    result = run("backup_postgres.sh", ACCOUNTANT_BACKUP_MIN_FREE_BYTES="999999999999999")
    assert result.returncode == 1, result.stderr
    assert not oldest.exists()
    assert not oldest.with_suffix(".dump.sha256").exists()
    assert not oldest.with_suffix(".dump.restore_verified").exists()
    assert all(path.exists() for path in kept)
    status = json.loads((directory / "status.json").read_text())
    assert status["last_error"] == "insufficient_disk_headroom"
    assert status["backup_bytes"] > 0


def test_restore_uses_dump_snapshot_not_current_source(shell):
    directory, run = shell
    backup = run("backup_postgres.sh")
    assert backup.returncode == 0, backup.stderr
    dump = next(directory.glob("*.dump"))
    assert (
        dump.with_suffix(".dump.counts").read_text() == "companies\t1\nfilings\t1\nraw_facts\t1\n"
    )
    # The psql stub rejects every source query unrelated to the dump preflight.
    verified = run("verify_backup_restore.sh", dump.as_posix())
    assert verified.returncode == 0, verified.stderr
    assert dump.with_suffix(".dump.restore_verified").exists()
    mismatch = run("verify_backup_restore.sh", dump.as_posix(), RESTORED_COUNT="0")
    assert mismatch.returncode == 1
    assert "row count mismatch" in mismatch.stderr


def test_backup_readiness_fails_on_missing_stale_or_failed_status(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "readiness", ROOT / "scripts/vps_readiness_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "status.json"
    assert not module.backup_status(path)["ok"]
    status = {
        "last_success_at": datetime.now(UTC).isoformat(),
        "last_error": "",
        "backup_bytes": 10,
    }
    path.write_text(json.dumps(status))
    assert module.backup_status(path)["ok"]
    status["last_error"] = "insufficient_disk_headroom"
    path.write_text(json.dumps(status))
    assert not module.backup_status(path)["ok"]
    status.update(last_error="", last_success_at="2020-01-01T00:00:00Z")
    path.write_text(json.dumps(status))
    assert not module.backup_status(path)["ok"]


def test_restore_runbook_has_no_production_drop_and_uses_mounted_scripts():
    docs = (ROOT / "docs/vps_readiness.md").read_text()
    assert "dropdb" not in docs
    assert "exec backup gosu postgres bash /scripts/backup_postgres.sh" in docs
    assert "gosu postgres bash /scripts/verify_backup_restore.sh" in docs
