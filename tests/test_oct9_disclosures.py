from datetime import date

import pytest

from accountant.db.models import Filing
from accountant.research.grading_evidence import build_disclosure_evidence


def filing(form, day, url):
    return Filing(form_type=form, filing_date=day, source_url=url, accession_number=url)


def test_newest_current_report_does_not_hide_latest_annual_concern():
    annual = filing("10-K", date(2026, 2, 1), "annual")
    current = filing("8-K", date(2026, 10, 9), "current")
    texts = {
        "annual": "There is substantial doubt about our ability to continue as a going concern.",
        "current": "The company announced a new director.",
    }
    evidence = build_disclosure_evidence(
        [current, annual],
        current,
        sec_user_agent="Test test@example.com",
        fetch_text=lambda url, _: texts[url],
    )
    assert evidence.going_concern is True
    assert {source["accession_number"] for source in evidence.sources} == {"annual", "current"}


@pytest.mark.parametrize(
    "text",
    [
        "If an error is found, our financial statements should no longer be relied upon.",
        "Unless corrected, the financial statements should no longer be relied upon.",
        "We have not concluded that our financial statements should no longer be relied upon.",
        "There is no determination that the financial results should no longer be relied on.",
        "It is possible that our financial statements should no longer be relied upon.",
    ],
)
def test_conditional_or_negated_non_reliance_is_not_a_confirmed_veto(text):
    current = filing("8-K", date(2026, 10, 9), "current")
    evidence = build_disclosure_evidence(
        [current],
        current,
        sec_user_agent="Test test@example.com",
        fetch_text=lambda *_: text,
    )
    assert evidence.big_r_restatement is None
    assert evidence.event_severity is None


def test_affirmative_disclosure_still_wins_over_hypothetical_sentence():
    current = filing("8-K", date(2026, 10, 9), "current")
    evidence = build_disclosure_evidence(
        [current],
        current,
        sec_user_agent="Test test@example.com",
        fetch_text=lambda *_: (
            "If errors occur, financial statements should no longer be relied upon. "
            "Our board concluded that the financial statements should no longer be relied upon."
        ),
    )
    assert evidence.big_r_restatement is True
    assert evidence.event_severity == 95
