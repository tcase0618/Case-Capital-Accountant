from datetime import date
from decimal import Decimal

import pytest

from accountant.db.models import RawFact
from accountant.research.annual_flows import annual_flow
from accountant.research.report_machine import _scenario_valuations


def fact(start, end, value, concept="NetIncomeLoss", unit="USD"):
    return RawFact(concept=concept, period_start=date.fromisoformat(start),
                   period_end=date.fromisoformat(end), value_numeric=Decimal(str(value)),
                   unit=unit, fact_hash=f"{concept}-{start}-{end}", accession_number="example")


def test_four_quarters_are_summed_with_provenance():
    rows = [fact("2025-07-01", "2025-09-30", 10), fact("2025-10-01", "2025-12-31", 20),
            fact("2026-01-01", "2026-03-31", 30), fact("2026-04-01", "2026-06-30", 40)]
    flow = annual_flow(rows, ["NetIncomeLoss"])
    assert flow.value == 100
    assert flow.start == date(2025, 7, 1)
    assert len(flow.provenance()["inputs"]) == 4


def test_fy_plus_ytd_minus_prior_ytd():
    rows = [fact("2025-01-01", "2025-12-31", 100), fact("2025-01-01", "2025-06-30", 40),
            fact("2026-01-01", "2026-06-30", 60)]
    flow = annual_flow(rows, ["NetIncomeLoss"])
    assert flow.value == 120
    assert flow.start == date(2025, 7, 1)
    assert [term["coefficient"] for term in flow.provenance()["inputs"]] == [1, 1, -1]


def test_a_lone_quarter_is_unavailable():
    assert annual_flow([fact("2026-04-01", "2026-06-30", 40)], ["NetIncomeLoss"]) is None


def test_gaps_and_segments_cannot_make_a_trailing_year():
    rows = [fact("2025-07-01", "2025-09-30", 10), fact("2025-10-01", "2025-12-31", 20),
            fact("2026-01-02", "2026-03-31", 30), fact("2026-04-01", "2026-06-30", 40)]
    assert annual_flow(rows, ["NetIncomeLoss"]) is None
    segment = fact("2025-01-01", "2025-12-31", 100)
    segment.dimensions = {"segment": "subsidiary"}
    assert annual_flow([segment], ["NetIncomeLoss"]) is None


def test_weighted_share_days_use_same_annual_window():
    rows = [fact("2025-07-01", "2025-09-30", 10, "Shares", "shares"),
            fact("2025-10-01", "2025-12-31", 20, "Shares", "shares"),
            fact("2026-01-01", "2026-03-31", 30, "Shares", "shares"),
            fact("2026-04-01", "2026-06-30", 40, "Shares", "shares")]
    flow = annual_flow(rows, ["Shares"], weighted_shares=True)
    assert flow.value == pytest.approx((10*92 + 20*92 + 30*90 + 40*91) / 365)


@pytest.mark.parametrize("shares", [None, 0, -1])
def test_missing_shares_never_return_company_totals_as_per_share(shares):
    result = _scenario_valuations(earnings_power=2_000_000_000, quality_score=60,
                                 growth_pct=10, share_count=shares)
    assert result == {"bear": None, "base": None, "bull": None}


def test_ttm_buy_board_never_substitutes_duration_shares():
    from types import SimpleNamespace

    from accountant.research.buy_board import _estimate_share_count

    report = SimpleNamespace(key_stats={"annual_flow_version": "SEC_TTM_FLOWS_V1",
                                        "weighted_avg_diluted_shares": 100})
    assert _estimate_share_count(None, report) is None
    report.key_stats["shares_outstanding"] = 200
    assert _estimate_share_count(None, report) == 200
