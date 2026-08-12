from __future__ import annotations

from pathlib import Path
from typing import Any

from accountant.config import Settings, get_settings


def duckdb_available() -> bool:
    try:
        import duckdb  # noqa: F401
    except ImportError:
        return False
    return True


def connect_duckdb(path: Path | None = None, *, settings: Settings | None = None) -> Any:
    import duckdb

    settings = settings or get_settings()
    db_path = path or settings.duckdb_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))
