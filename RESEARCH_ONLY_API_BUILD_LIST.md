# Research-Only API Build List

As of `2026-08-30`, the Accountant is close to a usable research-only API, but it is not at a clean finish state yet.

## Current status

- `done`: read-only FastAPI endpoints for companies, canonical facts, reports, report cards, buy board, future board, market quote, and integration readiness
- `done`: report machine status surface with `pending`, `runnable`, `blocked`, and worker states
- `done`: integration endpoints at `/api/integration/accountant` and `/api/integration/accountant/{ticker}`
- `done`: targeted API tests for the main response surface
- `partial`: backend startup wrapper is less reliable than direct `uv run python scripts/serve_local.py`
- `partial`: market-data endpoint is research-only, but credentials are currently missing on this host
- `partial`: queue is still processing the remaining `58` runnable companies
- `partial`: dashboard aggregate truth still needs a durable persisted refresh strategy for the largest tables

## Finish criteria

The research-only API is considered ready when all of these are true:

1. `GET /health` returns `200`
2. `GET /api/reports/status` returns `200` and shows a stable loop with no active DB timeout errors
3. `GET /api/integration/accountant` returns `200`
4. `GET /api/integration/accountant/{ticker}` returns `200` for real tickers
5. `GET /api/reports`, `GET /api/report-cards/latest`, and `GET /api/companies/{ticker}/canonical-facts` return `200`
6. research-only market-data status is explicit and truthful
7. the startup path is repeatable from one command
8. the repo has a known checkpoint for deploy or handoff

## Remaining build items

### 1. Runtime and startup

- make `scripts/start-accountant.ps1` capture stdout/stderr to `.run` logs
- extend startup wait time so PostgreSQL boot plus API startup do not look like a failed launch
- keep one canonical local start path and one canonical stop path
- add one smoke-check script that verifies the research-only API end to end

### 2. Readiness and observability

- automate checks for `/health`, `/api/reports/status`, `/api/integration/accountant`, `/api/integrations/ibkr`, and one ticker integration endpoint
- mark `ready`, `partial`, and `blocked` states explicitly
- surface credential status separately from API availability so missing quotes do not look like a broken API
- keep queue status and integration readiness in one machine-readable report

### 3. Research-data correctness

- finish the remaining `58` runnable companies or intentionally park them with a documented reason
- verify there are no recurrent `psycopg` connection timeout errors while the loop is running
- keep buy-board phrasing and payload math truthful when owner earnings or valuations are negative or missing
- finish a durable dashboard metrics strategy for large PostgreSQL tables

### 4. Market-data readiness

- load the research-only Alpaca credentials on the host that runs the API
- verify `/api/integrations/ibkr` reports `ok: true`, `connected: true`, and `quality: research_only`
- verify `/api/companies/{ticker}/market-quote` returns usable payloads for real tickers
- keep order mutation blocked before HTTP at all times

### 5. Verification and checkpointing

- run `uv run pytest tests/test_api.py -q`
- run the research-only readiness smoke check against the live server
- save the output of the smoke check in `.run`
- commit the repo to a known checkpoint once the research-only bar is met

## Work completed in this pass

- integration readiness endpoints already exist and are live
- targeted API tests are passing
- buy-board wording for negative owner earnings was corrected
- this build list now exists in-repo as the canonical finish checklist

## Next highest-leverage moves

1. stabilize `start-accountant.ps1`
2. add and run a research-only readiness check script
3. wire research credentials for market quotes
4. drain or intentionally park the remaining runnable backlog
