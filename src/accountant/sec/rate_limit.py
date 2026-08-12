from __future__ import annotations

import threading
import time


class RateLimiter:
    """Minimum-interval limiter. SEC fair-access guidance is 10 requests/second."""

    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval_seconds <= 0:
            return
        with self._lock:
            now = time.monotonic()
            remaining = self.min_interval_seconds - (now - self._last)
            if remaining > 0:
                time.sleep(remaining)
            self._last = time.monotonic()
