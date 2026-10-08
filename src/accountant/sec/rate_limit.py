from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


class RateLimiter:
    """Minimum-interval limiter. SEC fair-access guidance is 10 requests/second."""

    _process_lock = threading.Lock()
    _process_last = 0.0

    def __init__(self, min_interval_seconds: float, *, state_path: Path | None = None) -> None:
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self._state_path = state_path

    def wait(self) -> None:
        if self.min_interval_seconds <= 0:
            return
        with self._process_lock:
            if self._state_path is not None:
                self._wait_shared()
                return
            now = time.monotonic()
            remaining = self.min_interval_seconds - (now - RateLimiter._process_last)
            if remaining > 0:
                time.sleep(remaining)
            RateLimiter._process_last = time.monotonic()

    def _wait_shared(self) -> None:
        """Serialize reservations across processes sharing the data volume.

        This tiny operational database contains no SEC source facts. SQLite's
        write lock is released even if the requesting process exits.
        """
        assert self._state_path is not None
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._state_path, timeout=30) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS request_clock (id INTEGER PRIMARY KEY, last_at REAL NOT NULL)")
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT last_at FROM request_clock WHERE id = 1").fetchone()
            remaining = self.min_interval_seconds - (time.time() - row[0]) if row else 0
            if remaining > 0:
                time.sleep(remaining)
            connection.execute("INSERT OR REPLACE INTO request_clock VALUES (1, ?)", (time.time(),))
