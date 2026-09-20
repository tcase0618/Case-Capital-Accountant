# Accountant Automation Before VPS

This terminal should prove it can run unattended locally before paying for VPS hosting.

## Daily Automation

Run once manually:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-accountant-automation.ps1
```

Install the daily Windows Scheduled Task:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-accountant-automation-task.ps1 -Time "06:15"
```

The task:

- starts portable Postgres if needed
- imports SEC filings since the latest filing already in Postgres
- refreshes report cards for companies with newer core filings
- refreshes company facts, canonical facts, statements, reports, strategy, and buy-board candidates for those stale companies
- writes automation logs and a run summary under `artifacts/automation/`
- writes a company-level bottleneck CSV for AI/compute, energy/resources, and the full universe

## Full Score Backfill After Strategy Changes

When scoring code changes, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-accountant-automation.ps1 -RefreshAllScores
```

Use this after changes like `A-HIS` scoring so existing reports/cards receive the new fields.

## Pre-VPS Gates

Do not move to VPS until these are true for at least several unattended runs:

- latest SEC import completes with no errors
- `remaining_stale=0` after stale report refresh
- `stale_core_report_cards=0` in the automation JSON summary
- command center loads without expensive synchronous table scans
- bottleneck CSV is generated each run
- A-HIS / Accountant score fields are populated on fresh reports
- no duplicate automation runs overlap
- logs are enough to diagnose failures without Codex intervention

## Saved Smoke Tests

Run this after local startup, after deploys, and before declaring the Accountant ready:

```powershell
uv run python scripts\accountant_smoke_tests.py --base-url http://127.0.0.1:8010 --ticker AAPL
```

The smoke suite checks health, readiness, dashboard, report machine status, source integrity, integration status, reports, latest report cards, sectors, bottlenecks, buy-board status, paper books, market-data status, and ticker-specific integration/company/quote endpoints.

Every run writes:

- `artifacts/smoke/accountant_smoke_<timestamp>.json`
- `artifacts/smoke/accountant_smoke_latest.json`

Treat a failed smoke as a deployment/runtime blocker, not a cosmetic warning.

## Missing Critical Data Fix Path

The largest missing-data bucket is the accounting factor pack. Fix order:

1. Improve canonical mappings for current assets, current liabilities, interest expense, capex, dividends, CFO, net income, equity, and shares.
2. Add model-family routing so banks, insurers, REITs, pre-revenue biotech, operating companies, AI/compute, and energy/resources use the right gates.
3. Add MD&A/risk-factor text extraction for management-stated bottlenecks.
4. Add non-GAAP, governance, ownership, and short-interest data sources.
5. Run `-RefreshAllScores` after each scoring/mapping upgrade.
