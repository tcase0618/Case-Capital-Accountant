"""Check migrated research tables without silently creating any schema.

Run against an isolated migrated CI database only. Full legacy-schema drift
remains separately visible in `alembic check`; this is not a substitute for it.
"""

import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from accountant.config import get_settings
from accountant.db import Base
from accountant.db.models import BuyBoardCandidate, BuyBoardSnapshot, CompanyReport, ReportCard

MODELS = (CompanyReport, ReportCard, BuyBoardCandidate, BuyBoardSnapshot)
NAMES = {model.__tablename__ for model in MODELS}


def main():
    engine = sa.create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                "include_object": lambda _object, name, kind, _reflected, _comparison: (
                    kind != "table" or name in NAMES
                ),
            },
        )
        drift = compare_metadata(context, Base.metadata)
        if drift:
            raise RuntimeError(f"Research schema drift: {drift}")
        for model in MODELS:
            connection.execute(sa.select(model).limit(1))
    engine.dispose()
    print("4 migrated research tables queried; no scoped schema drift")


if __name__ == "__main__":
    main()
