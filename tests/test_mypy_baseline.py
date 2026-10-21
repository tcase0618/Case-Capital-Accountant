import importlib.util
from collections import Counter
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "mypy_baseline_gate", Path(__file__).parents[1] / "scripts/check_mypy_baseline.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_baseline_normalizes_windows_paths_and_ignores_line_movement():
    windows = gate.diagnostics("src\\a.py:12: error: Broken type  [arg-type]\n")
    linux = gate.diagnostics("src/a.py:99: error: Broken type  [arg-type]\n")
    assert windows == linux


def test_new_error_fails_even_if_another_error_is_resolved():
    added, resolved = gate.compare(Counter({"new": 1}), Counter({"old": 2}))
    assert added == {"new": 1}
    assert resolved == {"old": 2}


def test_duplicate_errors_cannot_grow_and_resolved_debt_must_be_removed():
    assert gate.compare(Counter({"old": 2}), Counter({"old": 1}))[0] == {"old": 1}
    assert gate.compare(Counter(), Counter({"old": 1}))[1] == {"old": 1}


def test_notes_are_ignored_but_unknown_output_fails_closed():
    assert not gate.diagnostics("src/a.py:1: note: explanation\n")
    with pytest.raises(ValueError, match="Unrecognized"):
        gate.diagnostics("mypy: internal error")
