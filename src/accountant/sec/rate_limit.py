from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class RateLimiter:
    """Minimum-interval limiter. SEC fair-access guidance is 10 requests/second."""

    _process_lock = threading.Lock()
    _process_last = 0.0

    def __init__(self, min_interval_seconds: float, *, state_path: Path | None = None) -> None:
        # Keep a safety margin below 10/s; zero is an explicit offline-test bypass.
        self.min_interval_seconds = max(0.12, min_interval_seconds) if min_interval_seconds > 0 else 0.0
        self._state_path = state_path

    def wait(self) -> None:
        with self.request_slot():
            pass

    @contextmanager
    def request_slot(self) -> Iterator[None]:
        """Hold the shared lease through dispatch, not merely admission.

        Record completion even on transport failure, so delayed threads cannot
        bunch requests after their reservations and violate the actual rate.
        """
        if self.min_interval_seconds <= 0:
            yield
            return
        with self._process_lock:
            if self._state_path is not None:
                with self._shared_slot():
                    yield
                return
            now = time.monotonic()
            remaining = self.min_interval_seconds - (now - RateLimiter._process_last)
            if remaining > 0:
                time.sleep(remaining)
            try:
                yield
            finally:
                RateLimiter._process_last = time.monotonic()

    @contextmanager
    def _shared_slot(self) -> Iterator[None]:
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
            try:
                yield
            finally:
                connection.execute("INSERT OR REPLACE INTO request_clock VALUES (1, ?)", (time.time(),))
                # Commit failure accounting even when the wrapped transport raises.
                connection.commit()
