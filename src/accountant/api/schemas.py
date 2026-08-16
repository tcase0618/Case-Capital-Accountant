from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cik: str
    ticker: str
    name: str
    entity_type: str | None
    sic: str | None
    sic_description: str | None
    fiscal_year_end: str | None
    state_of_incorporation: str | None
    filings_count: int = 0
    raw_facts_count: int = 0
    canonical_facts_count: int = 0
    statement_snapshots_count: int = 0
    research_records_count: int = 0
    latest_filing_date: date | None = None


class CompanyListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    cik: str
    name: str
    filings_count: int
    raw_facts_count: int
    canonical_facts_count: int
    statement_snapshots_count: int
    research_records_count: int
    latest_filing_date: date | None
    coverage_status: str


class RawFactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    accession_number: str | None
    concept: str
    taxonomy: str | None
    unit: str | None
    period_start: date | None
    period_end: date | None
    instant_date: date | None
    value_numeric: Decimal | None
    value_text: str | None
    form: str | None
    filed_date: date | None
    fiscal_year: int | None
    fiscal_period: str | None
    frame: str | None
    label: str | None
    description: str | None
    source_type: str


class FilingDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence: int | None
    document_name: str
    document_type: str | None
    description: str | None
    size_bytes: int | None
    url: str | None


class FilingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    accession_number: str
    form_type: str
    filing_date: date
    report_date: date | None
    accepted_at: str | None
    primary_document: str | None
    primary_doc_description: str | None
    is_amendment: bool
    is_xbrl: bool | None
    is_inline_xbrl: bool | None
    source_url: str | None
    documents: list[FilingDocumentResponse]


class CanonicalFactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    raw_fact_id: UUID
    canonical_concept_code: str
    canonical_label: str | None
    value: str | None
    value_numeric: Decimal | None
    unit: str | None
    mapping_rule: str | None
    mapping_version: int
    mapping_confidence: str
    reported_or_derived: str
    notes: str | None
    raw_taxonomy: str | None
    raw_concept: str | None
    accession_number: str | None
    filing_form: str | None
    period_end: date | None


class StatementSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    statement_type: str
    fiscal_year: int
    fiscal_quarter: int | None
    period_type: str | None
    start_date: date | None
    end_date: date | None
    instant_date: date | None
    source_accessions: list[str] | None
    primary_accession: str | None
    builder_version: str
    mapping_version: int
    resolver_version: str
    quality_status: str
    completeness: float | None
    warnings: list[str] | None
    is_restated: bool
    created_at: str | None


class ResearchRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    as_of_date: str
    classification: str
    classification_confidence: float | None
    accounting_quality_score: float | None
    owner_earnings_yield_pct: float | None
    roic_pct: float | None
    capital_allocation_score: float | None
    credit_quality_score: float | None
    forensic_risk_score: float | None
    valuation_range_low: float | None
    valuation_range_high: float | None
    current_price: float | None
    margin_of_safety_pct: float | None
    rules_triggered: list[str]
    rules_failed: list[str]
    warnings: list[str]
    classification_notes: str | None
    created_at: str | None


class TaxonomyConceptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str
    description: str | None
    category: str | None
    unit_hint: str | None
    version: int
    is_active: bool


class DashboardStatsResponse(BaseModel):
    total_companies: int
    total_filings: int
    total_raw_facts: int
    total_canonical_facts: int
    total_statement_snapshots: int
    total_research_records: int
    companies_with_raw_facts: int = 0
    companies_with_canonical_facts: int = 0
    companies_with_statement_snapshots: int = 0
    companies_with_research_records: int = 0
    companies_with_reports: int = 0


class FilingFeedItemResponse(BaseModel):
    ticker: str
    company_name: str
    accession_number: str
    form_type: str
    filing_date: date
    accepted_at: str | None


class DashboardResponse(BaseModel):
    generated_at: str
    stats: DashboardStatsResponse
    coverage: list[CompanyListItemResponse]
    recent_filings: list[FilingFeedItemResponse]
    ticker_tape: list[str]
    backlog: list[str]


class AvailableStatementResponse(BaseModel):
    statement_type: str
    period: str
    fiscal_end_date: str
    filing_type: str
    filed_date: str
    accepted_timestamp: str
    is_restated: bool
    original_filing_timestamp: str
    latest_amendment_timestamp: str


class HistoricalSnapshotResponse(BaseModel):
    company_id: str
    as_of_date: str
    as_of_timestamp: str
    available_annual_filings: list[AvailableStatementResponse]
    available_quarterly_filings: list[AvailableStatementResponse]
    available_amendments: list[AvailableStatementResponse]
    accounting_metrics_available: bool
    owner_earnings_available: bool
    roic_available: bool
    incremental_roic_available: bool
    economic_debt_available: bool
    dilution_available: bool
    capital_allocation_available: bool
    forensic_analysis_available: bool
    accounting_dna_available: bool
    accounting_twin_available: bool
    valuation_inputs_available: bool
    market_cap_available: bool
    debt_data_available: bool
    peer_data_available: bool
    historical_price_available: bool
    raw_fact_coverage_pct: float
    canonical_mapping_coverage_pct: float
    statement_completeness_score: float
    warnings: list[str]
    coverage_notes: str


class ActionResultResponse(BaseModel):
    status: str
    message: str
    details: dict[str, int | str | bool | list[str] | None]


