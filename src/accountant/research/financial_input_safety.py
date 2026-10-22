"""Conservative, versioned selection of consolidated USD financial inputs."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from math import isfinite

from accountant.db.models import RawFact

RULE_VERSION = "FINANCIAL_INPUT_SAFETY_V1"


def duration(fact: RawFact) -> int | None:
    if fact.period_start is not None and fact.period_end is not None:
        return (fact.period_end - fact.period_start).days
    if fact.period_end is not None or fact.instant_date is not None:
        return 0
    return None


def expected_unit(concept: str) -> str:
    if "EarningsPerShare" in concept:
        return "USD/shares"
    if "SharesOutstanding" in concept or "ShareOutstanding" in concept:
        return "shares"
    return "USD"


def safe_fact(fact: RawFact) -> bool:
    value = fact.value_numeric
    return (
        value is not None and isfinite(float(value))
        and not fact.dimensions
        and fact.taxonomy in {"us-gaap", "dei"}
        and fact.unit == expected_unit(fact.concept)
        and duration(fact) is not None
    )


def _timestamp(value: datetime | date | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    if not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time(), tzinfo=UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def select_facts(facts: Sequence[RawFact], concepts: list[str], period: str) -> list[RawFact]:
    buckets: dict[date, list[RawFact]] = {}
    for fact in facts:
        if fact.concept not in concepts or not safe_fact(fact):
            continue
        days = duration(fact)
        if period == "instant" and days != 0:
            continue
        if period == "quarterly" and not (days is not None and 70 <= days <= 110):
            continue
        if period == "annual" and not (days is not None and 350 <= days <= 380):
            continue
        end = fact.period_end or fact.instant_date
        if end is not None:
            buckets.setdefault(end, []).append(fact)
    selected = []
    for end in sorted(buckets, reverse=True):
        candidates = buckets[end]
        # Alias priority is explicit, never determined by input row order.
        concept = min((f.concept for f in candidates), key=concepts.index)
        candidates = [f for f in candidates if f.concept == concept]
        if len({f.period_start for f in candidates}) != 1:
            continue
        def rank(f):
            return (_timestamp(f.accepted_at), _timestamp(f.filed_date))
        latest = max(rank(f) for f in candidates)
        candidates = [f for f in candidates if rank(f) == latest]
        if len({f.value_numeric for f in candidates}) != 1:
            continue
        selected.append(min(candidates, key=lambda f: str(f.fact_hash or f.id)))
    return selected


def comparable(current: RawFact, prior: RawFact) -> bool:
    end = current.period_end or current.instant_date
    previous = prior.period_end or prior.instant_date
    if end is None or previous is None or not 350 <= (end - previous).days <= 380:
        return False
    if current.concept != prior.concept or current.unit != prior.unit:
        return False
    if current.period_start is None or prior.period_start is None:
        return current.period_start is None and prior.period_start is None
    return (
        350 <= (current.period_start - prior.period_start).days <= 380
        and abs((duration(current) or 0) - (duration(prior) or 0)) <= 14
        and previous < current.period_start
    )


def provenance(fact: RawFact) -> dict[str, object]:
    end = fact.period_end or fact.instant_date
    return {
        "rule_version": RULE_VERSION,
        "fact_id": str(fact.id), "fact_hash": fact.fact_hash,
        "filing_id": str(fact.filing_id), "accession_number": fact.accession_number,
        "concept": fact.concept, "unit": fact.unit,
        "period_start": fact.period_start.isoformat() if fact.period_start else None,
        "period_end": end.isoformat() if end is not None else None,
        "value": str(fact.value_numeric),
        "accepted_at": fact.accepted_at.isoformat() if fact.accepted_at else None,
        "filed_date": fact.filed_date.isoformat() if fact.filed_date else None,
    }


class FinancialSeries(list):
    def __init__(self, facts: list[RawFact]):
        super().__init__((f.period_end or f.instant_date, float(f.value_numeric))
                         for f in facts if f.value_numeric is not None)
        self.source_facts = facts


def annual_report_inputs(facts: Sequence[RawFact]) -> tuple[list[RawFact], list[RawFact]]:
    revenue = select_facts(facts, [
        "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
    ], "annual")
    windows = {(f.period_start, f.period_end) for f in revenue}
    ends = {f.period_end for f in revenue}
    return revenue, [f for f in facts if (
        (f.period_start, f.period_end) in windows
        or (duration(f) == 0 and (f.period_end or f.instant_date) in ends)
    )]
