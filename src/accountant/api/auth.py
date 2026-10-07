"""Authentication dependencies for state-changing Accountant endpoints."""

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from accountant.config import get_settings

_bearer = HTTPBearer(auto_error=False)


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
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
