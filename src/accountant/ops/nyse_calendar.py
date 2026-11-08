"""Published NYSE cash-equity sessions; not the federal EDGAR calendar.

Source: https://ir.theice.com/press/news-details/2025/NYSE-Group-Announces-2026-2027-and-2028-Holiday-and-Early-Closings-Calendar/
No runtime calendar requests. Extend the versioned table when NYSE publishes
later years; unsupported years fail closed. Unscheduled closures require an
explicit calendar update. This is not a trading/execution permission service.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

NYSE_CALENDAR_VERSION = "NYSE_CASH_2026_2028_V1"
ET = ZoneInfo("America/New_York")
_CLOSED = {
    2026: "01-01 01-19 02-16 04-03 05-25 06-19 07-03 09-07 11-26 12-25",
    2027: "01-01 01-18 02-15 03-26 05-31 06-18 07-05 09-06 11-25 12-24",
    # NYSE explicitly does not observe Saturday Jan 1, 2028 on Dec 31, 2027.
    2028: "01-17 02-21 04-14 05-29 06-19 07-04 09-04 11-23 12-25",
}
_EARLY_CLOSE = {
    2026: {"11-27", "12-24"},
    2027: {"11-26"},
    2028: {"07-03", "11-24"},
}


def nyse_session(day: date) -> tuple[datetime, datetime] | None:
    """Return aware regular-session boundaries, or None for a closed date."""
    if day.year not in _CLOSED:
        raise ValueError("NYSE calendar supports published years 2026 through 2028 only")
    month_day = day.strftime("%m-%d")
    if day.weekday() >= 5 or month_day in _CLOSED[day.year].split():
        return None
    close = time(13) if month_day in _EARLY_CLOSE[day.year] else time(16)
    return datetime.combine(day, time(9, 30), ET), datetime.combine(day, close, ET)
