from __future__ import annotations

import json
import sqlite3
import sys
from collections.abc import Iterable

from sqlalchemy import create_engine, text


TABLES: tuple[str, ...] = (
    "companies",
    "company_reports",
    "filings",
    "raw_facts",
    "canonical_facts",
    "statement_snapshots",
    "report_cards",
    "research_records",
)


def _sqlite_counts(sqlite_path: str, tables: Iterable[str]) -> dict[str, int]:
    con = sqlite3.connect(sqlite_path)
    try:
        cur = con.cursor()
        counts: dict[str, int] = {}
        for table in tables:
            cur.execute(f"select count(*) from {table}")
            counts[table] = int(cur.fetchone()[0])
        return counts
    finally:
        con.close()


def _postgres_counts(database_url: str, tables: Iterable[str]) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            counts: dict[str, int] = {}
            for table in tables:
                counts[table] = int(conn.execute(text(f"select count(*) from {table}")).scalar_one())
            return counts
    finally:
        engine.dispose()


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_cutover_ready.py <sqlite_path> <postgres_url>")
        return 2

    sqlite_path = sys.argv[1]
    postgres_url = sys.argv[2]

    source = _sqlite_counts(sqlite_path, TABLES)
    target = _postgres_counts(postgres_url, TABLES)
    ready = all(source[table] == target[table] for table in TABLES)

    print(json.dumps({"ready": ready, "source": source, "target": target}))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
