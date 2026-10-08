"""Conservative, versioned disclosure evidence; metadata alone is not a veto."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import TypedDict

from accountant.db.models import Filing, RawFact
from accountant.research.factor_engine import _annual_periods, _beneish_m_score, _period_label
from accountant.research.filing_signal_engine import fetch_filing_text, strip_html_to_text

RULE_VERSION = "DISCLOSURE_GRADING_V2"
_NON_RELIANCE = re.compile(
    r"(?:financial statements|financial results)[^.]{0,160}"
    r"(?:should|must|can) no longer be relied (?:upon|on)"
)
_GOING_CONCERN = re.compile(
    r"(?:raises?|raised|there is|exists?) substantial doubt[^.]{0,160}"
    r"(?:ability to continue as a going concern)"
)


@dataclass(frozen=True)
class DisclosureEvidence:
    rule_version: str
    going_concern: bool | None
    big_r_restatement: bool | None
    amendment_kind: str
    event_severity: float | None
    sources: list[dict]

    def provenance(self) -> dict:
        return asdict(self)


def build_disclosure_evidence(
    filings: list[Filing], latest: Filing | None, *, sec_user_agent: str, fetch_text=None
) -> DisclosureEvidence:
    fetch = fetch_text or fetch_filing_text
    cutoff = (latest.filing_date if latest and latest.filing_date else date.today()) - timedelta(
        days=365
    )
    candidates = [
        filing
        for filing in filings
        if filing is latest
        or (
            (filing.form_type or "").upper() in {"8-K", "8-K/A"}
            and filing.filing_date
            and filing.filing_date >= cutoff
        )
    ]
    incomplete = not candidates
    concern = restatement = False
    amendment_kind = "unknown" if latest and latest.is_amendment else "not_amended"
    sources = []
    for filing in candidates:
        text = (
            strip_html_to_text(fetch(filing.source_url, sec_user_agent))
            if filing.source_url
            else ""
        )
        if not text:
            incomplete = True
            sources.append({"accession_number": filing.accession_number, "text_available": False})
            continue
        # Analyze affirmative sentences; negated disclosures and TOC headings
        # such as "Item 4.02 Non-Reliance" alone cannot trigger a hard veto.
        sentences = re.split(r"(?<!\d)\.(?!\d)|[\n;]", text)
        positive_concern = any(
            _GOING_CONCERN.search(sentence)
            and not re.search(r"\b(?:no|not|without)\b[^.]{0,50}substantial doubt", sentence)
            and not re.search(r"\b(?:may|might|could|would)\b[^.]{0,50}substantial doubt", sentence)
            for sentence in sentences
        )
        positive_restatement = bool(_NON_RELIANCE.search(text))
        concern |= positive_concern
        restatement |= positive_restatement
        sources.append(
            {
                "accession_number": filing.accession_number,
                "source_url": filing.source_url,
                "text_available": True,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "going_concern_match": positive_concern,
                "non_reliance_match": positive_restatement,
            }
        )
        if filing is latest and filing.is_amendment:
            if positive_restatement:
                amendment_kind = "financial_non_reliance"
            elif re.search(r"(?:solely|only)[^.]{0,200}part iii", text):
                amendment_kind = "administrative_part_iii"
            else:
                amendment_kind = "unclassified"
    going_concern = True if concern else None if incomplete else False
    big_r = True if restatement else None if incomplete else False
    severity = 95.0 if concern or restatement else None if incomplete else 0.0
    return DisclosureEvidence(RULE_VERSION, going_concern, big_r, amendment_kind, severity, sources)


class BeneishObservation(TypedDict):
    period: str
    score: float | None


def sustained_beneish_evidence(facts: list[RawFact]) -> dict:
    periods = _annual_periods(facts)
    scores: list[BeneishObservation] = []
    for current, prior in zip(periods[:2], periods[1:3], strict=False):
        if current.fiscal_year != prior.fiscal_year + 1:
            break
        score = _beneish_m_score(current, prior)
        scores.append({"period": _period_label(current), "score": score})
    sustained = len(scores) == 2 and all(
        item["score"] is not None and item["score"] > -1.78 for item in scores
    )
    years = {period.fiscal_year for period in periods[:3]}
    return {
        "rule_version": "SUSTAINED_BENEISH_TWO_ANNUAL_V1",
        "threshold": -1.78,
        "required_periods": 2,
        "scores": scores,
        "sustained": sustained,
        "source_fact_ids": [str(fact.id) for fact in facts if fact.fiscal_year in years],
    }
