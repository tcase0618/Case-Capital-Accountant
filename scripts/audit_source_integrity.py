from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from accountant.db import create_db_engine, create_session_factory  # noqa: E402
from accountant.research.source_integrity import build_source_integrity_snapshot  # noqa: E402


def main() -> int:
    engine = create_db_engine()
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        payload = build_source_integrity_snapshot(session)
    print(json.dumps(payload, indent=2), flush=True)
    return 0 if payload["source_grade"] in {"STRONG", "WATCH"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