class UniverseImportRequest(BaseModel):
    universe_name: str | None = None
    ticker_blob: str


class UniverseImportResponse(BaseModel):
    status: str
    message: str
    mode: str
    requested: int
    imported: int
    existing: int
    unresolved: list[str]
    invalid: list[str]
    imported_tickers: list[str]


class MarketQuoteResponse(BaseModel):
    ok: bool
    symbol: str
    checked_at: str
    data_quality: str | None = None
    reason: str | None = None
    quote: dict[str, float | None] | None = None
    config: dict[str, str | int | bool | None]
    errors: list[dict[str, str | int | None]] | None = None


class IntegrationStatusResponse(BaseModel):
    ok: bool
    connected: bool | None = None
    checked_at: str
    quality: str | None = None
    reason: str | None = None
    config: dict[str, str | int | bool | None]
    errors: list[dict[str, str | int | None]] | None = None


class CompanyReportResponse(BaseModel):
    ticker: str
    company_name: str
    as_of_date: str
    stance: str
    bullish_score: float
    bearish_score: float
    composite_score: float
    data_quality_tier: str | None = None
    pipeline_stage: str
    latest_filing_date: str | None = None
    current_price: float | None = None
    key_stats: dict[str, float | int | str | None]
    highlights: list[str]
    report_markdown: str
    updated_at: str | None = None


class ReportCardResponse(BaseModel):
    ticker: str
    cik: str
    company_name: str
    sic_code: str | None = None
    gics_sector: str | None = None
    gics_industry: str | None = None
    exchange: str | None = None
    filing_type: str
    period_of_report: str | None = None
    filed_date: str
    accepted_at: str | None = None
    accession_number: str
    source_url: str | None = None
    is_restatement: bool
    prior_report_card_id: str | None = None
    standardized_financials: dict[str, object]
    growth_trend_deltas: dict[str, object]
    accrual_cash_quality: dict[str, object]
    forensic_scores: dict[str, object]
    positive_quality: dict[str, object]
    event_red_flags: dict[str, object]
    textual_signals: dict[str, object]
    non_gaap_forensics: dict[str, object]
    governance_ownership: dict[str, object]
    market_data_linkage: dict[str, object]
    universe_tradability: dict[str, object]
    final_verdict: dict[str, object]
    created_at: str | None = None


class BuyBoardCandidateResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str | None = None
    status: str
    source_report_date: str | None = None
    source_report_score: float | None = None
    first_price: float | None = None
    first_price_at: str | None = None
    current_price: float | None = None
    current_price_at: str | None = None
    first_cc_valuation: float | None = None
    first_valuation_at: str | None = None
    current_cc_valuation: float | None = None
    current_valuation_at: str | None = None
    cc_valuation_growth_forecast_pct: float | None = None
    upside_pct: float | None = None
    synopsis: str
    why_buy: list[str]
    accounting_basis: dict[str, float | int | str | None]
    battle_card: dict[str, object]
    last_price_refresh_at: str | None = None
    last_price_source: str | None = None
    current_market_data_quality: str | None = None
    last_price_error: str | None = None
    updated_at: str | None = None


class BuyBoardStatusResponse(BaseModel):
    running: bool
    started_at: str | None = None
    next_refresh_at: str | None = None
    last_refresh_at: str | None = None
    last_action: str | None = None
    last_error: str | None = None
    candidate_count: int
    last_refresh_count: int
    last_success_count: int


class FutureCandidateResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str | None = None
    stance: str
    composite_score: float
    source_report_date: str | None = None
    source_report_score: float | None = None
    current_price: float | None = None
    current_cc_valuation: float | None = None
    cc_valuation_growth_forecast_pct: float | None = None
    upside_pct: float | None = None
    synopsis: str
    designation_profile: str | None = None
    forecast_confidence_pct: float | None = None
    surprise_score: float | None = None
    surprise_upside_pct: float | None = None
    revenue_forecast_next_quarter_pct: float | None = None
    revenue_forecast_next_year_pct: float | None = None
    margin_forecast_pct: float | None = None
    owner_earnings_forecast: float | None = None
    eps: float | None = None
    eps_forecast: float | None = None
    scenario_bear_value: float | None = None
    scenario_base_value: float | None = None
    scenario_bull_value: float | None = None
    why_buy: list[str] = []
    accounting_basis: dict[str, float | int | str | None]
    battle_card: dict[str, object]


class CacheWarmStatusResponse(BaseModel):
    running: bool
    started_at: str | None = None
    finished_at: str | None = None
    phase: str | None = None
    last_action: str | None = None
    last_error: str | None = None
    reports_examined: int = 0
    active_candidates: int = 0
    monitor_candidates: int = 0


class ReportMachineStatusResponse(BaseModel):
    running: bool
    started_at: str | None = None
    last_cycle_at: str | None = None
    last_action: str | None = None
    last_error: str | None = None
    total_companies: int
    reports_cached: int
    processed_cycles: int
    last_processed_ticker: str | None = None
    pending_companies: int = 0
    universe_counts: dict[str, int]
    last_universe_sync_date: str | None = None
    worker_states: list[ReportWorkerStatusResponse] = []


class ReportWorkerStatusResponse(BaseModel):
    worker_id: int
    ticker: str | None = None
    status: str
    last_action: str | None = None
    last_completed_ticker: str | None = None
