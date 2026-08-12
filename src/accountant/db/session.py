from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from accountant.config import Settings, get_settings


def create_db_engine(url: str | None = None, *, settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    engine = create_engine(url or settings.database_url, pool_pre_ping=True, future=True)
    if engine.dialect.name == "sqlite":
        _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


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
