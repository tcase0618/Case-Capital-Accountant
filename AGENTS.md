# THE ACCOUNTANT — Agent Instructions

THE ACCOUNTANT is a deterministic accounting and fundamental research system for Case Capital.

Grok Build (or any other coding assistant) may write code. The running application must never call a language model.

These rules are permanent. They are not optional. They are not superseded by later prompts unless a later prompt explicitly amends this file and the amendment is reviewed.

## Permanent rules

1. **Zero LLM integrations.** Do not add OpenAI, xAI runtime APIs, Anthropic, Gemini, Ollama, OpenRouter, LangChain, LangGraph, embeddings, AI agents, chat completions, or any generative AI feature. Do not add LLM API key fields to configuration. Deterministic Python, SQL, rules, formulas, and structured data only.

2. **SEC/XBRL data is the source of accounting facts.** Company financials come from SEC EDGAR filings and their XBRL/iXBRL payloads. Market commentary, broker notes, and model output are not accounting facts.

3. **Raw source data is immutable.** Rows that represent source facts (`raw_facts` and raw source files under `data/raw/`) are insert-only. Never UPDATE or DELETE them to "correct" a value. Corrections are new rows with provenance, or a later filing.

4. **Python calculates.** Derived metrics, ratios, restatements, and mappings are computed in versioned Python (or SQL that implements a versioned formula). Do not hide calculations in notebooks, spreadsheets, or prompt text.

5. **SQL stores.** PostgreSQL is the system of record. DuckDB and Parquet are analytics/export layers. They must be rebuildable from PostgreSQL + immutable raw files.

6. **Every derived metric must retain provenance.** A calculated value is incomplete unless it records: source filing(s), source fact identity, formula/rule version, and inputs used. Missing provenance is a defect.

7. **Missing data must never be silently guessed.** If a fact, mapping, or date is absent, store NULL / raise / flag explicitly. Do not impute, interpolate, or "fill from last year" unless a named, versioned rule does so and records that it did.

8. **Accounting formulas and mapping rules must be versioned.** Concept maps, statement layouts, and ratio definitions live under versioned identifiers. Changing a formula is a new version, not an in-place edit of history.

9. **Tests are required before declaring functionality complete.** New behavior needs unit or integration tests. Run the relevant tests. Do not claim a milestone is done if tests were not run or are failing because of that work.

10. **This project has no trade-execution responsibilities.** THE ACCOUNTANT does not place, route, or manage orders. It does not talk to brokers. It researches and accounts. Execution belongs to other Case Capital systems.

## Scope discipline

Build only the requested milestone. Do not implement later modules (CompanyFacts, Arelle, statement reconstruction, valuation, forensics) until asked.

## Engineering defaults

- Prefer explicit types, small modules, and boring control flow.
- Fail loudly on contract violations (malformed ticker, missing User-Agent, HTTP errors after retries).
- Log structured events for SEC requests, inserts, and skips.
- Ingestion must be idempotent on natural keys (CIK, ticker, accession number, fact hash).
- Linux VPS is the target runtime; keep paths portable via `pathlib` and environment config.
