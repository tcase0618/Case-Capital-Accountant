"""Standard federal EDGAR closure calendar, for readiness (not trading dates).

Sources: https://www.sec.gov/submit-filings/filer-support-resources/edgar-calendar
and https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/
Ad-hoc SEC closures are not inferred. Update the version if closure rules change.
"""

from datetime import date, timedelta
from functools import lru_cache

CALENDAR_VERSION = "EDGAR_FEDERAL_HOLIDAYS_V1"


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _monday(year: int, month: int, occurrence: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(-first.weekday()) % 7 + 7 * (occurrence - 1))


@lru_cache(maxsize=32)
def edgar_holidays(year: int) -> frozenset[date]:
    """Observed recurring federal holidays for the modern (2021+) calendar."""
    if not 2021 <= year <= 9998:
        raise ValueError("EDGAR calendar supports years 2021 through 9998")
    last_may = date(year, 5, 31)
    november_first = date(year, 11, 1)
    holidays = {
        _observed(date(year, 1, 1)),
        _monday(year, 1, 3),
        _monday(year, 2, 3),
        last_may - timedelta(days=last_may.weekday()),
        _observed(date(year, 6, 19)),
        _observed(date(year, 7, 4)),
        _monday(year, 9, 1),
        _monday(year, 10, 2),
        _observed(date(year, 11, 11)),
        november_first + timedelta(days=(3 - november_first.weekday()) % 7 + 21),
        _observed(date(year, 12, 25)),
        # A Saturday New Year's Day is observed in the preceding calendar year.
        _observed(date(year + 1, 1, 1)),
    }
    return frozenset(day for day in holidays if day.year == year)


def edgar_business_days_since(latest: date, *, as_of: date) -> int:
    """Count EDGAR weekdays in (latest, as_of], including today's partial day.

    Counting today's partial day preserves the existing three-day tolerance;
    this does not claim that today's index has already been published.
    """
    if latest > as_of:
        raise ValueError("Latest filing is in the future")
    edgar_holidays(latest.year)
    edgar_holidays(as_of.year)
    total = 0
    day = latest
    while day < as_of:
        day += timedelta(days=1)
        if day.weekday() < 5 and day not in edgar_holidays(day.year):
            total += 1
    return total
