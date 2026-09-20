from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from accountant.db import create_db_engine, create_session_factory  # noqa: E402
from accountant.research.bottleneck_engine import (  # noqa: E402
    bottleneck_summary_from_cache,
    refresh_bottleneck_cache,
)


def main() -> int:
    args = _parse_args()
    engine = create_db_engine()
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        result = refresh_bottleneck_cache(session, limit=args.limit)
        session.commit()
        summary = bottleneck_summary_from_cache(session)
    payload = {"refresh": result, "summary": summary}
    print(json.dumps(payload, indent=2), flush=True)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh cached per-company bottleneck snapshots.")
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
