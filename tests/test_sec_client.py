"""Tests for SEC client."""

from unittest.mock import patch

import pytest

from accountant.domain.exceptions import MalformedTickerError, TickerNotFoundError
from accountant.sec.client import SecClient, TickerResolution
from accountant.sec.exceptions import SecConfigError


class TestSecClientInitialization:
    """Test SecClient initialization."""

    def test_client_requires_user_agent(self, test_settings):
        """Client initialization requires SEC_USER_AGENT."""
        test_settings.sec_user_agent = ""
        with pytest.raises(SecConfigError, match="SEC_USER_AGENT is required"):
            SecClient(settings=test_settings)

    def test_client_initializes_with_user_agent(self, test_settings):
        """Client initializes with valid user agent."""
        client = SecClient(settings=test_settings)
        assert client is not None
        client.close()

    def test_client_context_manager(self, test_settings):
        """Client works as context manager."""
        with SecClient(settings=test_settings) as client:
            assert client is not None


class TestTickerResolution:
    """Test ticker resolution."""

    def test_ticker_resolution_dataclass(self):
        """TickerResolution is a frozen dataclass."""
        resolution = TickerResolution(ticker="AAPL", cik="0000320193", name="Apple Inc.")
        assert resolution.ticker == "AAPL"
        assert resolution.cik == "0000320193"
        assert resolution.name == "Apple Inc."

    def test_ticker_map_loaded_on_demand(self, test_settings):
        """Ticker map is loaded on first access."""
        client = SecClient(settings=test_settings)

        # Mock the HTTP response
        mock_response = {
            "0": {
                "cik_str": 320193,
                "ticker": "AAPL",
                "title": "Apple Inc.",
            },
            "1": {
                "cik_str": 789019,
                "ticker": "MSFT",
                "title": "Microsoft Corp.",
            },
        }

        with patch.object(client, '_get_json', return_value=mock_response):
            tickers = client.get_company_tickers()
            assert "AAPL" in tickers
            assert "MSFT" in tickers
            assert tickers["AAPL"].name == "Apple Inc."

        client.close()

    def test_cik_normalization(self, test_settings):
        """Client normalizes CIK input."""
        client = SecClient(settings=test_settings)
        assert client.normalize_cik(320193) == "0000320193"
        assert client.normalize_cik("320193") == "0000320193"
        assert client.normalize_cik("CIK0000320193") == "0000320193"
        client.close()

    def test_ticker_not_found_error(self, test_settings):
        """Raises error for unknown ticker."""
        client = SecClient(settings=test_settings)

        mock_response = {
            "0": {
                "cik_str": 320193,
                "ticker": "AAPL",
                "title": "Apple Inc.",
            },
        }

        with patch.object(client, '_get_json', return_value=mock_response), pytest.raises(
            TickerNotFoundError, match="not found"
        ):
            client.resolve_ticker("ZZZZ")

        client.close()

    def test_malformed_ticker_rejected(self, test_settings):
        """Malformed ticker is rejected before lookup."""
        client = SecClient(settings=test_settings)

        with pytest.raises(MalformedTickerError):
            client.resolve_ticker("@@@")

        client.close()


class TestArchiveDocumentUrl:
    """Test archive document URL construction."""

    def test_archive_document_url(self, test_settings):
        """Archive document URL is correctly formed."""
        client = SecClient(settings=test_settings)

        url = client.archive_document_url(
            cik="0000320193",
            accession_number="0000320193-24-000001",
            document="aapl-20231231.htm",
        )

        assert "https://www.sec.gov/Archives/edgar/data/" in url
        assert "320193/" in url
        assert "000032019324000001/" in url
        assert "aapl-20231231.htm" in url

        client.close()
