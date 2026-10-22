"""Authentication dependencies for state-changing Accountant endpoints."""

import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from accountant.config import get_settings

_bearer = HTTPBearer(auto_error=False)


def require_research_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),  # noqa: B008
) -> str:
    """A separate GET-only credential never authorizes mutation endpoints."""
    settings = get_settings()
    expected = settings.research_api_token.strip()
    operator = settings.api_token.strip()
    allowed = [token for token in (expected, operator) if token]
    if not allowed:
        if settings.is_production:
            raise HTTPException(status_code=503, detail="Research API authentication is not configured.")
        return "development-no-auth"
    supplied = credentials.credentials if credentials else ""
    if not any(hmac.compare_digest(supplied.encode(), token.encode()) for token in allowed):
        raise HTTPException(
            status_code=401, detail="Invalid or missing research token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return supplied


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),  # noqa: B008
) -> str:
    """Require the configured bearer token outside local development/tests.

    Production must fail closed when the token is missing. Local development and
    tests remain usable without credentials so the API can be exercised safely.
    """

    settings = get_settings()
    expected = settings.api_token.strip()
    if not expected:
        if settings.is_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Mutation API authentication is not configured.",
            )
        return "development-no-auth"
    if credentials is None or not hmac.compare_digest(
        credentials.credentials.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
