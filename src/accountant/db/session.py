from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from accountant.config import Settings, get_settings

_SQLITE_WRITE_LOCK = threading.RLock()


def create_db_engine(url: str | None = None, *, settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    database_url = url or settings.database_url
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args = {
            "timeout": 120,
            "check_same_thread": False,
        }
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )
    if engine.dialect.name == "sqlite":
        _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=120000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def sqlite_write_guard(
    engine: Engine | None = None,
    *,
    url: str | None = None,
    settings: Settings | None = None,
    timeout_seconds: float | None = None,
) -> Iterator[None]:
    database_url = url
    if database_url is None and engine is not None:
        database_url = str(engine.url)
    if database_url is None:
        database_url = (settings or get_settings()).database_url
    if database_url.startswith("sqlite"):
        if timeout_seconds is None:
            with _SQLITE_WRITE_LOCK:
                yield
            return
        acquired = _SQLITE_WRITE_LOCK.acquire(timeout=timeout_seconds)
        if not acquired:
            raise TimeoutError(f"SQLite write guard busy after {timeout_seconds:.1f}s")
        try:
            yield
        finally:
            _SQLITE_WRITE_LOCK.release()
        return
    yield


@contextmanager
def session_scope(
    engine: Engine | None = None,
    *,
    settings: Settings | None = None,
) -> Iterator[Session]:
    own_engine = engine is None
    engine = engine or create_db_engine(settings=settings)
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        if own_engine:
            engine.dispose()
