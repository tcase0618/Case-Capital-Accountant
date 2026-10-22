from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import accountant.api.auth as auth
from accountant.config import Settings


def _credentials(value: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=value)


def test_development_allows_missing_token(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: Settings(accountant_env="development", api_token=""),
    )

    assert auth.require_api_token(None) == "development-no-auth"


def test_production_fails_closed_without_token(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: Settings(accountant_env="production", api_token=""),
    )

    with pytest.raises(HTTPException) as error:
        auth.require_api_token(None)

    assert error.value.status_code == 503


def test_production_rejects_invalid_token(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: Settings(accountant_env="production", api_token="expected"),
    )

    with pytest.raises(HTTPException) as error:
        auth.require_api_token(_credentials("wrong"))

    assert error.value.status_code == 401


def test_production_accepts_configured_token(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: Settings(accountant_env="production", api_token="expected"),
    )

    assert auth.require_api_token(_credentials("expected")) == "expected"


def test_research_token_is_read_only(monkeypatch) -> None:
    monkeypatch.setattr(
        auth, "get_settings",
        lambda: Settings(accountant_env="production", api_token="operator", research_api_token="reader"),
    )
    assert auth.require_research_token(_credentials("reader")) == "reader"
    assert auth.require_research_token(_credentials("operator")) == "operator"
    with pytest.raises(HTTPException) as error:
        auth.require_api_token(_credentials("reader"))
    assert error.value.status_code == 401


@pytest.mark.parametrize("supplied", [None, "wrong"])
def test_production_research_rejects_missing_and_wrong_token(monkeypatch, supplied) -> None:
    monkeypatch.setattr(
        auth, "get_settings",
        lambda: Settings(accountant_env="production", api_token="operator", research_api_token="reader"),
    )
    with pytest.raises(HTTPException) as error:
        auth.require_research_token(_credentials(supplied) if supplied else None)
    assert error.value.status_code == 401


def test_production_research_fails_closed_without_configured_tokens(monkeypatch) -> None:
    monkeypatch.setattr(
        auth, "get_settings",
        lambda: Settings(accountant_env="production", api_token="", research_api_token=""),
    )
    with pytest.raises(HTTPException) as error:
        auth.require_research_token(None)
    assert error.value.status_code == 503
