"""Tests for financial period resolver."""

from datetime import date

from accountant.financial.period_resolver import (
    RESOLVER_VERSION,
    FinancialPeriodResolver,
    ResolvedPeriod,
)


class TestResolvedPeriod:
    """Test ResolvedPeriod dataclass."""

    def test_instant_period(self):
        """Test creating instant (balance sheet) period."""
        period = ResolvedPeriod(
            period_type="INSTANT",
            fiscal_year=2024,
            fiscal_quarter=None,
            start_date=None,
            end_date=None,
            instant_date=date(2024, 12, 31),
            duration_days=None,
            fiscal_year_end="1231",
            is_ytd=False,
            is_derived=False,
            confidence="HIGH",
        )
        assert period.period_type == "INSTANT"
        assert period.instant_date == date(2024, 12, 31)
        assert period.confidence == "HIGH"

    def test_duration_period_with_warnings(self):
        """Test duration period with warnings."""
        period = ResolvedPeriod(
            period_type="Q1",
            fiscal_year=2024,
            fiscal_quarter=1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            instant_date=None,
            duration_days=90,
            fiscal_year_end="1231",
            is_ytd=False,
            is_derived=False,
            confidence="HIGH",
            warnings=["Minor duration variance"],
        )
        assert period.period_type == "Q1"
        assert period.fiscal_quarter == 1
        assert len(period.warnings) == 1


class TestFinancialPeriodResolver:
    """Test FinancialPeriodResolver logic."""

    def setup_method(self):
        """Initialize resolver."""
        self.resolver = FinancialPeriodResolver()

    def test_resolve_instant_fact(self):
        """Test resolution of balance sheet (instant) facts."""
        result = self.resolver.resolve_period(
            company_cik="0000789019",
            instant_date=date(2024, 12, 31),
            start_date=None,
            end_date=None,
            fiscal_year=2024,
            fiscal_period=None,
            frame=None,
            form="10-K",
            decimals=-6,
        )
        assert result.period_type == "INSTANT"
        assert result.fiscal_year == 2024
        assert result.instant_date == date(2024, 12, 31)
        assert result.confidence == "HIGH"
        assert result.is_derived is False

    def test_resolve_quarterly_duration(self):
        """Test resolution of Q1 quarterly fact."""
        result = self.resolver.resolve_period(
            company_cik="0000789019",
            instant_date=None,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="FY1",
            frame=None,
            form="10-Q",
            decimals=-6,
        )
        assert result.period_type == "Q1"
        assert result.fiscal_quarter == 1
        assert result.duration_days == 91  # Inclusive: Jan 1 to Mar 31 is 91 days
        assert result.confidence == "HIGH"

    def test_resolve_half_year_ytd(self):
        """Test resolution of 6-month YTD (half-year)."""
        result = self.resolver.resolve_period(
            company_cik="0000789019",
            instant_date=None,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            fiscal_year=2024,
            fiscal_period="FY2",
            frame=None,
            form="10-Q",
            decimals=-6,
        )
        assert result.period_type == "YTD_Q2"
        assert result.fiscal_quarter == 2
        assert result.is_ytd is True
        assert 181 <= result.duration_days <= 188

    def test_resolve_nine_month_ytd(self):
        """Test resolution of 9-month YTD."""
        result = self.resolver.resolve_period(
            company_cik="0000789019",
            instant_date=None,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 9, 30),
            fiscal_year=2024,
            fiscal_period="FY3",
            frame=None,
            form="10-Q",
            decimals=-6,
        )
        assert result.period_type == "YTD_Q3"
        assert result.fiscal_quarter == 3
        assert result.is_ytd is True
        assert 273 <= result.duration_days <= 283

    def test_resolve_full_year(self):
        """Test resolution of full-year (52-week) fact."""
        result = self.resolver.resolve_period(
            company_cik="0000789019",
            instant_date=None,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            fiscal_year=2024,
            fiscal_period="FY",
            frame="CY2024",
            form="10-K",
            decimals=-6,
        )
        assert result.period_type == "FY"
        assert result.fiscal_year == 2024
        assert 364 <= result.duration_days <= 366
        assert result.confidence == "HIGH"

    def test_resolve_53_week_year(self):
        """Test resolution of 53-week fiscal year."""
        result = self.resolver.resolve_period(
            company_cik="0000789019",
            instant_date=None,
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 6),  # 372 days (53 weeks)
            fiscal_year=2025,
            fiscal_period="FY",
            frame=None,
            form="10-K",
            decimals=-6,
        )
        assert result.period_type == "FY"
        assert 371 <= result.duration_days <= 374
        assert result.confidence == "MEDIUM"

    def test_resolve_insufficient_data(self):
        """Test resolution with no dates provided."""
        result = self.resolver.resolve_period(
            company_cik="0000789019",
            instant_date=None,
            start_date=None,
            end_date=None,
            fiscal_year=2024,
            fiscal_period=None,
            frame=None,
            form=None,
            decimals=None,
        )
        assert result.period_type == "UNKNOWN"
        assert result.confidence == "LOW"
        assert result.warnings is not None

    def test_fiscal_year_end_extraction(self):
        """Test extracting fiscal year end in MMDD format."""
        # December 31
        fye = self.resolver._extract_fiscal_year_end(date(2024, 12, 31))
        assert fye == "1231"

        # September 30
        fye = self.resolver._extract_fiscal_year_end(date(2024, 9, 30))
        assert fye == "0930"

        # June 30
        fye = self.resolver._extract_fiscal_year_end(date(2024, 6, 30))
        assert fye == "0630"

    def test_fiscal_year_derivation_calendar_year(self):
        """Test deriving fiscal year for calendar-year companies."""
        # For Dec 31 companies, FY = calendar year
        fy = self.resolver._derive_fiscal_year(date(2024, 12, 31), "1231")
        assert fy == 2024

        # January is in same calendar year as Dec 31 FYE
        fy = self.resolver._derive_fiscal_year(date(2024, 1, 31), "1231")
        assert fy == 2024

    def test_fiscal_year_derivation_non_calendar(self):
        """Test deriving fiscal year for non-calendar-year companies."""
        # Sept 30 FYE: if end_date is Sept 30, 2024, FY = 2024
        fy = self.resolver._derive_fiscal_year(date(2024, 9, 30), "0930")
        assert fy == 2024

        # Oct 1, 2024 is FY 2025 (after Sept 30, 2024 FYE)
        fy = self.resolver._derive_fiscal_year(date(2024, 10, 1), "0930")
        assert fy == 2025

        # June 30 FYE: July 1 is next fiscal year
        fy = self.resolver._derive_fiscal_year(date(2024, 7, 1), "0630")
        assert fy == 2025

        # June 30: same fiscal year
        fy = self.resolver._derive_fiscal_year(date(2024, 6, 30), "0630")
        assert fy == 2024

    def test_quarter_inference_by_month(self):
        """Test inferring quarter from start/end month."""
        # Q1 (ends March)
        q = self.resolver._infer_quarter_from_dates(1, 3)
        assert q == 1

        # Q2 (ends June)
        q = self.resolver._infer_quarter_from_dates(4, 6)
        assert q == 2

        # Q3 (ends September)
        q = self.resolver._infer_quarter_from_dates(7, 9)
        assert q == 3

        # Q4 (ends December)
        q = self.resolver._infer_quarter_from_dates(10, 12)
        assert q == 4

    def test_ytd_detection(self):
        """Test YTD period detection."""
        # 6-month YTD
        is_ytd = self.resolver._is_ytd_period(181)
        assert is_ytd is True

        # 9-month YTD
        is_ytd = self.resolver._is_ytd_period(273)
        assert is_ytd is True

        # 3-month quarter (not YTD)
        is_ytd = self.resolver._is_ytd_period(90)
        assert is_ytd is False

        # Full year (not YTD)
        is_ytd = self.resolver._is_ytd_period(365)
        assert is_ytd is False

    def test_resolve_period_versioning(self):
        """Test that resolver version is set on resolution."""
        # Resolver version should match
        assert RESOLVER_VERSION == "FINANCIAL_PERIOD_RESOLVER_V1"


