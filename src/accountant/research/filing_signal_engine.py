from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from html import unescape

import httpx

from accountant.db.models import Filing

_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_NON_TOKEN_RE = re.compile(r"[^a-z0-9]+")

_POSITIVE_TONE_WORDS = {
    "accelerate",
    "advancing",
    "benefit",
    "confidence",
    "disciplined",
    "durable",
    "efficient",
    "growth",
    "improve",
    "improving",
    "momentum",
    "opportunity",
    "outperform",
    "progress",
    "resilient",
    "strength",
    "strong",
}
_NEGATIVE_TONE_WORDS = {
    "adverse",
    "challenging",
    "decline",
    "decrease",
    "delay",
    "headwind",
    "impairment",
    "loss",
    "material weakness",
    "pressure",
    "risk",
    "shortfall",
    "uncertain",
    "volatility",
    "weakness",
}
_AUDITOR_KEYWORDS = ("auditor", "independent registered public accounting firm", "dismissed", "engaged")
_CFO_KEYWORDS = ("chief financial officer", "cfo", "principal financial officer")
_CEO_KEYWORDS = ("chief executive officer", "ceo", "principal executive officer")
_SUPPLIER_FINANCE_KEYWORDS = ("supplier finance", "supply chain finance", "reverse factoring")


@dataclass(frozen=True)
class TextualSignalBundle:
    yoy_filing_similarity_score: float | None
    risk_factor_similarity_score: float | None
    mgmt_tone_score: float | None
    reverse_factoring_disclosed: bool
    pension_discount_rate: float | None
    pension_expected_return: float | None
    related_party_revenue_pct: float | None
    summary: str | None


@dataclass(frozen=True)
class EventSignalBundle:
    auditor_name: str | None
    auditor_tenure_years: float | None
    auditor_changed_flag: bool
    auditor_change_date: str | None
    sec_comment_letter_flag: bool
    cfo_turnover_flag: bool
    cfo_turnover_date: str | None
    ceo_turnover_flag: bool
    ceo_turnover_date: str | None


@dataclass(frozen=True)
class GovernanceSignalBundle:
    insider_buy_cluster_flag: bool
    insider_net_shares_bought_90d: float | None
    institutional_ownership_pct: float | None
    institutional_ownership_qoq_delta: float | None
    short_interest_pct_float: float | None
    short_interest_delta: float | None
    dual_class_flag: bool
    audit_fee_ratio: float | None


@dataclass(frozen=True)
class NonGaapSignalBundle:
    gaap_eps: float | None
    non_gaap_eps: float | None
    non_gaap_gap_pct: float | None
    non_gaap_gap_3yr_trend: float | None
    recurring_nonrecurring_flag: bool


