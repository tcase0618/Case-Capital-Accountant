"""Offline regressions for the 2026-10-08 Accountant audit."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from accountant.config import Settings
from accountant.research import report_machine as module
from accountant.research.report_machine import ContinuousResearchMachine

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("environment", ["prod", "staging", "typo"])
def test_unknown_environment_rejected(environment):
    with pytest.raises(ValidationError):
        Settings(accountant_env=environment)


def test_production_environment_normalized():
    assert Settings(accountant_env=" production ").is_production


def test_statement_lane_exception_reaches_worker(monkeypatch):
    machine = ContinuousResearchMachine()
    monkeypatch.setattr(module, "_count", lambda session, model, company_id: 1 if model is module.CanonicalFact else 0)
    monkeypatch.setattr(module, "build_company_statement_snapshots", Mock(side_effect=RuntimeError("statement failure")))
    session = Mock()
    with pytest.raises(RuntimeError, match="statement failure"):
        machine._build_statements_lane(session, SimpleNamespace(id="company"), "TEST", 0, role="STATEMENTS")
    session.rollback.assert_called_once()


def test_worker_failure_survives_cycle_summary(monkeypatch):
    machine = ContinuousResearchMachine()
    engine = Mock()
    factory = Mock(return_value=Mock())
    monkeypatch.setattr(module, "create_db_engine", lambda: engine)
    monkeypatch.setattr(module, "create_session_factory", lambda engine: factory)
    monkeypatch.setattr(machine, "_storage_preflight", lambda engine: SimpleNamespace(allowed=True))
    monkeypatch.setattr(machine, "_sync_universes_if_needed", lambda session: None)
    monkeypatch.setattr(machine, "_refresh_progress_snapshot", lambda session: {
        "pending_companies": 1, "runnable_companies": 1,
        "blocked_companies": 0, "blocked_examples": [],
    })
    monkeypatch.setattr(machine, "_load_role_assignments", lambda session: [1])

    def fail(factory, assignments):
        machine._record_error(RuntimeError("statement failure"), worker_index=0, role="STATEMENTS", ticker="TEST")
        return []

    monkeypatch.setattr(machine, "_process_role_assignments", fail)
    machine._run_cycle()
    assert machine.snapshot()["last_error"]
    assert machine.snapshot()["recent_errors"][0]["worker_id"] == "1"


def test_production_build_uses_lockfiles():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "COPY pyproject.toml uv.lock" in dockerfile
    assert "uv sync --locked" in dockerfile
    assert "RUN npm ci" in dockerfile


def test_compose_health_is_separate_from_readiness():
    compose = (ROOT / "docker-compose.prod.yml").read_text()
    assert "127.0.0.1:${ACCOUNTANT_PUBLIC_PORT:-8010}:8010" in compose
    assert "vps_readiness_check.py" not in compose
    assert "/health" in compose


def test_ci_provides_dummy_compose_environment():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "cp .env.production.example .env.production" in workflow


def test_filings_rotation_ignores_report_age():
    from datetime import UTC, datetime

    from accountant.research.report_machine import _lane_sort_key

    checked = {"ticker": "AAA", "filings_count": 1, "filings_checked_at": datetime.now(UTC)}
    unchecked = {"ticker": "BBB", "filings_count": 1, "filings_checked_at": None}
    assert _lane_sort_key("filings", unchecked) < _lane_sort_key("filings", checked)


def test_six_k_amendment_is_reportable():
    from accountant.sec.forms import REPORT_CARD_FORMS

    assert "6-K/A" in module._REPORT_CARD_FILING_TYPES
    assert module._REPORT_CARD_FILING_TYPES == REPORT_CARD_FORMS


def test_token_comparison_uses_constant_time(monkeypatch):
    from fastapi.security import HTTPAuthorizationCredentials

    import accountant.api.auth as auth

    monkeypatch.setattr(auth, "get_settings", lambda: Settings(accountant_env="production", api_token="secret"))
    compare = Mock(return_value=True)
    monkeypatch.setattr(auth.hmac, "compare_digest", compare)
    assert auth.require_api_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials="secret")) == "secret"
    compare.assert_called_once_with(b"secret", b"secret")


def test_failed_filing_text_is_retried(monkeypatch):
    from accountant.research import filing_signal_engine as signals

    signals._fetch_filing_text_cached.cache_clear()
    client = Mock()
    client.get_text.side_effect = [RuntimeError("throttled"), "<p>Independent auditor</p>"]
    monkeypatch.setattr(signals, "SecClient", lambda **kwargs: SimpleNamespace(
        __enter__=lambda self: client,
    ))
    context = Mock()
    context.__enter__ = Mock(return_value=client)
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(signals, "SecClient", lambda **kwargs: context)
    assert signals.fetch_filing_text("https://www.sec.gov/test", "Test test@example.com") == ""
    assert signals.fetch_filing_text("https://www.sec.gov/test", "Test test@example.com") == "independent auditor"
    assert client.get_text.call_count == 2
    signals._fetch_filing_text_cached.cache_clear()


def test_failed_text_is_unknown_event(monkeypatch):
    from datetime import date

    from accountant.db.models import Filing
    from accountant.research.filing_signal_engine import build_event_red_flags

    filing = Filing(form_type="8-K", filing_date=date.today(), source_url="https://www.sec.gov/test")
    flags = build_event_red_flags([filing], sec_user_agent="test", fetch_text=lambda *args: "")
    assert flags.auditor_changed_flag is None
    assert flags.ceo_turnover_flag is None
    assert flags.cfo_turnover_flag is None


def test_independent_rate_limiters_share_clock(monkeypatch):
    import accountant.sec.rate_limit as limits

    clock = [100.0]
    monkeypatch.setattr(limits.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(limits.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(limits.RateLimiter, "_process_last", 0.0)
    for _ in range(12):
        limits.RateLimiter(0.12).wait()
    assert clock[0] >= 101.31


def test_every_mutation_and_external_data_route_requires_auth():
    from fastapi.routing import APIRoute

    from accountant.api.app import app
    from accountant.api.auth import require_api_token

    protected_reads = {"/api/integrations/ibkr", "/api/companies/{ticker}/market-quote"}
    checked = []
    for route in app.routes:
        if isinstance(route, APIRoute) and (route.methods - {"GET", "HEAD", "OPTIONS"} or route.path in protected_reads):
            assert any(dependency.call is require_api_token for dependency in route.dependant.dependencies), route.path
            checked.append(route.path)
    assert len(checked) == 9


def test_production_startup_does_not_create_unversioned_tables(monkeypatch):
    import accountant.api.app as app_module

    monkeypatch.setattr(app_module, "get_settings", lambda: Settings(accountant_env="production", machine_enabled=False))
    create = Mock()
    monkeypatch.setattr(app_module.Base.metadata, "create_all", create)
    monkeypatch.setattr(app_module, "_API_SESSION_FACTORY", Mock(return_value=Mock()))
    monkeypatch.setattr(app_module, "ensure_canonical_taxonomy_seeded", lambda session: None)
    for name in ("_ensure_dashboard_fact_totals_refresh", "_ensure_dashboard_metrics_refresh", "_ensure_companies_cache_refresh"):
        monkeypatch.setattr(app_module, name, lambda: None)
    monkeypatch.setattr(app_module.CACHE_WARMER, "start", lambda: None)
    app_module.startup_machine()
    create.assert_not_called()


def test_public_worker_error_omits_sql_and_connection_details():
    machine = ContinuousResearchMachine()
    machine._record_error(RuntimeError("[SQL: insert into private_table] host=internal token=private"))
    snapshot = machine.snapshot()
    assert snapshot["last_error"] == "research_worker_error"
    assert "private" not in str(snapshot)
    assert "[SQL:" not in str(snapshot)


def test_dev_database_is_loopback_only():
    assert '"127.0.0.1:5432:5432"' in (ROOT / "docker-compose.yml").read_text()


def test_backup_uses_matching_postgres_tools_and_isolated_restore():
    compose = (ROOT / "docker-compose.prod.yml").read_text()
    assert "image: postgres:16-bookworm" in compose
    assert "gosu postgres bash /scripts/backup_postgres.sh" in compose
    script = (ROOT / "scripts/verify_backup_restore.sh").read_text()
    assert "accountant_restore_test_*" in script
    assert "pg_restore --exit-on-error" in script
    assert "sha256sum --check" in script
    assert not any(line.lstrip().startswith("dropdb ") for line in script.splitlines())
