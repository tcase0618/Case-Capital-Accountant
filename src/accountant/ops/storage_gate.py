"""Shared admission checks for bounded research write jobs."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Any

from sqlalchemy import text

from accountant.config import get_settings
from accountant.ops.storage_budget import StorageBudget, evaluate_storage_budget

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_ADVISORY_KEY = 7161923401


class StorageGate:
    """Serialize guarded writers and re-measure before each job.

    PostgreSQL's session advisory lock coordinates the API and scheduler
    processes and is released by PostgreSQL if a process dies. Holding it
    throughout a job prevents another process from spending the same reserve.
    Each gate keeps its original cycle baseline, rather than resetting it at
    every admission. A reserve estimates job growth; it is not a byte quota.
    """

    def __init__(self, *, engine: Any, data_dir: Path, budget: StorageBudget, reserve_mb: int) -> None:
        self._engine = engine
        self._data_dir = data_dir
        self._budget = budget
        self._reserve_bytes = max(0, reserve_mb) * 1024 * 1024
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(str(engine.url), threading.Lock())
        self._local = threading.local()
        self._start_database_bytes = self._database_size()
        self.stop_reason: str | None = None

    @classmethod
    def from_settings(cls, engine: Any) -> StorageGate:
        settings = get_settings()
        return cls(
            engine=engine, data_dir=settings.data_dir,
            budget=StorageBudget(settings.storage_max_database_gb, settings.storage_min_free_disk_gb,
                                 settings.storage_max_cycle_growth_gb),
            reserve_mb=settings.storage_worker_reserve_mb,
        )

    @property
    def enabled(self) -> bool:
        return any((self._budget.max_database_bytes, self._budget.min_free_disk_bytes,
                    self._budget.max_cycle_growth_bytes))

    def claim(self) -> bool:
        if not self.enabled:
            return True
        self._lock.acquire()
        self._local.claimed = True
        self._local.connection = None
        try:
            if self._engine.dialect.name == "postgresql":
                connection = self._engine.connect().execution_options(isolation_level="AUTOCOMMIT")
                self._local.connection = connection
                connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": _ADVISORY_KEY})
            data_path = self._data_dir if self._data_dir.exists() else self._data_dir.parent
            decision = evaluate_storage_budget(
                self._budget, database_bytes=self._database_size(),
                disk_free_bytes=shutil.disk_usage(data_path).free,
                cycle_start_database_bytes=self._start_database_bytes,
                reserved_bytes=self._reserve_bytes,
            )
            if not decision.allowed:
                self.stop_reason = decision.reason
                self.release()
                return False
            return True
        except BaseException:
            self.release()
            raise

    def release(self) -> None:
        if not getattr(self._local, "claimed", False):
            return
        connection = self._local.connection
        try:
            if connection is not None:
                try:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _ADVISORY_KEY})
                except BaseException:
                    # Do not return a still-locked backend to the pool.
                    connection.invalidate()
                    raise
                finally:
                    connection.close()
        finally:
            self._local.claimed = False
            self._lock.release()

    def _database_size(self) -> int:
        if self._engine.dialect.name != "postgresql":
            return 0
        connection = getattr(self._local, "connection", None)
        if connection is not None:
            return int(connection.execute(text("SELECT pg_database_size(current_database())")).scalar_one())
        with self._engine.connect() as connection:
            return int(connection.execute(text("SELECT pg_database_size(current_database())")).scalar_one())