def build_textual_signals(
    latest_filing: Filing | None,
    prior_same_form_filing: Filing | None,
    *,
    sec_user_agent: str,
    fetch_text: Callable[[str, str], str] | None = None,
) -> TextualSignalBundle:
    if latest_filing is None or not latest_filing.source_url:
        return TextualSignalBundle(None, None, None, False, None, None, None, None)

    fetch = fetch_text or fetch_filing_text
    latest_text = fetch(latest_filing.source_url, sec_user_agent)
    if not latest_text:
        return TextualSignalBundle(None, None, None, False, None, None, None, None)

    prior_text = ""
    if prior_same_form_filing is not None and prior_same_form_filing.source_url:
        prior_text = fetch(prior_same_form_filing.source_url, sec_user_agent)

    latest_risk = extract_risk_factors_section(latest_text)
    prior_risk = extract_risk_factors_section(prior_text) if prior_text else ""

    summary_parts: list[str] = []
    yoy_similarity = cosine_similarity(latest_text, prior_text) if prior_text else None
    if yoy_similarity is not None:
        summary_parts.append(f"filing similarity {yoy_similarity:.2f}")
    risk_similarity = cosine_similarity(latest_risk, prior_risk) if latest_risk and prior_risk else None
    if risk_similarity is not None:
        summary_parts.append(f"risk similarity {risk_similarity:.2f}")

    tone_score = tone_score_for_text(latest_text)
    reverse_factoring = any(keyword in latest_text for keyword in _SUPPLIER_FINANCE_KEYWORDS)
    if reverse_factoring:
        summary_parts.append("supplier finance disclosure detected")

    discount_rate = extract_first_percentage(
        latest_text,
        [
            r"discount rate[^.%]{0,80}?(\d{1,2}(?:\.\d+)?)\s*%",
            r"assumed discount rate[^.%]{0,80}?(\d{1,2}(?:\.\d+)?)\s*%",
        ],
    )
    expected_return = extract_first_percentage(
        latest_text,
        [
            r"expected return on plan assets[^.%]{0,80}?(\d{1,2}(?:\.\d+)?)\s*%",
            r"long-term rate of return[^.%]{0,80}?(\d{1,2}(?:\.\d+)?)\s*%",
        ],
    )
    related_party_revenue_pct = extract_first_percentage(
        latest_text,
        [
            r"related part(?:y|ies)[^.%]{0,120}?(\d{1,3}(?:\.\d+)?)\s*%\s+of\s+(?:net\s+)?revenue",
            r"(\d{1,3}(?:\.\d+)?)\s*%\s+of\s+(?:net\s+)?revenue[^.]{0,80}?related part(?:y|ies)",
        ],
    )
    summary = "; ".join(summary_parts) if summary_parts else None

    return TextualSignalBundle(
        yoy_filing_similarity_score=round(yoy_similarity, 4) if yoy_similarity is not None else None,
        risk_factor_similarity_score=round(risk_similarity, 4) if risk_similarity is not None else None,
        mgmt_tone_score=round(tone_score, 4) if tone_score is not None else None,
        reverse_factoring_disclosed=reverse_factoring,
        pension_discount_rate=discount_rate,
        pension_expected_return=expected_return,
        related_party_revenue_pct=related_party_revenue_pct,
        summary=summary,
    )


def build_event_red_flags(
    filings: list[Filing],
    *,
    sec_user_agent: str,
    fetch_text: Callable[[str, str], str] | None = None,
) -> EventSignalBundle:
    fetch = fetch_text or fetch_filing_text
    today_cutoff = date.today() - timedelta(days=365)
    recent_filings = [filing for filing in filings if filing.filing_date and filing.filing_date >= today_cutoff]

    sec_comment_letter_flag = any(
        (filing.form_type or "").upper() in {"UPLOAD", "CORRESP"} for filing in recent_filings
    )

    eight_ks = [filing for filing in recent_filings if "8-K" in (filing.form_type or "").upper()]
    auditor_change_date: str | None = None
    cfo_turnover_date: str | None = None
    ceo_turnover_date: str | None = None
    auditor_changed_flag = False
    cfo_turnover_flag = False
    ceo_turnover_flag = False
    auditor_name: str | None = None

    for filing in eight_ks:
        text = _filing_metadata_text(filing)
        if filing.source_url:
            fetched = fetch(filing.source_url, sec_user_agent)
            if fetched:
                text = f"{text} {fetched}"
        if not auditor_changed_flag and contains_any(text, _AUDITOR_KEYWORDS):
            auditor_changed_flag = True
            auditor_change_date = filing.filing_date.isoformat() if filing.filing_date else None
            auditor_name = extract_auditor_name(text)
        if not cfo_turnover_flag and contains_any(text, _CFO_KEYWORDS):
            cfo_turnover_flag = True
            cfo_turnover_date = filing.filing_date.isoformat() if filing.filing_date else None
        if not ceo_turnover_flag and contains_any(text, _CEO_KEYWORDS):
            ceo_turnover_flag = True
            ceo_turnover_date = filing.filing_date.isoformat() if filing.filing_date else None

    auditor_tenure_years = None
    if auditor_changed_flag and auditor_change_date:
        try:
            auditor_tenure_years = round((date.today() - date.fromisoformat(auditor_change_date)).days / 365.0, 2)
        except ValueError:
            auditor_tenure_years = None

    return EventSignalBundle(
        auditor_name=auditor_name,
        auditor_tenure_years=auditor_tenure_years,
        auditor_changed_flag=auditor_changed_flag,
        auditor_change_date=auditor_change_date,
        sec_comment_letter_flag=sec_comment_letter_flag,
        cfo_turnover_flag=cfo_turnover_flag,
        cfo_turnover_date=cfo_turnover_date,
        ceo_turnover_flag=ceo_turnover_flag,
        ceo_turnover_date=ceo_turnover_date,
    )


