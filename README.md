# THE ACCOUNTANT

Deterministic accounting and fundamental research system for Case Capital.

THE ACCOUNTANT ingests SEC EDGAR data, stores it immutably, and will later reconstruct statements and compute versioned metrics in Python and SQL. It contains **no LLM integrations**. Coding assistants may write the code; the running system does not call models.

This repository currently implements **Prompt 1**: project foundation + SEC company-submissions / filing-metadata ingestion.

## What this milestone does

- Project skeleton: `uv`, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, DuckDB, Parquet, Typer, Rich, pytest, Ruff, Docker Compose, structured logging
- Tables: `companies`, `securities`, `filings`, `filing_documents`, `raw_facts`
- `SecClient` with SEC User-Agent, ticker → CIK, rate limiting, retries, backoff
- Idempotent ingestion of company submissions filing metadata
- CLI: `doctor`, `company`, `ingest filings`, `filing latest`
- `GET /health`

It does **not** yet parse XBRL, CompanyFacts, Arelle, statements, formulas, valuation, or forensics.

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

## CLI

```bash
uv run accountant doctor
uv run accountant company AAPL
uv run accountant ingest filings AAPL
uv run accountant filing latest AAPL
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

There are no LLM API key fields. Do not add any.

## Linux VPS notes

1. Clone the repo and copy `.env.example` → `.env`.
2. Set `ACCOUNTANT_ENV=production` and a strong Postgres password.
3. `docker compose up -d --build`
4. Run `alembic upgrade head` inside the api container (or a one-shot migrate service).
5. Confirm `curl -fsS http://127.0.0.1:8000/health` and `accountant doctor`.

## Permanent product rules

Documented in [`AGENTS.md`](AGENTS.md): zero LLMs, SEC/XBRL as fact source, immutable raw data, Python calculates, SQL stores, provenance required, no silent guesses, versioned formulas, tests before "done", no trade execution.
