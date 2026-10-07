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