def build_governance_signals(
    filings: list[Filing],
    *,
    sec_user_agent: str,
    fetch_text: Callable[[str, str], str] | None = None,
    security_count: int = 1,
) -> GovernanceSignalBundle:
    fetch = fetch_text or fetch_filing_text
    recent_cutoff = date.today() - timedelta(days=90)
    form4s = [filing for filing in filings if (filing.form_type or "").upper() == "4" and filing.filing_date and filing.filing_date >= recent_cutoff]
    insider_buy_cluster_flag = len(form4s) >= 2
    insider_net_shares_bought_90d = float(len(form4s)) if form4s else None

    latest_filing = filings[0] if filings else None
    latest_text = ""
    if latest_filing and latest_filing.source_url:
        latest_text = fetch(latest_filing.source_url, sec_user_agent)
    audit_fees = extract_audit_fee_ratio(latest_text)

    return GovernanceSignalBundle(
        insider_buy_cluster_flag=insider_buy_cluster_flag,
        insider_net_shares_bought_90d=insider_net_shares_bought_90d,
        institutional_ownership_pct=None,
        institutional_ownership_qoq_delta=None,
        short_interest_pct_float=None,
        short_interest_delta=None,
        dual_class_flag=security_count > 1,
        audit_fee_ratio=audit_fees,
    )


def build_non_gaap_signals(
    latest_filing: Filing | None,
    prior_filings_same_form: list[Filing],
    *,
    sec_user_agent: str,
    gaap_eps: float | None,
    fetch_text: Callable[[str, str], str] | None = None,
) -> NonGaapSignalBundle:
    if latest_filing is None or not latest_filing.source_url:
        return NonGaapSignalBundle(gaap_eps, None, None, None, False)

    fetch = fetch_text or fetch_filing_text
    latest_text = fetch(latest_filing.source_url, sec_user_agent)
    latest_non_gaap = extract_non_gaap_eps(latest_text)
    non_gaap_gap_pct = None
    if latest_non_gaap is not None and gaap_eps not in (None, 0):
        non_gaap_gap_pct = round(((latest_non_gaap - gaap_eps) / abs(gaap_eps)) * 100, 2)

    historical_non_gaap: list[float] = []
    for filing in prior_filings_same_form[:3]:
        if not filing.source_url:
            continue
        value = extract_non_gaap_eps(fetch(filing.source_url, sec_user_agent))
        if value is not None:
            historical_non_gaap.append(value)
    non_gaap_gap_3yr_trend = None
    if latest_non_gaap is not None and historical_non_gaap:
        baseline = sum(historical_non_gaap) / len(historical_non_gaap)
        if baseline != 0:
            non_gaap_gap_3yr_trend = round(((latest_non_gaap - baseline) / abs(baseline)) * 100, 2)
    recurring_nonrecurring_flag = len(historical_non_gaap) >= 2 and latest_non_gaap is not None

    return NonGaapSignalBundle(
        gaap_eps=gaap_eps,
        non_gaap_eps=latest_non_gaap,
        non_gaap_gap_pct=non_gaap_gap_pct,
        non_gaap_gap_3yr_trend=non_gaap_gap_3yr_trend,
        recurring_nonrecurring_flag=recurring_nonrecurring_flag,
    )


