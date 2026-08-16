# THE ACCOUNTANT

Deterministic accounting and fundamental research system for Case Capital.

THE ACCOUNTANT ingests SEC EDGAR data, stores it immutably, and will later reconstruct statements and compute versioned metrics in Python and SQL. It contains **no LLM integrations**. Coding assistants may write the code; the running system does not call models.

This repository currently implements **Prompt 1 + Prompt 2**:
- **Prompt 1**: Project foundation + SEC company-submissions / filing-metadata ingestion
- **Prompt 2**: CompanyFacts API ingestion + raw XBRL fact normalization

## What these milestones do

### Prompt 1
- Project skeleton: `uv`, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, DuckDB, Parquet, Typer, Rich, pytest, Ruff, Docker Compose, structured logging
- Tables: `companies`, `securities`, `filings`, `filing_documents`, `raw_facts`
- `SecClient` with SEC User-Agent, ticker → CIK, rate limiting, retries, backoff
- Idempotent ingestion of company submissions filing metadata
- CLI: `doctor`, `company`, `ingest filings`, `filing latest`
- `GET /health`

### Prompt 2
- SEC CompanyFacts API client (`CompanyFactsClient`)
- Raw XBRL fact ingestion with deterministic hashing
- Fact deduplication (identical facts → same hash)
- Filing linkage (accession number → filing)
- Extended `raw_facts` table with XBRL metadata (concept, taxonomy, unit, period, form, label, etc.)
- CLI: `ingest-companyfacts TICKER`, `facts TICKER`, `companyconcept TICKER TAXONOMY CONCEPT`
- Documentation: `docs/companyfacts.md`

They do **not** yet parse Arelle-validated XBRL instances, canonicalize taxonomy, resolve periods, reconstruct statements, compute formulas, or perform valuation/forensics.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16 (Docker Compose provided) for local/VPS persistence
- Tests run against in-memory SQLite and do not require Postgres

## Quick start

```bash
cd the-accountant
cp .env.example .env
# Set SEC_USER_AGENT to something the SEC will accept, e.g.
# SEC_USER_AGENT="Case Capital Accountant accountant@casecapital.example"
```

```bash
uv sync --extra dev
docker compose up -d postgres
uv run alembic upgrade head
uv run accountant doctor
```

## Local app boot

For a reliable local-first launch on Windows, use the bundled startup script. It builds the frontend if needed, forces a local SQLite database for the app process, starts the backend on `http://127.0.0.1:8010`, and serves the built frontend from the same port.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-accountant.ps1
```

Stop it with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-accountant.ps1
```

## CLI

### Core Commands

```bash
uv run accountant doctor                               # Check configuration & environment
uv run accountant company AAPL                         # Look up company by ticker
uv run accountant ingest filings AAPL                  # Ingest SEC filing metadata
uv run accountant filing latest AAPL                   # Get latest filing
```

### CompanyFacts Commands (Prompt 2)

```bash
# Ingest XBRL facts from SEC CompanyFacts API
# (requires: SEC_USER_AGENT set, company already ingested via `ingest filings`)
uv run accountant ingest-companyfacts AAPL

# Query raw XBRL facts with optional filters
uv run accountant facts AAPL                           # All facts for AAPL
uv run accountant facts AAPL --concept Assets          # Filter by concept
uv run accountant facts AAPL --taxonomy us-gaap        # Filter by taxonomy
uv run accountant facts AAPL --form 10-K               # Filter by form
uv run accountant facts AAPL --limit 50                # Limit results

# Retrieve historical data for a single concept
uv run accountant companyconcept AAPL us-gaap Assets
```

`accountant doctor` checks configuration, the configured database, DuckDB, required directories, and the Python environment.

## API

```bash
uv run uvicorn accountant.api.app:app --reload --host 0.0.0.0 --port 8000
```

```http
GET /health
```

## Tests and lint

```bash
uv run pytest
uv run ruff check src tests
```

## Layout

```
src/accountant/
  api/          FastAPI app
  cli/          Typer commands
  config.py     Environment settings (no LLM keys)
  db/           SQLAlchemy models and session
  domain/       Ticker/CIK rules (no I/O)
  ingest/       Company + filing persistence
  sec/          SEC HTTP client
  storage/      DuckDB + Parquet helpers
alembic/        Schema migrations
tests/          pytest suite with mocked SEC HTTP
```

## Configuration

See `.env.example`. Required for live SEC calls:

| Variable | Purpose |
| --- | --- |
| `SEC_USER_AGENT` | SEC-compliant User-Agent (`Name email@domain`) |
| `DATABASE_URL` | SQLAlchemy URL (`postgresql+psycopg://...`) |
| `ACCOUNTANT_ENV` | `development` / `production` |
| `LOG_LEVEL` | `INFO`, `DEBUG`, … |
| `DATA_DIR` | Raw files, DuckDB, Parquet |
| `MARKET_DATA_MODE` | Keep as `research_only` |
| `IBKR_ENABLED` | Enable IBKR research profile |
| `IBKR_HOST` / `IBKR_PORT` | TWS or IB Gateway host/port |
| `IBKR_CLIENT_ID` | Read-only client id for IBKR session |
| `IBKR_READ_ONLY` | Should remain `true` |
| `IBKR_ACCOUNT_ID` | Optional account identifier |

There are no LLM API key fields. Do not add any.

Notes:
- `SEC_USER_AGENT` is not an API key. It is just an identifying string required by the SEC, for example `Case Capital Accountant you@example.com`.
- IBKR in this repo is treated as a research-only connectivity profile, not an order-routing path.

## Linux VPS notes

1. Clone the repo and copy `.env.example` → `.env`.
2. Set `ACCOUNTANT_ENV=production` and a strong Postgres password.
3. `docker compose up -d --build`
4. Run `alembic upgrade head` inside the api container (or a one-shot migrate service).
5. Confirm `curl -fsS http://127.0.0.1:8000/health` and `accountant doctor`.

## Permanent product rules

Documented in [`AGENTS.md`](AGENTS.md): zero LLMs, SEC/XBRL as fact source, immutable raw data, Python calculates, SQL stores, provenance required, no silent guesses, versioned formulas, tests before "done", no trade execution.
