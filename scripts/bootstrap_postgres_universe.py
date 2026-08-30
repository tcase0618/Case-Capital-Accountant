from __future__ import annotations

from collections.abc import Iterable

from accountant.db import Base, create_db_engine, create_session_factory
from accountant.ingest.companies import import_companies_from_tickers
from accountant.sec import SecClient
from accountant.taxonomy.seed import ensure_canonical_taxonomy_seeded
from accountant.universe.sources import load_universe_tickers


def _merge_universe_groups(groups: Iterable[list[str]]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for ticker in group:
            if ticker in seen:
                continue
            seen.add(ticker)
            merged.append(ticker)
    return merged


def main() -> None:
    engine = create_db_engine()
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    session = factory()
    try:
        ensure_canonical_taxonomy_seeded(session)
        session.commit()

        universe = load_universe_tickers(["sp500", "russell2000", "nasdaq"])
        tickers = _merge_universe_groups(universe.values())
        print(
            "loaded universe "
            f"sp500={len(universe.get('sp500', []))} "
            f"russell2000={len(universe.get('russell2000', []))} "
            f"nasdaq={len(universe.get('nasdaq', []))} "
            f"unique={len(tickers)}",
            flush=True,
        )

        with SecClient() as sec_client:
            result = import_companies_from_tickers(session, tickers, sec_client)
            session.commit()

        print(
            "bootstrap completed "
            f"requested={result.requested} "
            f"imported={result.imported} "
            f"existing={result.existing} "
            f"unresolved={len(result.unresolved)} "
            f"invalid={len(result.invalid)}",
            flush=True,
        )
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