class TestStandaloneQuarterDerivation:
    """Test standalone quarter derivation from YTD facts."""

    def setup_method(self):
        """Initialize resolver."""
        self.resolver = FinancialPeriodResolver()

    def test_derive_q2_from_ytd_minus_q1(self):
        """Test deriving Q2 from 6M YTD - Q1."""
        ytd_q2_value = 1000.0  # 6-month YTD
        q1_value = 300.0  # Q1
        unit = "USD"
        fiscal_year = 2024
        decimals = -6

        result, method = self.resolver.derive_standalone_quarter(
            ytd_q2_value=ytd_q2_value,
            q1_value=q1_value,
            ytd_q3_value=None,
            ytd_q2_for_q3=None,
            fy_value=None,
            ytd_q3_for_q4=None,
            unit=unit,
            fiscal_year=fiscal_year,
            decimals=decimals,
        )

        assert result is not None
        assert result["quarter"] == 2
        assert result["value"] == 700.0  # 1000 - 300
        assert result["unit"] == "USD"
        assert result["fiscal_year"] == 2024
        assert method == "YTD_MINUS_Q1"

    def test_derive_q3_from_ytd_minus_ytd(self):
        """Test deriving Q3 from 9M YTD - 6M YTD."""
        ytd_q3_value = 2000.0  # 9-month YTD
        ytd_q2_value = 1200.0  # 6-month YTD
        unit = "USD"
        fiscal_year = 2024
        decimals = -6

        result, method = self.resolver.derive_standalone_quarter(
            ytd_q2_value=None,
            q1_value=None,
            ytd_q3_value=ytd_q3_value,
            ytd_q2_for_q3=ytd_q2_value,
            fy_value=None,
            ytd_q3_for_q4=None,
            unit=unit,
            fiscal_year=fiscal_year,
            decimals=decimals,
        )

        assert result is not None
        assert result["quarter"] == 3
        assert result["value"] == 800.0  # 2000 - 1200
        assert result["unit"] == "USD"
        assert method == "YTD_MINUS_YTD"

    def test_derive_q4_from_fy_minus_ytd(self):
        """Test deriving Q4 from FY - 9M YTD."""
        fy_value = 3000.0  # Full year
        ytd_q3_value = 2000.0  # 9-month YTD
        unit = "USD"
        fiscal_year = 2024
        decimals = -6

        result, method = self.resolver.derive_standalone_quarter(
            ytd_q2_value=None,
            q1_value=None,
            ytd_q3_value=None,
            ytd_q2_for_q3=None,
            fy_value=fy_value,
            ytd_q3_for_q4=ytd_q3_value,
            unit=unit,
            fiscal_year=fiscal_year,
            decimals=decimals,
        )

        assert result is not None
        assert result["quarter"] == 4
        assert result["value"] == 1000.0  # 3000 - 2000
        assert result["unit"] == "USD"
        assert method == "FY_MINUS_YTD"

    def test_derive_missing_unit(self):
        """Test derivation fails with missing unit."""
        result, method = self.resolver.derive_standalone_quarter(
            ytd_q2_value=1000.0,
            q1_value=300.0,
            ytd_q3_value=None,
            ytd_q2_for_q3=None,
            fy_value=None,
            ytd_q3_for_q4=None,
            unit=None,  # Missing unit
            fiscal_year=2024,
            decimals=-6,
        )

        assert result is None
        assert method == "unit_missing"

    def test_derive_insufficient_data(self):
        """Test derivation fails with insufficient data."""
        result, method = self.resolver.derive_standalone_quarter(
            ytd_q2_value=None,
            q1_value=None,
            ytd_q3_value=None,
            ytd_q2_for_q3=None,
            fy_value=None,
            ytd_q3_for_q4=None,
            unit="USD",
            fiscal_year=2024,
            decimals=-6,
        )

        assert result is None
        assert method == "insufficient_data"

    def test_derive_with_negative_values(self):
        """Test derivation works with negative values (losses, decreases)."""
        ytd_q2_value = -100.0  # Loss YTD
        q1_value = -50.0  # Q1 loss
        unit = "USD"

        result, method = self.resolver.derive_standalone_quarter(
            ytd_q2_value=ytd_q2_value,
            q1_value=q1_value,
            ytd_q3_value=None,
            ytd_q2_for_q3=None,
            fy_value=None,
            ytd_q3_for_q4=None,
            unit=unit,
            fiscal_year=2024,
            decimals=-6,
        )

        assert result is not None
        assert result["value"] == -50.0  # -100 - (-50)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        """Initialize resolver."""
        self.resolver = FinancialPeriodResolver()

    def test_leap_year_february(self):
        """Test periods spanning February in leap year."""
        # 2024 is leap year (Feb 29 exists)
        result = self.resolver.resolve_period(
            company_cik="0000789019",
            instant_date=None,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 29),
            fiscal_year=2024,
            fiscal_period=None,
            frame=None,
            form="10-Q",
            decimals=-6,
        )
        assert result.duration_days == 60

    def test_fiscal_year_end_boundary(self):
        """Test period ending exactly on fiscal year end."""
        # Sept 30 FYE
        self.resolver.resolve_period(
            company_cik="0000789019",
            instant_date=None,
            start_date=date(2024, 10, 1),
            end_date=date(2024, 9, 30),  # Will be date math error, but test handling
            fiscal_year=None,
            fiscal_period=None,
            frame=None,
            form="10-Q",
            decimals=-6,
        )
        # Invalid date range (start > end) should be handled

    def test_single_day_period(self):
        """Test single-day period (start_date == end_date)."""
        result = self.resolver.resolve_period(
            company_cik="0000789019",
            instant_date=None,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
            fiscal_year=2024,
            fiscal_period=None,
            frame=None,
            form=None,
            decimals=None,
        )
        assert result.duration_days == 1
        assert result.period_type == "UNKNOWN"  # Not standard period

    def test_very_long_period(self):
        """Test period spanning multiple years."""
        result = self.resolver.resolve_period(
            company_cik="0000789019",
            instant_date=None,
            start_date=date(2023, 1, 1),
            end_date=date(2024, 12, 31),
            fiscal_year=None,
            fiscal_period=None,
            frame=None,
            form=None,
            decimals=None,
        )
        assert result.duration_days == 731  # 2023 (365) + 2024 (366) = 731
        assert result.period_type == "UNKNOWN"  # Over 2 years

    def test_fiscal_year_end_all_months(self):
        """Test fiscal year end extraction for all months."""
        for month in range(1, 13):
            # Use day 30 for easier testing (except Feb)
            day = 30 if month != 2 else 28
            test_date = date(2024, month, day)
            fye = self.resolver._extract_fiscal_year_end(test_date)
            expected = f"{month:02d}{day:02d}"
            assert fye == expected
