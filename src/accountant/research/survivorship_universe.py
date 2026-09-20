from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from accountant.db.models import Filing


@dataclass(frozen=True)
class FilerUniverseSnapshot:
    as_of_date: date
    lookback_days: int
    company_ids: list[str]


def build_filer_universe_as_of(
    session: Session,
    *,
    as_of_date: date,
    lookback_days: int = 400,
) -> FilerUniverseSnapshot:
    window_start = as_of_date - timedelta(days=lookback_days)
    rows = session.execute(
        select(distinct(Filing.company_id))
        .where(
            Filing.form_type.in_(("10-K", "10-Q", "10-K/A", "10-Q/A")),
            Filing.filing_date >= window_start,
            Filing.filing_date <= as_of_date,
        )
        .order_by(Filing.company_id.asc())
    ).scalars().all()
    return FilerUniverseSnapshot(
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        company_ids=[str(value) for value in rows],
    )
