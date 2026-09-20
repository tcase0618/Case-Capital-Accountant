"""Eastern-time polling schedule for SEC ingestion windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
DEFAULT_WINDOWS = "06:00-09:30,16:00-22:00"


@dataclass(frozen=True)
class PollWindow:
    start: time
    end: time


def parse_windows(value: str = DEFAULT_WINDOWS) -> list[PollWindow]:
    windows: list[PollWindow] = []
    for raw_window in value.split(","):
        start_raw, separator, end_raw = raw_window.strip().partition("-")
        if not separator:
            raise ValueError(f"invalid poll window: {raw_window!r}")
        start = time.fromisoformat(start_raw)
        end = time.fromisoformat(end_raw)
        if end <= start:
            raise ValueError(f"poll window must end after it starts: {raw_window!r}")
        windows.append(PollWindow(start=start, end=end))
    if not windows:
        raise ValueError("at least one poll window is required")
    return sorted(windows, key=lambda item: item.start)


def seconds_until_next_poll(
    now: datetime,
    *,
    windows: list[PollWindow],
    active_interval_seconds: int,
) -> int:
    """Return 0 inside a window or the delay until the next active window."""

    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local_now = now.astimezone(EASTERN)
    for window in windows:
        start_at = datetime.combine(local_now.date(), window.start, tzinfo=EASTERN)
        end_at = datetime.combine(local_now.date(), window.end, tzinfo=EASTERN)
        if start_at <= local_now < end_at:
            remaining = int((end_at - local_now).total_seconds())
            return max(1, min(active_interval_seconds, remaining))
        if local_now < start_at:
            return max(1, int((start_at - local_now).total_seconds()))

    next_start = datetime.combine(local_now.date() + timedelta(days=1), windows[0].start, tzinfo=EASTERN)
    return max(1, int((next_start - local_now).total_seconds()))
