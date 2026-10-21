"""ACC-LOW-003: readiness follows EDGAR days, not market or calendar days."""

import importlib.util
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest


def readiness():
    spec = importlib.util.spec_from_file_location(
        "oct21_readiness", Path(__file__).parents[1] / "scripts/vps_readiness_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "latest,calendar_days,expected",
    [
        ("2026-10-09", 4, True),  # Monday was Columbus Day, not an EDGAR day.
        ("2026-10-05", 8, False),
        ("2026-10-14", -1, False),  # Future source dates must fail closed.
        (None, None, False),
        ("invalid", 0, False),
    ],
)
def test_readiness_sec_freshness_on_first_post_holiday_morning(
    monkeypatch, capsys, latest, calendar_days, expected
):
    import json

    module = readiness()

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 13, 12, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(module, "backup_status", lambda _: {"ok": True})
    monkeypatch.setattr(module, "scheduler_status", lambda _: {"ok": True})
    payloads = {
        "/health": {"status": "ok"},
        "/api/reports/status": {"running": True, "reports_cached": 1},
        "/api/source-integrity": {
            "source_grade": "WATCH",
            "sec": {"latest_filing_date": latest, "days_since_latest_filing": calendar_days},
            "coverage": {"report_coverage_pct": 100, "bottleneck_coverage_pct": 100},
        },
        "/api/paper-books": {},
    }
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payloads[request.url.path])
        )
    )
    monkeypatch.setattr(module.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(sys, "argv", ["readiness"])
    assert module.main() == (0 if expected else 1)
    result = json.loads(capsys.readouterr().out)
    check = next(check for check in result["checks"] if check["name"] == "sec_fresh_enough")
    assert check["ok"] is expected


def test_calendar_matches_the_sec_published_2026_closures():
    from accountant.ops.edgar_calendar import edgar_holidays

    assert edgar_holidays(2026) == {
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 5, 25),
        date(2026, 6, 19),
        date(2026, 7, 3),
        date(2026, 9, 7),
        date(2026, 10, 12),
        date(2026, 11, 11),
        date(2026, 11, 26),
        date(2026, 12, 25),
    }


@pytest.mark.parametrize(
    "latest,as_of,expected",
    [
        (date(2026, 10, 9), date(2026, 10, 12), 0),
        (date(2026, 10, 9), date(2026, 10, 13), 1),
        (date(2026, 7, 2), date(2026, 7, 6), 1),
        (date(2021, 12, 30), date(2022, 1, 3), 1),
        (date(2022, 12, 30), date(2023, 1, 3), 1),
        (date(2026, 4, 2), date(2026, 4, 3), 1),  # Good Friday is an EDGAR day.
        (date(2026, 10, 13), date(2026, 10, 13), 0),
    ],
)
def test_edgar_days_exclude_observed_federal_holidays_not_market_holidays(latest, as_of, expected):
    from accountant.ops.edgar_calendar import edgar_business_days_since

    assert edgar_business_days_since(latest, as_of=as_of) == expected


def test_readiness_uses_eastern_date_not_utc_date(monkeypatch):
    module = readiness()

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 14, 1, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(module, "datetime", Clock)
    result = module.sec_freshness({"latest_filing_date": "2026-10-13"}, max_business_days=0)
    assert result["as_of_date"] == "2026-10-13"
    assert result["ok"]
