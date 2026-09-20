from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import psycopg

from accountant.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOP_LEVEL_PATHS = (
    ".run",
    "data",
    "artifacts",
    "backups",
    "frontend",
    "src",
    "scripts",
    "tests",
)


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")

    payload: dict[str, Any] = {
        "repo_root": str(REPO_ROOT),
        "vps_disk_gb": args.vps_disk_gb,
        "filesystem": _filesystem_snapshot(args.top),
        "postgres": _postgres_snapshot(dsn),
    }
    payload["vps_fit"] = _fit_assessment(payload, args.vps_disk_gb)

    print(json.dumps(payload, indent=2))
    return 1 if payload["vps_fit"]["status"] == "FAIL" else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure Accountant storage and VPS fit.")
    parser.add_argument("--vps-disk-gb", type=float, default=50.0, help="Target VPS disk size to assess.")
    parser.add_argument(
        "--top",
        nargs="*",
        default=list(DEFAULT_TOP_LEVEL_PATHS),
        help="Top-level repo paths to size.",
    )
    return parser.parse_args()


def _filesystem_snapshot(paths: list[str]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    total = 0
    for relative in paths:
        path = REPO_ROOT / relative
        size = _path_size(path)
        total += size
        items.append(
            {
                "path": relative,
                "exists": path.exists(),
                "bytes": size,
                "gb": _gb(size),
            }
        )
    return {
        "measured_paths_total_bytes": total,
        "measured_paths_total_gb": _gb(total),
        "paths": sorted(items, key=lambda item: item["bytes"], reverse=True),
    }


def _postgres_snapshot(dsn: str) -> dict[str, Any]:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("select pg_database_size(current_database())")
        database_size = int(cur.fetchone()[0] or 0)
        cur.execute(
            """
            select
              relname,
              pg_total_relation_size(c.oid) as total_bytes,
              pg_relation_size(c.oid) as table_bytes,
              pg_indexes_size(c.oid) as index_bytes
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public'
              and c.relkind in ('r', 'p')
            order by pg_total_relation_size(c.oid) desc
            """
        )
        tables = [
            {
                "table": row[0],
                "total_bytes": int(row[1] or 0),
                "total_gb": _gb(int(row[1] or 0)),
                "table_gb": _gb(int(row[2] or 0)),
                "index_gb": _gb(int(row[3] or 0)),
            }
            for row in cur.fetchall()
        ]

    derived_bytes = sum(
        table["total_bytes"]
        for table in tables
        if table["table"] not in {"raw_facts"}
    )
    return {
        "database_size_bytes": database_size,
        "database_size_gb": _gb(database_size),
        "derived_without_raw_facts_bytes": derived_bytes,
        "derived_without_raw_facts_gb": _gb(derived_bytes),
        "largest_tables": tables[:20],
    }


def _fit_assessment(payload: dict[str, Any], vps_disk_gb: float) -> dict[str, Any]:
    postgres = payload["postgres"]
    full_db_gb = float(postgres["database_size_gb"])
    derived_gb = float(postgres["derived_without_raw_facts_gb"])
    os_docker_buffer_gb = 12.0
    safe_free_buffer_gb = max(vps_disk_gb * 0.20, 10.0)
    required_full_gb = full_db_gb + os_docker_buffer_gb + safe_free_buffer_gb
    required_derived_gb = derived_gb + os_docker_buffer_gb + safe_free_buffer_gb

    if required_full_gb <= vps_disk_gb:
        status = "PASS"
        recommendation = "Full Postgres deployment fits with safety buffer."
    elif required_derived_gb <= vps_disk_gb:
        status = "LEAN_ONLY"
        recommendation = (
            "Full raw warehouse does not fit. A derived/read-only deployment may fit, "
            "but raw/canonical rebuild and fact drill-down need external storage or a schema refactor."
        )
    else:
        status = "FAIL"
        recommendation = "Target VPS is too small even for a safe derived-data deployment."

    return {
        "status": status,
        "recommendation": recommendation,
        "assumptions": {
            "os_docker_buffer_gb": os_docker_buffer_gb,
            "safe_free_buffer_gb": round(safe_free_buffer_gb, 2),
        },
        "required_full_gb": round(required_full_gb, 2),
        "required_derived_gb": round(required_derived_gb, 2),
        "raw_facts_note": (
            "raw_facts is the dominant table. It cannot be deleted in-place without a planned "
            "schema/data-mode change because canonical_facts currently references raw_facts."
        ),
    }


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total


def _gb(bytes_value: int) -> float:
    return round(bytes_value / 1024 / 1024 / 1024, 3)


if __name__ == "__main__":
    raise SystemExit(main())
