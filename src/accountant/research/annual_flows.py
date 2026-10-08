"""Versioned, provenance-bearing trailing-year arithmetic on SEC duration facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from accountant.db.models import RawFact

FORMULA_VERSION = "SEC_TTM_FLOWS_V1"


@dataclass(frozen=True)
class AnnualFlow:
    value: float
    start: date
    end: date
    terms: tuple[tuple[RawFact, int], ...]

    def provenance(self) -> dict:
        return {
            "formula_version": FORMULA_VERSION,
            "period_start": self.start.isoformat(), "period_end": self.end.isoformat(),
            "inputs": [{"fact_id": str(fact.id), "fact_hash": fact.fact_hash,
                        "accession_number": fact.accession_number, "coefficient": coefficient,
                        "value": float(fact.value_numeric)} for fact, coefficient in self.terms],
        }


def annual_flow(facts: list[RawFact], concepts: list[str], *, as_of: date | None = None,
                weighted_shares: bool = False) -> AnnualFlow | None:
    """Use a complete FY, four adjacent quarters, or FY + YTD - prior YTD.

    Never annualize a lone quarter. For duration share counts, sum share-days
    over the same recipe and divide by the actual trailing-year day count.
    """
    for concept in concepts:
        candidates = [fact for fact in facts if fact.concept == concept
                      and fact.value_numeric is not None and fact.period_start and fact.period_end
                      and not fact.dimensions and (as_of is None or fact.period_end <= as_of)
                      and fact.unit == ("shares" if weighted_shares else "USD")]
        if not candidates:
            continue
        periods: dict[tuple[date, date], RawFact] = {}
        for fact in candidates:
            key = (fact.period_start, fact.period_end)
            previous = periods.get(key)
            if previous is None or _reported_key(fact) > _reported_key(previous):
                periods[key] = fact
        values = list(periods.values())
        end = max(fact.period_end for fact in values)
        ending = sorted((fact for fact in values if fact.period_end == end),
                        key=lambda fact: fact.period_start)
        for fact in ending:
            if 330 <= _days(fact) <= 400:
                return _result(((fact, 1),), fact.period_start, end, weighted_shares)
        quarters = [fact for fact in values if 60 <= _days(fact) <= 110]
        for latest in [fact for fact in quarters if fact.period_end == end]:
            chain = [latest]
            while len(chain) < 4:
                prior = next((fact for fact in quarters
                              if fact.period_end == chain[-1].period_start - timedelta(days=1)), None)
                if prior is None:
                    break
                chain.append(prior)
            if len(chain) == 4 and 330 <= (end - chain[-1].period_start).days + 1 <= 400:
                return _result(tuple((fact, 1) for fact in reversed(chain)), chain[-1].period_start,
                               end, weighted_shares)
        for current in ending:
            if not 60 <= _days(current) <= 310:
                continue
            annual = next((fact for fact in values if 330 <= _days(fact) <= 400
                           and fact.period_end == current.period_start - timedelta(days=1)), None)
            if annual is None:
                continue
            prior = next((fact for fact in values if fact.period_start == annual.period_start
                          and abs(_days(fact) - _days(current)) <= 7
                          and 330 <= (end - fact.period_end).days <= 400), None)
            if prior is not None:
                return _result(((annual, 1), (current, 1), (prior, -1)),
                               prior.period_end + timedelta(days=1), end, weighted_shares)
        # Latest evidence exists but cannot support a trailing-year value.
        return None
    return None


def _days(fact: RawFact) -> int:
    return (fact.period_end - fact.period_start).days + 1


def _reported_key(fact: RawFact) -> tuple[str, str, str]:
    return (fact.accepted_at.isoformat() if fact.accepted_at else "",
            fact.filed_date.isoformat() if fact.filed_date else "",
            fact.created_at.isoformat() if fact.created_at else "")


def _result(terms, start, end, weighted_shares) -> AnnualFlow:
    if weighted_shares:
        value = sum(float(fact.value_numeric) * _days(fact) * sign for fact, sign in terms)
        value /= (end - start).days + 1
    else:
        value = sum(float(fact.value_numeric) * sign for fact, sign in terms)
    return AnnualFlow(value, start, end, terms)
