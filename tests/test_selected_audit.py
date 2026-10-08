"""Regression coverage for independently promoted audit fixes."""

import pytest


def test_api_uses_lifespan_registration():
    from accountant.api.app import app

    assert not app.router.on_startup
    assert not app.router.on_shutdown


@pytest.mark.asyncio
async def test_lifespan_stops_services_after_success_and_startup_failure(monkeypatch):
    import accountant.api.app as module

    calls = []
    monkeypatch.setattr(module, "startup_machine", lambda: calls.append("start"))
    monkeypatch.setattr(module, "shutdown_machine", lambda: calls.append("stop"))
    async with module.lifespan(module.app):
        assert calls == ["start"]
    assert calls == ["start", "stop"]

    def fail():
        raise RuntimeError("injected startup failure")

    monkeypatch.setattr(module, "startup_machine", fail)
    with pytest.raises(RuntimeError, match="injected startup failure"):
        async with module.lifespan(module.app):
            pytest.fail("failed startup must not enter running state")
    assert calls == ["start", "stop", "stop"]


def test_market_routes_require_operator_authentication(monkeypatch):
    from fastapi.testclient import TestClient

    import accountant.api.app as module
    from accountant.config import Settings

    monkeypatch.setattr(
        "accountant.api.auth.get_settings",
        lambda: Settings(accountant_env="production", api_token="test-token"),
    )
    monkeypatch.setattr(module, "alpaca_status", lambda: pytest.fail("unauthorized upstream call"))
    monkeypatch.setattr(module, "ibkr_quote", lambda *_: pytest.fail("unauthorized upstream call"))
    client = TestClient(module.app)
    assert client.get("/api/integrations/ibkr").status_code == 401
    assert client.get("/api/companies/TEST/market-quote").status_code == 401
