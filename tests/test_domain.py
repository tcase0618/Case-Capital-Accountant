"""Tests for domain validators."""

import pytest

from accountant.domain.cik import normalize_cik
from accountant.domain.exceptions import AccountantError, MalformedTickerError
from accountant.domain.ticker import normalize_ticker


class TestCikNormalization:
    """Test CIK normalization."""

    def test_cik_simple_number(self):
        """Normalize simple numeric CIK."""
        assert normalize_cik(320193) == "0000320193"

    def test_cik_string(self):
        """Normalize string CIK."""
        assert normalize_cik("320193") == "0000320193"

    def test_cik_already_padded(self):
        """Accept already-padded CIK."""
        assert normalize_cik("0000320193") == "0000320193"

    def test_cik_with_leading_zeros_stripped(self):
        """Handle CIKs with leading zeros."""
        assert normalize_cik("00320193") == "0000320193"

    def test_cik_prefix_ignored(self):
        """Accept CIK with prefix."""
        assert normalize_cik("CIK0000320193") == "0000320193"
        assert normalize_cik("cik320193") == "0000320193"

    def test_cik_too_long_rejected(self):
        """Reject CIK that is too long."""
        with pytest.raises(AccountantError, match="malformed CIK"):
            normalize_cik("12345678901")  # 11 digits

    def test_cik_non_numeric_rejected(self):
        """Reject non-numeric CIK."""
        with pytest.raises(AccountantError, match="malformed CIK"):
            normalize_cik("ABCD1234")

    def test_cik_none_rejected(self):
        """Reject None CIK."""
        with pytest.raises(AccountantError, match="CIK is required"):
            normalize_cik(None)

    def test_cik_zero(self):
        """Accept CIK of zero."""
        assert normalize_cik("0") == "0000000000"


class TestTickerNormalization:
    """Test ticker normalization."""

    def test_ticker_simple_uppercase(self):
        """Normalize simple ticker."""
        assert normalize_ticker("AAPL") == "AAPL"

    def test_ticker_lowercase_converted(self):
        """Convert lowercase to uppercase."""
        assert normalize_ticker("aapl") == "AAPL"

    def test_ticker_mixed_case_converted(self):
        """Convert mixed case to uppercase."""
        assert normalize_ticker("AaPl") == "AAPL"

    def test_ticker_class_shares_with_dash(self):
        """Support class shares with dash."""
        assert normalize_ticker("BRK-B") == "BRK-B"

    def test_ticker_class_shares_with_dot(self):
        """Support class shares with dot."""
        assert normalize_ticker("BF.B") == "BF.B"

    def test_ticker_whitespace_stripped(self):
        """Strip whitespace."""
        assert normalize_ticker("  AAPL  ") == "AAPL"

    def test_ticker_none_rejected(self):
        """Reject None ticker."""
        with pytest.raises(MalformedTickerError, match="ticker is required"):
            normalize_ticker(None)

    def test_ticker_empty_rejected(self):
        """Reject empty ticker."""
        with pytest.raises(MalformedTickerError, match="ticker is required"):
            normalize_ticker("")

    def test_ticker_single_letter(self):
        """Accept single-letter tickers."""
        assert normalize_ticker("A") == "A"

    def test_ticker_too_long_rejected(self):
        """Reject tickers that are too long."""
        with pytest.raises(MalformedTickerError, match="malformed ticker"):
            normalize_ticker("ABCDEFGHIJK")  # 11 characters

    def test_ticker_invalid_characters_rejected(self):
        """Reject tickers with invalid characters."""
        with pytest.raises(MalformedTickerError, match="malformed ticker"):
            normalize_ticker("AA@L")
