from datetime import datetime
from zoneinfo import ZoneInfo

from accountant.ops.polling_schedule import parse_windows, seconds_until_next_poll

EASTERN = ZoneInfo("America/New_York")


def test_polling_schedule_starts_immediately_inside_active_window() -> None:
    delay = seconds_until_next_poll(
        datetime(2026, 9, 21, 8, 0, tzinfo=EASTERN),
        windows=parse_windows("06:00-09:30,16:00-22:00"),
        active_interval_seconds=900,
    )

    assert delay == 0


def test_polling_schedule_waits_until_after_market_window() -> None:
    delay = seconds_until_next_poll(
        datetime(2026, 9, 21, 10, 0, tzinfo=EASTERN),
        windows=parse_windows("06:00-09:30,16:00-22:00"),
        active_interval_seconds=900,
    )

    assert delay == 6 * 60 * 60


def test_polling_schedule_waits_until_next_business_day_window() -> None:
    delay = seconds_until_next_poll(
        datetime(2026, 9, 21, 22, 30, tzinfo=EASTERN),
        windows=parse_windows("06:00-09:30,16:00-22:00"),
        active_interval_seconds=900,
    )

    assert delay == 7 * 60 * 60 + 30 * 60


def test_wait_across_spring_dst_uses_elapsed_utc_time():
    delay = seconds_until_next_poll(
        datetime(2026, 3, 7, 22, 30, tzinfo=EASTERN),
        windows=parse_windows("06:00-09:30,16:00-22:00"), active_interval_seconds=900,
    )
    assert delay == 6 * 60 * 60 + 30 * 60


def test_wait_across_fall_dst_uses_elapsed_utc_time():
    delay = seconds_until_next_poll(
        datetime(2026, 10, 31, 22, 30, tzinfo=EASTERN),
        windows=parse_windows("06:00-09:30,16:00-22:00"), active_interval_seconds=900,
    )
    assert delay == 8 * 60 * 60 + 30 * 60
