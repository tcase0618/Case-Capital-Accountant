"""ACC-MED-022: public status reads share bounded database work."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from sqlalchemy import event


def test_public_status_requests_do_not_repeat_canonical_scans(test_session, test_engine):
    from accountant.api import app as api

    scans = []

    def record(_connection, _cursor, statement, _parameters, _context, _many):
        if "count(*) from canonical_facts" in statement.lower():
            scans.append(statement)

    event.listen(test_engine, "before_cursor_execute", record)
    try:
        first = api.source_integrity(test_session)
        first_scan_count = len(scans)
        assert first_scan_count > 0
        api.source_integrity(test_session)
        api.deployment_readiness(test_session)
        assert len(scans) == first_scan_count
        assert first.source_grade == "FAILED"
    finally:
        event.remove(test_engine, "before_cursor_execute", record)


def test_cache_expiry_failure_and_caller_mutation(test_session, monkeypatch):
    from accountant.research import source_integrity as module

    clock = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    build = Mock(return_value={"generated_at": "original", "truth_policy": {}, "warnings": []})
    monkeypatch.setattr(module, "build_source_integrity_snapshot", build)
    cache = module.SourceIntegrityCache()
    first = cache.snapshot(test_session)
    first["warnings"].append("caller mutation")
    assert cache.snapshot(test_session)["warnings"] == []
    assert build.call_count == 1
    clock[0] += module.SOURCE_INTEGRITY_CACHE_TTL_SECONDS
    build.side_effect = RuntimeError("fixture database unavailable")
    with pytest.raises(RuntimeError):
        cache.snapshot(test_session)
    build.side_effect = None
    build.return_value = {"generated_at": "new", "truth_policy": {}, "warnings": []}
    assert cache.snapshot(test_session)["generated_at"] == "new"
    assert build.call_count == 3


def test_concurrent_refresh_is_single_flight_and_engines_are_isolated(test_engine, monkeypatch):
    from accountant.research import source_integrity as module

    build = Mock(return_value={"truth_policy": {}, "warnings": []})
    monkeypatch.setattr(module, "build_source_integrity_snapshot", build)
    cache = module.SourceIntegrityCache()
    session = Mock()
    session.get_bind.return_value = test_engine
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: cache.snapshot(session), range(8)))
    assert len(results) == 8
    assert build.call_count == 1
    other = Mock()
    other.get_bind.return_value = Mock()
    cache.snapshot(other)
    assert build.call_count == 2
