"""ACC-LOW-015: quote refresh targets follow published cash-equity sessions."""

from datetime import UTC, datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

ET = ZoneInfo("America/New_York")


@pytest.mark.parametrize(
    "now,expected",
    [
        ("2026-10-30T16:01", "2026-11-02T09:30"),
        ("2026-11-01T08:00", "2026-11-02T09:30"),
        ("2026-11-25T16:01", "2026-11-27T09:30"),
        ("2026-11-26T08:00", "2026-11-27T09:30"),
        ("2026-11-27T12:00", "2026-11-27T13:00"),
        ("2026-11-27T13:01", "2026-11-30T09:30"),
        ("2026-12-24T12:00", "2026-12-24T13:00"),
        ("2027-12-31T08:00", "2027-12-31T09:30"),
        ("2028-07-03T12:00", "2028-07-03T13:00"),
        ("2026-11-02T10:00", "2026-11-02T16:00"),
    ],
)
def test_next_refresh_uses_market_sessions(now, expected):
    from accountant.research.buy_board import _next_refresh_time

    result = _next_refresh_time(datetime.fromisoformat(now).replace(tzinfo=ET))
    wanted = datetime.fromisoformat(expected).replace(tzinfo=ET)
    assert result == wanted
    assert result.astimezone(UTC) == wanted.astimezone(UTC)


@pytest.mark.parametrize("day", ["01-01", "01-19", "02-16", "04-03", "05-25", "06-19", "07-03", "09-07", "11-26", "12-25"])
def test_published_2026_holidays_are_closed(day):
    from accountant.ops.nyse_calendar import nyse_session

    assert nyse_session(datetime.fromisoformat(f"2026-{day}").date()) is None


def test_dst_wait_uses_elapsed_seconds_and_utc_inputs():
    from accountant.research.buy_board import _next_refresh_time, _refresh_wait_seconds

    before = datetime(2026, 10, 30, 16, 1, tzinfo=ET)
    target = _next_refresh_time(before)
    assert target.astimezone(UTC) == datetime(2026, 11, 2, 14, 30, tzinfo=UTC)
    assert _next_refresh_time(before.astimezone(UTC)) == target
    assert _refresh_wait_seconds(before, target) == 239340
    spring = datetime(2026, 3, 6, 16, 1, tzinfo=ET)
    assert _refresh_wait_seconds(spring, _next_refresh_time(spring)) == 232140


@pytest.mark.parametrize("year", [2025, 2029])
def test_unknown_calendar_year_and_naive_time_fail_closed(year):
    from accountant.research.buy_board import _next_refresh_time

    with pytest.raises(ValueError, match="published years"):
        _next_refresh_time(datetime(year, 1, 2, 8, tzinfo=ET))
    with pytest.raises(ValueError, match="aware"):
        _next_refresh_time(datetime(2026, 11, 2, 8))


@pytest.mark.parametrize(
    "observed,refreshes",
    [(datetime(2026, 11, 2, 9, 30, 1, tzinfo=ET), 1),
     (datetime(2026, 11, 7, 9, 30, tzinfo=ET), 0)],
)
def test_scheduler_skips_a_target_missed_during_suspend(monkeypatch, observed, refreshes):
    from accountant.research import buy_board as module

    moments = iter([datetime(2026, 10, 30, 16, 1, tzinfo=ET), observed])

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(moments)

    monkeypatch.setattr(module, "datetime", Clock)
    board = module.BuyBoardScheduler()
    board._stop = Mock()
    board._stop.is_set.side_effect = [False, True]
    board._stop.wait.return_value = False
    monkeypatch.setattr(board, "_prime_snapshot", lambda: None)
    refresh = Mock()
    monkeypatch.setattr(board, "_refresh", refresh)
    board._run()
    assert refresh.call_count == refreshes
    assert board.snapshot()["last_session_date"] == ("2026-11-02" if refreshes else None)


def test_early_close_labels_and_delayed_target_guards():
    from accountant.research.buy_board import _scheduled_refresh_due, _session_label

    target = datetime(2026, 11, 27, 13, tzinfo=ET)
    assert _session_label(target) == "CLOSE_1300"
    assert _session_label(datetime(2026, 11, 28, 9, 30, tzinfo=ET)) == "NON_SESSION"
    assert _scheduled_refresh_due(target, target.replace(minute=1))
    assert not _scheduled_refresh_due(target, target.replace(hour=16))
    assert not _scheduled_refresh_due(target, datetime(2026, 11, 28, 13, tzinfo=ET))


def test_scheduler_calendar_exhaustion_exposes_pause_without_quotes(monkeypatch):
    from accountant.research import buy_board as module

    board = module.BuyBoardScheduler()
    monkeypatch.setattr(board, "_prime_snapshot", lambda: None)
    monkeypatch.setattr(module, "_next_refresh_time", Mock(side_effect=ValueError("unsupported year")))
    refresh = Mock()
    monkeypatch.setattr(board, "_refresh", refresh)
    board._run()
    refresh.assert_not_called()
    assert board.snapshot()["next_refresh_at"] is None
    assert board.snapshot()["last_error"]
    assert "calendar unavailable" in board.snapshot()["last_action"]
