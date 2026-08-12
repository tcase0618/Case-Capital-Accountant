from accountant.domain.exceptions import AccountantError, ConfigurationError


class SecConfigError(ConfigurationError):
    """SEC client is missing required configuration."""


class SecHttpError(AccountantError):
    def __init__(self, status_code: int, url: str, body: str = "") -> None:
        self.status_code = status_code
        self.url = url
        self.body = body
        detail = f"SEC HTTP {status_code} for {url}"
        if body:
            detail = f"{detail}: {body[:300]}"
        super().__init__(detail)


class SecRetryableError(SecHttpError):
    """HTTP failure that should be retried (429 / 5xx / transport)."""
