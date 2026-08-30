from __future__ import annotations

import argparse
import csv
import io
import sqlite3
from collections.abc import Iterable
from urllib.parse import urlparse

import psycopg
from sqlalchemy import func, select, text

from accountant.db import Base, create_db_engine, create_session_factory
from accountant.db.models import (  # noqa: F401
    BuyBoardCandidate,
    BuyBoardSnapshot,
    CalculationResult,
    CanonicalConcept,
    CanonicalFact,
    CanonicalMapping,
    Company,
    CompanyReport,
    Filing,
    FilingDocument,
    FinancialPeriod,
    RawFact,
    ReportCard,
    ResearchRecord,
    Security,
    StatementLine,
    StatementSnapshot,
)

CHUNK_SIZE = 10_000


def _table_models() -> list[type]:
    models: list[type] = []
    mapper_by_table = {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}
    for table in Base.metadata.sorted_tables:
        model = mapper_by_table.get(table.name)
        if model is not None:
            models.append(model)
    return models


def _sqlite_path_from_url(url: str) -> str:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ValueError(f"Unsupported SQLite URL: {url}")
    return url[len(prefix) :]


def _postgres_dsn_from_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme.startswith("postgresql"):
        raise ValueError(f"Unsupported PostgreSQL URL: {url}")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _sqlite_columns(con: sqlite3.Connection, table_name: str) -> list[str]:
    rows = con.execute(f"pragma table_info({table_name})").fetchall()
    return [str(row[1]) for row in rows]


def _truncate_target(target_url: str, models: list[type]) -> None:
    engine = create_db_engine(target_url)
    try:
        table_names = ", ".join(
            f'"{model.__tablename__}"' for model in reversed(models)
        )
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    finally:
        engine.dispose()


def _assert_empty_target(target_url: str, models: list[type]) -> None:
    engine = create_db_engine(target_url)
    factory = create_session_factory(engine)
    session = factory()
    try:
        existing = session.execute(select(func.count()).select_from(models[0])).scalar_one()
        if existing:
            raise RuntimeError("Target database is not empty. Re-run with --truncate-target.")
    finally:
        session.close()
        engine.dispose()


def _copy_table(sqlite_con: sqlite3.Connection, pg_con: psycopg.Connection, table_name: str) -> int:
    columns = _sqlite_columns(sqlite_con, table_name)
    col_list = ", ".join(f'"{column}"' for column in columns)
    select_sql = f"select {', '.join(columns)} from {table_name}"
    cursor = sqlite_con.execute(select_sql)
    copied = 0

    while True:
        rows = cursor.fetchmany(CHUNK_SIZE)
        if not rows:
            break

        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        for row in rows:
            writer.writerow(["\\N" if value is None else value for value in row])
        buffer.seek(0)

        with pg_con.cursor() as pg_cur:
            with pg_cur.copy(
                f"COPY {table_name} ({col_list}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')"
            ) as copy:
                copy.write(buffer.read())
        pg_con.commit()
        copied += len(rows)
        print(f"{table_name}: copied {copied}")

    return copied


def migrate(source_url: str, target_url: str, *, truncate_target: bool) -> None:
    models = _table_models()
    if truncate_target:
        print("truncating target tables")
        _truncate_target(target_url, models)
    else:
        print("validating empty target")
        _assert_empty_target(target_url, models)

    sqlite_path = _sqlite_path_from_url(source_url)
    postgres_dsn = _postgres_dsn_from_url(target_url)
    print(f"connecting to sqlite source: {sqlite_path}")
    print(f"connecting to postgres target: {postgres_dsn}")

    sqlite_con = sqlite3.connect(sqlite_path)
    sqlite_con.row_factory = None
    try:
        with psycopg.connect(postgres_dsn) as pg_con:
            pg_con.autocommit = False
            for model in models:
                print(f"starting table: {model.__tablename__}")
                copied = _copy_table(sqlite_con, pg_con, model.__tablename__)
                print(f"{model.__tablename__}: done {copied}")
    finally:
        sqlite_con.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk-copy THE ACCOUNTANT data from SQLite to PostgreSQL.")
    parser.add_argument("--source", required=True, help="SQLAlchemy SQLite source URL")
    parser.add_argument("--target", required=True, help="SQLAlchemy PostgreSQL target URL")
    parser.add_argument(
        "--truncate-target",
        action="store_true",
        help="Delete target rows before copying",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    migrate(args.source, args.target, truncate_target=args.truncate_target)


if __name__ == "__main__":
    main()
