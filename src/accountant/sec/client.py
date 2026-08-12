from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from accountant.config import Settings, get_settings
from accountant.domain.cik import normalize_cik
from accountant.domain.exceptions import TickerNotFoundError
from accountant.domain.ticker import normalize_ticker
from accountant.logging import get_logger
from accountant.sec.exceptions import SecConfigError, SecHttpError, SecRetryableError
from accountant.sec.rate_limit import RateLimiter

log = get_logger(__name__)

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class TickerResolution:
    ticker: str
    cik: str
    name: str


class SecClient:
    """SEC EDGAR HTTP client. Deterministic, no LLM usage."""

    def __init__(
        self,
        user_agent: str | None = None,
        *,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
        min_interval_seconds: float | None = None,
        max_retries: int | None = None,
        timeout_seconds: float | None = None,
        backoff_min_seconds: float | None = None,
        backoff_max_seconds: float | None = None,
    ) -> None:
        settings = settings or get_settings()
        user_agent = (user_agent if user_agent is not None else settings.sec_user_agent).strip()
        if not user_agent:
            raise SecConfigError(
                "SEC_USER_AGENT is required and must identify the caller "
                "(example: 'Case Capital Accountant accountant@example.com')"
            )

        self._settings = settings
        self._user_agent = user_agent
        self._base_www = settings.sec_base_www.rstrip("/")
        self._base_data = settings.sec_base_data.rstrip("/")
        self._max_retries = max_retries if max_retries is not None else settings.sec_max_retries
        self._timeout = timeout_seconds if timeout_seconds is not None else settings.sec_timeout_seconds
        self._backoff_min = (
            backoff_min_seconds if backoff_min_seconds is not None else settings.sec_backoff_min_seconds
        )
        self._backoff_max = (
            backoff_max_seconds if backoff_max_seconds is not None else settings.sec_backoff_max_seconds
        )
        interval = (
            min_interval_seconds
            if min_interval_seconds is not None
            else settings.sec_min_interval_seconds
        )
        self._limiter = RateLimiter(interval)
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(
            timeout=httpx.Timeout(self._timeout),
            headers=self._headers(),
            follow_redirects=True,
        )
        self._ticker_map: dict[str, TickerResolution] | None = None

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> SecClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self._user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        }

    def normalize_cik(self, cik: str | int) -> str:
        return normalize_cik(cik)

    def cik_without_leading_zeros(self, cik: str | int) -> str:
        padded = self.normalize_cik(cik)
        return str(int(padded))

    def resolve_ticker(self, ticker: str) -> TickerResolution:
        symbol = normalize_ticker(ticker)
        mapping = self._load_ticker_map()
        resolved = mapping.get(symbol)
        if resolved is None:
            raise TickerNotFoundError(f"ticker not found in SEC company_tickers.json: {symbol}")
        log.info("sec.ticker_resolved", ticker=resolved.ticker, cik=resolved.cik, name=resolved.name)
        return resolved

    def get_company_tickers(self) -> dict[str, TickerResolution]:
        return dict(self._load_ticker_map())

    def get_submissions(self, cik: str | int) -> dict[str, Any]:
        padded = self.normalize_cik(cik)
        url = f"{self._base_data}/submissions/CIK{padded}.json"
        payload = self._get_json(url)
        if not isinstance(payload, dict):
            raise SecHttpError(200, url, "submissions payload is not an object")
        return payload

    def get_submissions_file(self, filename: str) -> dict[str, Any]:
        """Fetch a historical submissions shard listed under filings.files."""
        safe = filename.strip().lstrip("/")
        if not safe or ".." in safe or "/" in safe or "\\" in safe:
            raise SecHttpError(400, filename, "refusing malformed submissions filename")
        url = f"{self._base_data}/submissions/{safe}"
        payload = self._get_json(url)
        if not isinstance(payload, dict):
            raise SecHttpError(200, url, "submissions file payload is not an object")
        return payload

    def archive_document_url(self, cik: str | int, accession_number: str, document: str) -> str:
        cik_nolead = str(int(self.normalize_cik(cik)))
        accession_nodash = accession_number.replace("-", "")
        return (
            f"{self._base_www}/Archives/edgar/data/{cik_nolead}/"
            f"{accession_nodash}/{document}"
        )

    def _load_ticker_map(self) -> dict[str, TickerResolution]:
        if self._ticker_map is not None:
            return self._ticker_map
        url = f"{self._base_www}/files/company_tickers.json"
        payload = self._get_json(url)
        if not isinstance(payload, dict):
            raise SecHttpError(200, url, "company_tickers payload is not an object")
        mapping: dict[str, TickerResolution] = {}
        for row in payload.values():
            if not isinstance(row, dict):
                continue
            ticker_raw = row.get("ticker")
            cik_raw = row.get("cik_str")
            title = row.get("title")
            if ticker_raw is None or cik_raw is None:
                continue
            try:
                symbol = normalize_ticker(str(ticker_raw))
                cik = self.normalize_cik(cik_raw)
            except Exception:
                log.warning("sec.ticker_map_skip", ticker=ticker_raw, cik=cik_raw)
                continue
            mapping[symbol] = TickerResolution(
                ticker=symbol,
                cik=cik,
                name=str(title).strip() if title else symbol,
            )
        if not mapping:
            raise SecHttpError(200, url, "company_tickers.json contained no usable rows")
        self._ticker_map = mapping
        log.info("sec.ticker_map_loaded", count=len(mapping))
        return mapping

    def _get_json(self, url: str) -> Any:
        last_error: Exception | None = None
        attempts = max(1, self._max_retries)
        for attempt in range(1, attempts + 1):
            self._limiter.wait()
            try:
                started = time.monotonic()
                response = self._http.get(url, headers=self._headers())
                elapsed_ms = (time.monotonic() - started) * 1000
                log.info(
                    "sec.http",
                    url=url,
                    status=response.status_code,
                    attempt=attempt,
                    elapsed_ms=round(elapsed_ms, 1),
                )
                if response.status_code in _RETRYABLE_STATUS:
                    last_error = SecRetryableError(
                        response.status_code, url, response.text[:300]
                    )
                    if attempt < attempts:
                        delay = self._backoff(attempt)
                        log.warning(
                            "sec.retry",
                            url=url,
                            status=response.status_code,
                            attempt=attempt,
                            sleep_seconds=delay,
                        )
                        time.sleep(delay)
                        continue
                    raise last_error
                if response.status_code >= 400:
                    raise SecHttpError(response.status_code, url, response.text[:500])
                try:
                    return response.json()
                except ValueError as exc:
                    raise SecHttpError(response.status_code, url, "response is not valid JSON") from exc
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = SecRetryableError(0, url, str(exc))
                if attempt < attempts:
                    delay = self._backoff(attempt)
                    log.warning(
                        "sec.retry",
                        url=url,
                        error=str(exc),
                        attempt=attempt,
                        sleep_seconds=delay,
                    )
                    time.sleep(delay)
                    continue
                raise last_error from exc
        assert last_error is not None
        raise last_error

    def _backoff(self, attempt: int) -> float:
        delay = self._backoff_min * (2 ** (attempt - 1))
        return min(self._backoff_max, delay)
