class AccountantError(Exception):
    """Base error for THE ACCOUNTANT."""


class ConfigurationError(AccountantError):
    """Missing or invalid configuration."""


class MalformedTickerError(AccountantError):
    """Ticker failed validation. Never coerced into a guess."""


class TickerNotFoundError(AccountantError):
    """Ticker is well-formed but not present in the SEC ticker map."""


class MissingDataError(AccountantError):
    """Required source data is absent. Callers must not invent a substitute."""
