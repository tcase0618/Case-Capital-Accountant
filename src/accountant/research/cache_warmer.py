from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from accountant.db import create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import Company, CompanyReport
from accountant.logging import get_logger
from accountant.research.buy_board import backfill_buy_board_candidates
from sqlalchemy import func, select

log = get_logger(__name__)


@dataclass
class CacheWarmSnapshot:
    running: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    phase: str | None = None
    last_action: str | None = None
    last_error: str | None = None
    reports_examined: int = 0
    active_candidates: int = 0
    monitor_candidates: int = 0


class CacheWarmer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot = CacheWarmSnapshot()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._snapshot.running = True
            self._snapshot.started_at = datetime.now(UTC).isoformat()
            self._snapshot.finished_at = None
            self._snapshot.phase = "queued"
            self._snapshot.last_action = "cache warm queued"
            self._snapshot.last_error = None
            self._thread = threading.Thread(target=self._run, daemon=True, name="accountant-cache-warmer")
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self._snapshot.running = False
            if self._snapshot.phase not in {"complete", "failed"}:
                self._snapshot.phase = "stopped"

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            running = bool(self._thread and self._thread.is_alive() and not self._stop.is_set())
            self._snapshot.running = running
            return {
                "running": running,
                "started_at": self._snapshot.started_at,
                "finished_at": self._snapshot.finished_at,
                "phase": self._snapshot.phase,
                "last_action": self._snapshot.last_action,
                "last_error": self._snapshot.last_error,
                "reports_examined": self._snapshot.reports_examined,
                "active_candidates": self._snapshot.active_candidates,
                "monitor_candidates": self._snapshot.monitor_candidates,
            }

    def _run(self) -> None:
        engine = create_db_engine()
        factory = create_session_factory(engine)
        session = factory()
        try:
            company_count = int(session.execute(select(func.count()).select_from(Company)).scalar_one())
            report_count = int(session.execute(select(func.count()).select_from(CompanyReport)).scalar_one())
            pending_count = max(0, company_count - report_count)
            if pending_count > 0:
                with self._lock:
                    self._snapshot.phase = "deferred"
                    self._snapshot.finished_at = datetime.now(UTC).isoformat()
                    self._snapshot.last_action = f"deferred until report backlog drains ({pending_count} pending)"
                    self._snapshot.last_error = None
                return
            with self._lock:
                self._snapshot.phase = "buy_board_backfill"
                self._snapshot.last_action = "warming cached buy board candidates"
            with sqlite_write_guard():
                summary = backfill_buy_board_candidates(session)
            if self._stop.is_set():
                session.rollback()
                with self._lock:
                    self._snapshot.phase = "stopped"
                    self._snapshot.last_action = "cache warm stopped"
                return
            with sqlite_write_guard():
                session.commit()
            with self._lock:
                self._snapshot.phase = "complete"
                self._snapshot.finished_at = datetime.now(UTC).isoformat()
                self._snapshot.last_action = "cache warm complete"
                self._snapshot.last_error = None
                self._snapshot.reports_examined = int(summary["reports_examined"])
                self._snapshot.active_candidates = int(summary["active_candidates"])
                self._snapshot.monitor_candidates = int(summary["monitor_candidates"])
        except Exception as exc:
            session.rollback()
            error_text = str(exc)[:500]
            log.warning("cache_warmer.failed", error=error_text)
            with self._lock:
                self._snapshot.phase = "failed"
                self._snapshot.finished_at = datetime.now(UTC).isoformat()
                self._snapshot.last_action = "cache warm failed"
                self._snapshot.last_error = error_text
        finally:
            session.close()
            engine.dispose()
            with self._lock:
                self._snapshot.running = False


CACHE_WARMER = CacheWarmer()
