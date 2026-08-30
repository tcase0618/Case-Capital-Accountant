from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from accountant.research.filing_signal_engine import (
    build_event_red_flags,
    build_governance_signals,
    build_non_gaap_signals,
    build_textual_signals,
    cosine_similarity,
    extract_audit_fee_ratio,
    extract_non_gaap_eps,
    extract_risk_factors_section,
    strip_html_to_text,
    tone_score_for_text,
)


def test_strip_html_and_extract_risk_factors() -> None:
    raw_html = """
    <html><body>
    <h1>Item 1A. Risk Factors</h1>
    <p>We face volatility and material weakness risk.</p>
    <h1>Item 1B.</h1>
    </body></html>
    """
    text = strip_html_to_text(raw_html)
    risk = extract_risk_factors_section(text)

    assert "risk factors" in text
    assert "volatility and material weakness risk" in risk


def test_similarity_and_tone_scores_are_deterministic() -> None:
    left = "strong growth momentum with disciplined capital allocation"
    right = "strong growth momentum and disciplined allocation"
    similarity = cosine_similarity(left, right)
    tone = tone_score_for_text(left)

    assert similarity is not None
    assert similarity > 0.5
    assert tone is not None
    assert tone > 0


def test_build_textual_signals_extracts_similarity_and_disclosures() -> None:
    latest = SimpleNamespace(source_url="latest", form_type="10-K")
    prior = SimpleNamespace(source_url="prior", form_type="10-K")
    payloads = {
        "latest": """
            Item 1A. Risk Factors. We face volatility but see strong growth momentum.
            Our supplier finance program remains active.
            The expected return on plan assets was 6.5%.
            The discount rate was 4.2%.
            Related parties represented 12% of revenue.
            Item 1B.
        """,
        "prior": """
            Item 1A. Risk Factors. We face volatility but see steady growth momentum.
            Item 1B.
        """,
    }

    signals = build_textual_signals(
        latest,
        prior,
        sec_user_agent="Case Capital Accountant test@example.com",
        fetch_text=lambda url, _ua: payloads[url],
    )

    assert signals.yoy_filing_similarity_score is not None
    assert signals.risk_factor_similarity_score is not None
    assert signals.reverse_factoring_disclosed is True
    assert signals.pension_discount_rate == 4.2
    assert signals.pension_expected_return == 6.5
    assert signals.related_party_revenue_pct == 12.0
    assert signals.summary is not None


def test_build_event_red_flags_detects_comment_letters_and_turnover() -> None:
    filings = [
        SimpleNamespace(
            form_type="CORRESP",
            filing_date=date(2026, 7, 1),
            primary_document=None,
            primary_doc_description="SEC correspondence",
            source_url=None,
        ),
        SimpleNamespace(
            form_type="8-K",
            filing_date=date(2026, 6, 15),
            primary_document="form8k.htm",
            primary_doc_description="Chief Financial Officer resignation and auditor dismissal",
            source_url="eightk",
        ),
    ]
    payloads = {
        "eightk": """
            The company dismissed Deloitte as its independent registered public accounting firm.
            The chief financial officer resigned.
        """
    }

    signals = build_event_red_flags(
        filings,
        sec_user_agent="Case Capital Accountant test@example.com",
        fetch_text=lambda url, _ua: payloads.get(url, ""),
    )

    assert signals.sec_comment_letter_flag is True
    assert signals.auditor_changed_flag is True
    assert signals.auditor_change_date == "2026-06-15"
    assert signals.cfo_turnover_flag is True
    assert signals.cfo_turnover_date == "2026-06-15"


def test_extract_non_gaap_eps_and_audit_fee_ratio() -> None:
    text = """
        Non-GAAP diluted EPS was $2.15 for the quarter.
        Audit Fees $1,000,000
        Tax Fees $250,000
    """

    assert extract_non_gaap_eps(text) == 2.15
    assert extract_audit_fee_ratio(text) == 0.25


def test_build_governance_signals_detects_form4_cluster_and_dual_class() -> None:
    filings = [
        SimpleNamespace(form_type="10-K", filing_date=date(2026, 3, 1), source_url="tenk"),
        SimpleNamespace(form_type="4", filing_date=date(2026, 8, 1), source_url=None),
        SimpleNamespace(form_type="4", filing_date=date(2026, 7, 20), source_url=None),
    ]
    payloads = {
        "tenk": """
            Audit Fees $1,200,000
            All Other Fees $120,000
        """
    }

    signals = build_governance_signals(
        filings,
        sec_user_agent="Case Capital Accountant test@example.com",
        fetch_text=lambda url, _ua: payloads.get(url, ""),
        security_count=2,
    )

    assert signals.insider_buy_cluster_flag is True
    assert signals.insider_net_shares_bought_90d == 2.0
    assert signals.dual_class_flag is True
    assert signals.audit_fee_ratio == 0.1


def test_build_non_gaap_signals_calculates_gap_and_trend() -> None:
    latest = SimpleNamespace(source_url="latest", form_type="10-Q")
    priors = [
        SimpleNamespace(source_url="prior1", form_type="10-Q"),
        SimpleNamespace(source_url="prior2", form_type="10-Q"),
        SimpleNamespace(source_url="prior3", form_type="10-Q"),
    ]
    payloads = {
        "latest": "Adjusted diluted EPS was $2.20.",
        "prior1": "Adjusted diluted EPS was $1.90.",
        "prior2": "Adjusted diluted EPS was $1.80.",
        "prior3": "Adjusted diluted EPS was $1.70.",
    }

    signals = build_non_gaap_signals(
        latest,
        priors,
        sec_user_agent="Case Capital Accountant test@example.com",
        gaap_eps=2.0,
        fetch_text=lambda url, _ua: payloads.get(url, ""),
    )

    assert signals.gaap_eps == 2.0
    assert signals.non_gaap_eps == 2.2
    assert signals.non_gaap_gap_pct == 10.0
    assert signals.non_gaap_gap_3yr_trend == 22.22
    assert signals.recurring_nonrecurring_flag is True