@lru_cache(maxsize=512)
def fetch_filing_text(url: str, sec_user_agent: str) -> str:
    if not url:
        return ""
    try:
        with httpx.Client(
            timeout=httpx.Timeout(10.0),
            headers={"User-Agent": sec_user_agent, "Accept-Encoding": "gzip, deflate"},
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return strip_html_to_text(response.text)
    except Exception:
        return ""


def strip_html_to_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    cleaned = _SCRIPT_STYLE_RE.sub(" ", raw_html)
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = cleaned.replace("\x00", " ")
    return _WHITESPACE_RE.sub(" ", cleaned).strip().lower()


def extract_risk_factors_section(text: str) -> str:
    if not text:
        return ""
    match = re.search(
        r"item\s+1a[^a-z0-9]{0,20}risk factors(?P<section>.*?)(?:item\s+1b|item\s+2|item\s+7)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return _WHITESPACE_RE.sub(" ", match.group("section")).strip()


def cosine_similarity(left: str, right: str) -> float | None:
    left_tokens = tokenize(left)
    right_tokens = tokenize(right)
    if not left_tokens or not right_tokens:
        return None
    left_counts = Counter(left_tokens)
    right_counts = Counter(right_tokens)
    intersection = set(left_counts) & set(right_counts)
    numerator = sum(left_counts[token] * right_counts[token] for token in intersection)
    left_norm = math.sqrt(sum(value * value for value in left_counts.values()))
    right_norm = math.sqrt(sum(value * value for value in right_counts.values()))
    if left_norm == 0 or right_norm == 0:
        return None
    return max(0.0, min(1.0, numerator / (left_norm * right_norm)))


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    normalized = _NON_TOKEN_RE.sub(" ", text.lower())
    return [token for token in normalized.split() if len(token) >= 3]


def tone_score_for_text(text: str) -> float | None:
    tokens = tokenize(text)
    if not tokens:
        return None
    token_text = " ".join(tokens)
    positive = sum(token in _POSITIVE_TONE_WORDS for token in tokens)
    negative = sum(token in _NEGATIVE_TONE_WORDS for token in tokens)
    negative += sum(phrase in token_text for phrase in ("material weakness",))
    total = positive + negative
    if total == 0:
        return 0.0
    return max(-1.0, min(1.0, (positive - negative) / total))


def extract_first_percentage(text: str, patterns: list[str]) -> float | None:
    if not text:
        return None
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return round(float(match.group(1)), 2)
            except (TypeError, ValueError):
                continue
    return None


def contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def extract_auditor_name(text: str) -> str | None:
    match = re.search(
        r"(?:engaged|appointed|dismissed|resigned)[^.]{0,120}?(deloitte|pwc|pricewaterhousecoopers|ey|ernst\s*&\s*young|kpmg|bdo|grant thornton)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).strip()


def extract_non_gaap_eps(text: str) -> float | None:
    if not text:
        return None
    patterns = [
        r"non-gaap diluted eps[^0-9\-]{0,20}\$?\(?(-?\d+(?:\.\d+)?)\)?",
        r"adjusted diluted eps[^0-9\-]{0,20}\$?\(?(-?\d+(?:\.\d+)?)\)?",
        r"non-gaap net income per diluted share[^0-9\-]{0,20}\$?\(?(-?\d+(?:\.\d+)?)\)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return round(float(match.group(1)), 2)
            except (TypeError, ValueError):
                continue
    return None


def extract_audit_fee_ratio(text: str) -> float | None:
    if not text:
        return None
    audit_match = re.search(r"audit fees[^0-9]{0,40}\$?\(?([0-9][0-9,]*(?:\.\d+)?)\)?", text, re.IGNORECASE)
    non_audit_match = re.search(
        r"(?:audit-related fees|tax fees|all other fees)[^0-9]{0,40}\$?\(?([0-9][0-9,]*(?:\.\d+)?)\)?",
        text,
        re.IGNORECASE,
    )
    if not audit_match or not non_audit_match:
        return None
    try:
        audit_fees = float(audit_match.group(1).replace(",", ""))
        non_audit_fees = float(non_audit_match.group(1).replace(",", ""))
    except ValueError:
        return None
    if audit_fees <= 0:
        return None
    return round(non_audit_fees / audit_fees, 4)


def _filing_metadata_text(filing: Filing) -> str:
    parts = [
        filing.form_type or "",
        filing.primary_document or "",
        filing.primary_doc_description or "",
    ]
    return " ".join(parts).lower()
