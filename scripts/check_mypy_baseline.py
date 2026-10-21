"""ACC-LOW-005: full-src type debt must not grow or silently change.

The checked-in baseline is debt, not a clean type-check claim. Resolved entries
must be removed; new diagnostics fail even when the total count decreases.
Never regenerate this baseline automatically in CI.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests/mypy_baseline.json"
COMMAND = [
    sys.executable,
    "-m",
    "mypy",
    "src",
    "--platform",
    "linux",
    "--python-version",
    "3.12",
    "--show-error-codes",
    "--no-error-summary",
    "--no-pretty",
    "--hide-error-context",
]
ERROR = re.compile(r"^(.+?):\d+(?::\d+)?: error: (.+)  \[([-\w]+)\]$")


def diagnostics(output: str) -> Counter[str]:
    found: Counter[str] = Counter()
    for line in output.splitlines():
        if not line.strip() or ": note: " in line:
            continue
        match = ERROR.fullmatch(line)
        if match is None:
            raise ValueError(f"Unrecognized mypy output: {line}")
        path, message, code = match.groups()
        found[f"{path.replace(chr(92), '/')} [{code}] {message}"] += 1
    return found


def compare(current: Counter[str], baseline: Counter[str]) -> tuple[Counter[str], Counter[str]]:
    return current - baseline, baseline - current


def main() -> int:
    result = subprocess.run(COMMAND, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode not in (0, 1) or result.stderr.strip():
        print("Mypy failed to run; baseline was not evaluated.")
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return 1
    try:
        current = diagnostics(result.stdout)
        baseline = Counter(json.loads(BASELINE.read_text(encoding="utf-8"))["diagnostics"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Baseline check failed: {exc}")
        return 1
    added, resolved = compare(current, baseline)
    for diagnostic, count in sorted(added.items()):
        print(f"NEW ({count}): {diagnostic}")
    for diagnostic, count in sorted(resolved.items()):
        print(f"RESOLVED; remove from baseline ({count}): {diagnostic}")
    if added or resolved:
        return 1
    print(
        f"Full-src mypy debt unchanged: {sum(current.values())} existing errors; no new diagnostics."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
