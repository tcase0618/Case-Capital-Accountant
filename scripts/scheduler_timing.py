from __future__ import annotations

import argparse
from datetime import datetime

from accountant.ops.polling_schedule import (
    DEFAULT_WINDOWS,
    EASTERN,
    parse_windows,
    seconds_until_next_poll,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Return the sleep time before the next SEC polling cycle.")
    parser.add_argument("--windows", default=DEFAULT_WINDOWS)
    parser.add_argument("--active-interval-seconds", type=int, default=900)
    args = parser.parse_args()
    if args.active_interval_seconds <= 0:
        raise ValueError("active polling interval must be positive")
    print(
        seconds_until_next_poll(
            datetime.now(EASTERN),
            windows=parse_windows(args.windows),
            active_interval_seconds=args.active_interval_seconds,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
