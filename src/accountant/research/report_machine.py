from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from accountant.config import get_settings
from accountant.db import create_db_engine, create_session_factory, sqlite_write_guard
from accountant.db.models import (
    CanonicalFact,
    Company,
    CompanyReport,
    Filing,
    RawFact,
    ResearchRecord,
    Security,
    StatementSnapshot,
)
from accountant.domain.exceptions import TickerNotFoundError
from accountant.financial.snapshot_service import build_company_statement_snapshots
from accountant.ingest.canonical_ingestion import CanonicalFactIngestion
from accountant.ingest.companies import import_companies_from_tickers
from accountant.ingest.companyfacts import (
    ingest_company_facts_payload,
)
from accountant.ingest.filings import (
    fetch_company_filings_payload,
    ingest_company_filings_payload,
)
from accountant.logging import get_logger
from accountant.market.alpaca_research import quote as alpaca_quote
from accountant.research.bottleneck_engine import upsert_company_bottleneck_snapshot
from accountant.research.buy_board import (
    _estimate_cc_valuation,
    _estimate_share_count,
    sync_buy_board_candidate,
)
from accountant.research.classification_engine import FundamentalResearchClassificationEngine
from accountant.research.company_router import route_company
from accountant.research.data_quality_engine import ResearchDataQualityEngine
from accountant.research.factor_engine import build_accounting_factor_pack
from accountant.research.filing_signal_engine import (
    build_event_red_flags,
    build_governance_signals,
    build_non_gaap_signals,
    build_textual_signals,
)
from accountant.research.grading_engine import GradingInputs, ReportCardGradingEngine
from accountant.research.report_cards import persist_report_card
from accountant.research.research_controls import build_research_controls, build_valuation_range
from accountant.research.universe_signal_engine import membership_for_ticker
from accountant.sec import SecClient
from accountant.sec.companyfacts import CompanyFactsClient
from accountant.sec.exceptions import SecHttpError
from accountant.universe import load_universe_tickers

log = get_logger(__name__)

_NON_OPERATING_NAME_MARKERS = (
    "acquisition corp",
    "acquisition corporation",
    "acquisition co",
    "acquisition company",
    "blank check",
    "spac",
)

# Full report-card scoring belongs to financial statements and explicitly
# material SEC events. Ownership forms remain available as source evidence but
# must not replace a company's latest accounting report.
_REPORT_CARD_FILING_TYPES = {
    "10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A", "6-K",
    "8-K", "8-K/A", "NT 10-K", "NT 10-Q", "UPLOAD", "CORRESP",
}

_BASE_WORKER_ROLES: list[dict[str, Any]] = [
    {
        "role": "sec-filings-a",
        "label": "SEC FILINGS A",
        "primary_lane": "filings",
        "fallback_lanes": ["report-build", "report-refresh"],
    },
    {
        "role": "sec-filings-b",
        "label": "SEC FILINGS B",
        "primary_lane": "filings",
        "fallback_lanes": ["report-build", "report-refresh"],
    },
    {
        "role": "companyfacts",
        "label": "COMPANYFACTS",
        "primary_lane": "companyfacts",
        "fallback_lanes": ["canonical", "report-build"],
    },
    {
        "role": "canonical",
        "label": "CANONICAL",
        "primary_lane": "canonical",
        "fallback_lanes": ["statements", "report-build"],
    },
    {
        "role": "statements",
        "label": "STATEMENTS",
        "primary_lane": "statements",
        "fallback_lanes": ["report-build", "report-refresh"],
    },
    {
        "role": "reports-a",
        "label": "REPORTS A",
        "primary_lane": "report-build",
        "fallback_lanes": ["report-refresh", "strategy"],
    },
    {
        "role": "reports-b",
        "label": "REPORTS B",
        "primary_lane": "report-build",
        "fallback_lanes": ["report-refresh", "strategy"],
    },
    {
        "role": "strategy",
        "label": "STRATEGY",
        "primary_lane": "strategy",
        "fallback_lanes": ["report-refresh", "report-build"],
    },
]


@dataclass
class MachineSnapshot:
    running: bool = False
    started_at: str | None = None
    last_cycle_at: str | None = None
    last_action: str | None = None
    last_error: str | None = None
    total_companies: int = 0
    reports_cached: int = 0
    processed_cycles: int = 0
    last_processed_ticker: str | None = None
    pending_companies: int = 0
    runnable_companies: int = 0
    blocked_companies: int = 0
    blocked_examples: list[dict[str, str]] = field(default_factory=list)
    universe_counts: dict[str, int] = field(default_factory=dict)
    last_universe_sync_date: str | None = None
    worker_states: list[dict[str, str | int | None]] = field(default_factory=list)


class ContinuousResearchMachine:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._snapshot = MachineSnapshot()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._wake.clear()
            self._snapshot.running = True
            self._snapshot.started_at = datetime.now(UTC).isoformat()
            self._snapshot.worker_states = self._blank_worker_states()
            self._thread = threading.Thread(target=self._run, daemon=True, name="accountant-report-machine")
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        with self._lock:
            self._snapshot.running = False
            self._snapshot.worker_states = self._blank_worker_states()

    def run_once(self) -> dict[str, Any]:
        self._wake.set()
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            running = bool(self._thread and self._thread.is_alive() and not self._stop.is_set())
            self._snapshot.running = running
            return {
                "running": running,
                "started_at": self._snapshot.started_at,
                "last_cycle_at": self._snapshot.last_cycle_at,
                "last_action": self._snapshot.last_action,
                "last_error": self._snapshot.last_error,
                "total_companies": self._snapshot.total_companies,
                "reports_cached": self._snapshot.reports_cached,
                "processed_cycles": self._snapshot.processed_cycles,
                "last_processed_ticker": self._snapshot.last_processed_ticker,
                "pending_companies": self._snapshot.pending_companies,
                "runnable_companies": self._snapshot.runnable_companies,
                "blocked_companies": self._snapshot.blocked_companies,
                "blocked_examples": [dict(item) for item in self._snapshot.blocked_examples],
                "universe_counts": dict(self._snapshot.universe_counts),
                "last_universe_sync_date": self._snapshot.last_universe_sync_date,
                "worker_states": [dict(item) for item in self._snapshot.worker_states],
            }

    def _blank_worker_states(self) -> list[dict[str, str | int | None]]:
        return [
            {
                "worker_id": spec["worker_id"],
                "role": spec["label"],
                "ticker": None,
                "status": "standby",
                "last_action": "standby",
                "last_completed_ticker": None,
            }
            for spec in _worker_role_specs(max(1, get_settings().machine_workers))
        ]

    def _set_worker_state(
        self,
        worker_index: int,
        *,
        role: str | None = None,
        ticker: str | None = None,
        status: str | None = None,
        last_action: str | None = None,
        last_completed_ticker: str | None = None,
    ) -> None:
        with self._lock:
            while len(self._snapshot.worker_states) <= worker_index:
                next_id = len(self._snapshot.worker_states) + 1
                self._snapshot.worker_states.append(
                    {
                        "worker_id": next_id,
                        "role": _worker_role_specs(next_id)[next_id - 1]["label"],
                        "ticker": None,
                        "status": "standby",
                        "last_action": "standby",
                        "last_completed_ticker": None,
                    }
                )
            state = self._snapshot.worker_states[worker_index]
            if role is not None:
                state["role"] = role
            if ticker is not None or status in {"idle", "standby", "complete"}:
                state["ticker"] = ticker
            if status is not None:
                state["status"] = status
            if last_action is not None:
                state["last_action"] = last_action
            if last_completed_ticker is not None:
                state["last_completed_ticker"] = last_completed_ticker

    def _mark_progress(self, action: str) -> None:
        with self._lock:
            self._snapshot.last_action = action
            self._snapshot.last_cycle_at = datetime.now(UTC).isoformat()

    def _run(self) -> None:
        interval = max(5, get_settings().machine_interval_seconds)
        try:
            while not self._stop.is_set():
                try:
                    has_pending = self._run_cycle()
                except Exception as exc:  # pragma: no cover - daemon runtime protection
                    error_text = _safe_error_text(exc)
                    log.error("machine.cycle_failed", error=error_text)
                    with self._lock:
                        self._snapshot.last_error = error_text[:500]
                        self._snapshot.last_cycle_at = datetime.now(UTC).isoformat()
                    has_pending = True
                self._wake.wait(timeout=0 if has_pending else interval)
                self._wake.clear()
        finally:
            with self._lock:
                self._snapshot.running = False

    def _run_cycle(self) -> bool:
        engine = create_db_engine()
        factory = create_session_factory(engine)
        try:
            session = factory()
            try:
                self._sync_universes_if_needed(session)
                progress = self._refresh_progress_snapshot(session)
                assignments = self._load_role_assignments(session)
            finally:
                session.close()

            processed: list[str] = []
            if assignments:
                processed = self._process_role_assignments(factory, assignments)

            summary_session = factory()
            try:
                progress = self._refresh_progress_snapshot(summary_session)
            finally:
                summary_session.close()

            with self._lock:
                self._snapshot.last_cycle_at = datetime.now(UTC).isoformat()
                self._snapshot.pending_companies = progress["pending_companies"]
                self._snapshot.runnable_companies = progress["runnable_companies"]
                self._snapshot.blocked_companies = progress["blocked_companies"]
                self._snapshot.blocked_examples = progress["blocked_examples"]
                self._snapshot.processed_cycles += 1
                if processed:
                    self._snapshot.last_processed_ticker = processed[-1]
                    self._snapshot.last_action = f"processed {', '.join(processed[:3])}" if len(processed) <= 3 else f"processed {len(processed)} companies"
                elif progress["runnable_companies"] == 0:
                    self._snapshot.last_action = "coverage queue drained"
                    self._snapshot.worker_states = self._blank_worker_states()
                self._snapshot.last_error = None
        finally:
            engine.dispose()
        return progress["runnable_companies"] > 0

    def _sync_universes_if_needed(self, session: Session) -> None:
        settings = get_settings()
        today = date.today().isoformat()
        if self._snapshot.last_universe_sync_date == today:
            return
        universe_names = [item.strip() for item in settings.machine_universes.split(",") if item.strip()]
        if not universe_names:
            return
        tickers_by_universe = load_universe_tickers(universe_names)
        merged: list[str] = []
        counts: dict[str, int] = {}
        for name, tickers in tickers_by_universe.items():
            counts[name] = len(tickers)
            merged.extend(tickers)
        existing_companies = int(session.execute(select(func.count()).select_from(Company)).scalar_one())
        if existing_companies > 0:
            with self._lock:
                self._snapshot.universe_counts = counts
                self._snapshot.last_universe_sync_date = today
                self._snapshot.last_action = f"reused universe registry ({existing_companies} companies)"
            return
        with SecClient() as sec_client:
            import_companies_from_tickers(session, merged, sec_client)
        session.commit()
        with self._lock:
            self._snapshot.universe_counts = counts
            self._snapshot.last_universe_sync_date = today
            self._snapshot.last_action = f"synced universes ({sum(counts.values())} symbols)"

    def _load_role_assignments(self, session: Session) -> list[dict[str, Any]]:
        inventory = self._load_role_inventory(session)
        assignments: list[dict[str, Any]] = []
        reserved_company_ids: set[Any] = set()
        for spec in _worker_role_specs(max(1, get_settings().machine_workers)):
            lane, row = self._pick_role_assignment(inventory, spec, reserved_company_ids)
            company_id = row["company_id"] if row is not None else None
            ticker = row["ticker"] if row is not None else None
            if company_id is not None:
                reserved_company_ids.add(company_id)
            assignments.append(
                {
                    "worker_id": spec["worker_id"],
                    "role": spec["label"],
                    "lane": lane,
                    "company_id": company_id,
                    "ticker": ticker,
                }
            )
        return assignments

    def _load_role_inventory(self, session: Session) -> list[dict[str, Any]]:
        filing_counts = (
            select(
                Filing.company_id.label("company_id"),
                func.count(Filing.id).label("filings_count"),
            )
            .group_by(Filing.company_id)
            .subquery()
        )
        raw_fact_counts = (
            select(
                RawFact.company_id.label("company_id"),
                func.count(RawFact.id).label("raw_facts_count"),
            )
            .group_by(RawFact.company_id)
            .subquery()
        )
        canonical_counts = (
            select(
                CanonicalFact.company_id.label("company_id"),
                func.count(CanonicalFact.id).label("canonical_count"),
            )
            .group_by(CanonicalFact.company_id)
            .subquery()
        )
        statement_counts = (
            select(
                StatementSnapshot.company_id.label("company_id"),
                func.count(StatementSnapshot.id).label("statement_count"),
            )
            .group_by(StatementSnapshot.company_id)
            .subquery()
        )
        stmt: Select[Any] = (
            select(
                Company.id.label("company_id"),
                Security.ticker.label("ticker"),
                Company.name.label("company_name"),
                Company.entity_type.label("entity_type"),
                Security.security_type.label("security_type"),
                CompanyReport.id.label("report_id"),
                CompanyReport.pipeline_stage.label("pipeline_stage"),
                CompanyReport.updated_at.label("report_updated_at"),
                func.coalesce(filing_counts.c.filings_count, 0).label("filings_count"),
                func.coalesce(raw_fact_counts.c.raw_facts_count, 0).label("raw_facts_count"),
                func.coalesce(canonical_counts.c.canonical_count, 0).label("canonical_count"),
                func.coalesce(statement_counts.c.statement_count, 0).label("statement_count"),
            )
            .join(Security, Security.company_id == Company.id)
            .outerjoin(CompanyReport, CompanyReport.company_id == Company.id)
            .outerjoin(filing_counts, filing_counts.c.company_id == Company.id)
            .outerjoin(raw_fact_counts, raw_fact_counts.c.company_id == Company.id)
            .outerjoin(canonical_counts, canonical_counts.c.company_id == Company.id)
            .outerjoin(statement_counts, statement_counts.c.company_id == Company.id)
            .order_by(Security.ticker.asc())
        )
        return [dict(row._mapping) for row in session.execute(stmt).all()]

    def _pick_role_assignment(
        self,
        inventory: list[dict[str, Any]],
        spec: dict[str, Any],
        reserved_company_ids: set[Any],
    ) -> tuple[str, dict[str, Any] | None]:
        lanes = [spec["primary_lane"], *spec.get("fallback_lanes", [])]
        for lane in lanes:
            candidates = self._lane_candidates(inventory, lane, reserved_company_ids)
            if candidates:
                return lane, candidates[0]
        return spec["primary_lane"], None

    def _lane_candidates(
        self,
        inventory: list[dict[str, Any]],
        lane: str,
        reserved_company_ids: set[Any],
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for row in inventory:
            if row["company_id"] in reserved_company_ids:
                continue
            if not _is_priority_operating_equity(
                ticker=row["ticker"],
                company_name=row["company_name"],
                entity_type=row["entity_type"],
                security_type=row["security_type"],
            ):
                continue
            if row["pipeline_stage"] == "parked":
                continue
            if lane == "filings" or lane == "companyfacts" and row["filings_count"] > 0 and row["raw_facts_count"] == 0 or lane == "canonical" and row["raw_facts_count"] > 0 and row["canonical_count"] == 0 or lane == "statements" and row["canonical_count"] > 0 and row["statement_count"] == 0 or lane == "report-build" and row["canonical_count"] > 0 and (
                row["report_id"] is None or row["pipeline_stage"] != "reports-ready"
            ) or lane == "report-refresh" and row["canonical_count"] > 0 and row["pipeline_stage"] == "reports-ready" or lane == "strategy" and row["report_id"] is not None and row["pipeline_stage"] == "reports-ready":
                candidates.append(row)

        return sorted(candidates, key=lambda row: _lane_sort_key(lane, row))

    def _process_role_assignments(
        self,
        factory,
        assignments: list[dict[str, Any]],
    ) -> list[str]:
        processed: list[str] = []
        processed_lock = threading.Lock()

        def _worker(assignment: dict[str, Any]) -> None:
            worker_index = max(0, int(assignment["worker_id"]) - 1)
            role = str(assignment["role"])
            lane = str(assignment["lane"])
            company_id = assignment["company_id"]
            ticker = assignment["ticker"]
            if company_id is None or ticker is None:
                self._set_worker_state(
                    worker_index,
                    role=role,
                    ticker=None,
                    status="standby",
                    last_action="queue drained" if self._snapshot.pending_companies == 0 else f"standby {lane}",
                )
                return
            self._set_worker_state(
                worker_index,
                role=role,
                ticker=ticker,
                status="processing",
                last_action=f"{lane} {ticker}",
            )
            session = factory()
            try:
                company = session.get(Company, company_id)
                if company is None:
                    self._set_worker_state(
                        worker_index,
                        role=role,
                        ticker=None,
                        status="standby",
                        last_action="company missing",
                    )
                    return
                processed_ticker = self._process_company_lane(
                    session,
                    company,
                    ticker,
                    worker_index,
                    lane=lane,
                    role=role,
                )
                if processed_ticker:
                    with processed_lock:
                        processed.append(processed_ticker)
                    with self._lock:
                        self._snapshot.last_processed_ticker = processed_ticker
                        self._snapshot.last_action = f"processed {processed_ticker}"
                        self._snapshot.last_cycle_at = datetime.now(UTC).isoformat()
                    self._set_worker_state(
                        worker_index,
                        role=role,
                        ticker=None,
                        status="complete",
                        last_action=f"{lane} {processed_ticker}",
                        last_completed_ticker=processed_ticker,
                    )
                else:
                    self._set_worker_state(
                        worker_index,
                        role=role,
                        ticker=None,
                        status="standby",
                        last_action=f"standby {lane}",
                        last_completed_ticker=ticker,
                    )
            finally:
                session.close()

        threads = [
            threading.Thread(
                target=_worker,
                args=(assignment,),
                daemon=True,
                name=f"accountant-report-worker-{assignment['worker_id']}",
            )
            for assignment in assignments
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return processed

    def _process_company_lane(
        self,
        session: Session,
        company: Company,
        ticker: str,
        worker_index: int,
        *,
        lane: str,
        role: str,
    ) -> str | None:
        if lane == "filings":
            return ticker if self._refresh_company_filings(session, company, ticker, worker_index, role=role) else None
        if lane == "companyfacts":
            return ticker if self._refresh_companyfacts(session, company, ticker, worker_index, role=role) else None
        if lane == "canonical":
            return ticker if self._normalize_company_lane(session, company, ticker, worker_index, role=role) else None
        if lane == "statements":
            return ticker if self._build_statements_lane(session, company, ticker, worker_index, role=role) else None
        if lane in {"report-build", "report-refresh"}:
            return ticker if self._build_report_lane(session, company, ticker, worker_index, role=role) else None
        if lane == "strategy":
            return ticker if self._refresh_strategy_lane(session, company, ticker, worker_index, role=role) else None
        return None

    def _refresh_company_filings(
        self,
        session: Session,
        company: Company,
        ticker: str,
        worker_index: int,
        *,
        role: str,
    ) -> bool:
        self._mark_progress(f"refreshing filings {ticker}")
        self._set_worker_state(worker_index, role=role, ticker=ticker, status="processing", last_action=f"refreshing filings {ticker}")
        try:
            with SecClient() as sec_client:
                filing_payload = fetch_company_filings_payload(sec_client, ticker)
            with sqlite_write_guard():
                ingest_company_filings_payload(session, filing_payload)
                session.commit()
            return True
        except TickerNotFoundError as exc:
            session.rollback()
            log.warning("machine.ticker_unresolved", ticker=ticker, error=_safe_error_text(exc))
        except Exception as exc:
            session.rollback()
            log.warning("machine.filing_ingest_failed", ticker=ticker, error=_safe_error_text(exc)[:300])
        return False

    def _refresh_companyfacts(
        self,
        session: Session,
        company: Company,
        ticker: str,
        worker_index: int,
        *,
        role: str,
    ) -> bool:
        if _count(session, Filing, company.id) == 0:
            return False
        self._mark_progress(f"refreshing facts {ticker}")
        self._set_worker_state(worker_index, role=role, ticker=ticker, status="processing", last_action=f"refreshing facts {ticker}")
        with SecClient() as sec_client:
            companyfacts_client = CompanyFactsClient(get_settings(), sec_client=sec_client)
            try:
                facts_data = companyfacts_client.get_company_facts(company.cik)
                with sqlite_write_guard():
                    ingest_company_facts_payload(session, company, facts_data)
                    session.commit()
                return True
            except SecHttpError as exc:
                session.rollback()
                if exc.status_code == 404:
                    try:
                        with sqlite_write_guard():
                            self._build_partial_report(session, company, ticker, terminal_reason="companyfacts_404")
                            session.commit()
                        return True
                    except Exception as build_exc:
                        session.rollback()
                        log.warning("machine.partial_report_build_failed", ticker=ticker, error=str(build_exc)[:300])
                else:
                    log.warning("machine.companyfacts_ingest_failed", ticker=ticker, error=_safe_error_text(exc)[:300])
            except TickerNotFoundError as exc:
                session.rollback()
                log.warning("machine.ticker_unresolved", ticker=ticker, error=_safe_error_text(exc))
            except Exception as exc:
                session.rollback()
                log.warning("machine.companyfacts_ingest_failed", ticker=ticker, error=_safe_error_text(exc)[:300])
            finally:
                companyfacts_client.close()
        return False

    def _normalize_company_lane(
        self,
        session: Session,
        company: Company,
        ticker: str,
        worker_index: int,
        *,
        role: str,
    ) -> bool:
        raw_facts_count = _count(session, RawFact, company.id)
        if raw_facts_count == 0:
            return False
        if _count(session, CanonicalFact, company.id) > 0:
            return False
        self._mark_progress(f"canonicalizing {ticker}")
        self._set_worker_state(worker_index, role=role, ticker=ticker, status="processing", last_action=f"canonicalizing {ticker}")
        try:
            with sqlite_write_guard():
                self._normalize_company(session, company)
                session.commit()
            canonical_count = _count(session, CanonicalFact, company.id)
            if canonical_count == 0:
                with sqlite_write_guard():
                    self._build_partial_report(
                        session,
                        company,
                        ticker,
                        terminal_reason="zero_canonical_after_normalize",
                    )
                    session.commit()
            return True
        except Exception as exc:
            session.rollback()
            log.warning("machine.normalize_skipped", ticker=ticker, error=str(exc)[:300])
        return False

    def _build_statements_lane(
        self,
        session: Session,
        company: Company,
        ticker: str,
        worker_index: int,
        *,
        role: str,
    ) -> bool:
        if _count(session, CanonicalFact, company.id) == 0:
            return False
        if _count(session, StatementSnapshot, company.id) > 0:
            return False
        self._mark_progress(f"building statements {ticker}")
        self._set_worker_state(worker_index, role=role, ticker=ticker, status="processing", last_action=f"building statements {ticker}")
        try:
            with sqlite_write_guard():
                build_company_statement_snapshots(session, company.id)
                session.commit()
            return True
        except Exception as exc:
            session.rollback()
            log.warning("machine.statement_snapshot_build_failed", ticker=ticker, error=str(exc)[:300])
        return False

    def _build_report_lane(
        self,
        session: Session,
        company: Company,
        ticker: str,
        worker_index: int,
        *,
        role: str,
    ) -> bool:
        filings_count = _count(session, Filing, company.id)
        raw_facts_count = _count(session, RawFact, company.id)
        canonical_count = _count(session, CanonicalFact, company.id)
        report = _latest_company_report(session, company.id)
        if canonical_count == 0:
            if filings_count > 0 and ((raw_facts_count > 0 and report is None) or raw_facts_count == 0):
                self._mark_progress(f"seeding partial report {ticker}")
                self._set_worker_state(worker_index, role=role, ticker=ticker, status="processing", last_action=f"seeding partial report {ticker}")
                try:
                    with sqlite_write_guard():
                        self._build_partial_report(session, company, ticker)
                        session.commit()
                    return True
                except Exception as exc:
                    session.rollback()
                    log.warning("machine.partial_report_build_failed", ticker=ticker, error=str(exc)[:300])
            return False
        self._mark_progress(f"building report {ticker}")
        self._set_worker_state(worker_index, role=role, ticker=ticker, status="processing", last_action=f"building report {ticker}")
        try:
            with sqlite_write_guard():
                self._build_report(session, company, ticker)
                session.commit()
            return True
        except Exception as exc:
            session.rollback()
            log.warning("machine.report_build_failed", ticker=ticker, error=str(exc)[:300])
        return False

    def _refresh_strategy_lane(
        self,
        session: Session,
        company: Company,
        ticker: str,
        worker_index: int,
        *,
        role: str,
    ) -> bool:
        report = _latest_company_report(session, company.id)
        if report is None or report.pipeline_stage != "reports-ready":
            return False
        self._mark_progress(f"classifying {ticker}")
        self._set_worker_state(worker_index, role=role, ticker=ticker, status="processing", last_action=f"classifying {ticker}")
        try:
            with sqlite_write_guard():
                sync_buy_board_candidate(session, report)
                session.commit()
            return True
        except Exception as exc:
            session.rollback()
            log.warning("machine.strategy_refresh_failed", ticker=ticker, error=str(exc)[:300])
        return False

    def _process_company(self, session: Session, company: Company, ticker: str, worker_index: int) -> None:
        self._mark_progress(f"processing {ticker}")
        companyfacts_terminal_404 = False
        existing_report = _latest_company_report(session, company.id)
        if existing_report is not None and existing_report.pipeline_stage == "parked":
            self._set_worker_state(worker_index, ticker=ticker, status="idle", last_action=f"parked {ticker}")
            return
        with SecClient() as sec_client:
            filings_count = _count(session, Filing, company.id)
            if filings_count == 0:
                self._set_worker_state(worker_index, ticker=ticker, status="processing", last_action=f"ingesting filings {ticker}")
                self._mark_progress(f"ingesting filings {ticker}")
                try:
                    filing_payload = fetch_company_filings_payload(sec_client, ticker)
                    with sqlite_write_guard():
                        ingest_company_filings_payload(session, filing_payload)
                        session.commit()
                except TickerNotFoundError as exc:
                    session.rollback()
                    log.warning("machine.ticker_unresolved", ticker=ticker, error=_safe_error_text(exc))
                except Exception as exc:
                    session.rollback()
                    log.warning("machine.filing_ingest_failed", ticker=ticker, error=_safe_error_text(exc)[:300])
            raw_facts_count = _count(session, RawFact, company.id)
            if raw_facts_count == 0:
                self._set_worker_state(worker_index, ticker=ticker, status="processing", last_action=f"ingesting facts {ticker}")
                self._mark_progress(f"ingesting facts {ticker}")
                companyfacts_client = CompanyFactsClient(get_settings(), sec_client=sec_client)
                try:
                    facts_data = companyfacts_client.get_company_facts(company.cik)
                    with sqlite_write_guard():
                        ingest_company_facts_payload(session, company, facts_data)
                except SecHttpError as exc:
                    session.rollback()
                    if exc.status_code == 404:
                        companyfacts_terminal_404 = True
                        log.info("machine.companyfacts_unavailable", ticker=ticker, cik=company.cik)
                    else:
                        log.warning("machine.companyfacts_ingest_failed", ticker=ticker, error=_safe_error_text(exc)[:300])
                except TickerNotFoundError as exc:
                    session.rollback()
                    log.warning("machine.ticker_unresolved", ticker=ticker, error=_safe_error_text(exc))
                except Exception as exc:
                    session.rollback()
                    log.warning("machine.companyfacts_ingest_failed", ticker=ticker, error=_safe_error_text(exc)[:300])
                finally:
                    companyfacts_client.close()
                if session.in_transaction():
                    with sqlite_write_guard():
                        session.commit()
        filings_count = _count(session, Filing, company.id)
        raw_facts_count = _count(session, RawFact, company.id)
        report = _latest_company_report(session, company.id)
        if filings_count > 0 and ((raw_facts_count > 0 and report is None) or companyfacts_terminal_404):
            self._set_worker_state(worker_index, ticker=ticker, status="processing", last_action=f"seeding partial report {ticker}")
            self._mark_progress(f"seeding partial report {ticker}")
            try:
                with sqlite_write_guard():
                    self._build_partial_report(
                        session,
                        company,
                        ticker,
                        terminal_reason="companyfacts_404" if companyfacts_terminal_404 and raw_facts_count == 0 else None,
                    )
                    session.commit()
            except Exception as exc:
                session.rollback()
                log.warning("machine.partial_report_build_failed", ticker=ticker, error=str(exc)[:300])
                return
            return
        canonical_count = _count(session, CanonicalFact, company.id)
        if canonical_count == 0 and _count(session, RawFact, company.id) > 0:
            self._set_worker_state(worker_index, ticker=ticker, status="processing", last_action=f"canonicalizing {ticker}")
            self._mark_progress(f"canonicalizing {ticker}")
            try:
                with sqlite_write_guard():
                    self._normalize_company(session, company)
                    session.commit()
            except Exception as exc:
                session.rollback()
                log.warning("machine.normalize_skipped", ticker=ticker, error=str(exc)[:300])
            canonical_count = _count(session, CanonicalFact, company.id)
            if canonical_count == 0:
                self._set_worker_state(worker_index, ticker=ticker, status="processing", last_action=f"parking {ticker}")
                self._mark_progress(f"parking {ticker}")
                try:
                    with sqlite_write_guard():
                        self._build_partial_report(
                            session,
                            company,
                            ticker,
                            terminal_reason="zero_canonical_after_normalize",
                        )
                        session.commit()
                except Exception as exc:
                    session.rollback()
                    log.warning("machine.partial_report_build_failed", ticker=ticker, error=str(exc)[:300])
                return
        if _count(session, CanonicalFact, company.id) > 0:
            self._set_worker_state(worker_index, ticker=ticker, status="processing", last_action=f"building statements {ticker}")
            self._mark_progress(f"building statements {ticker}")
            try:
                with sqlite_write_guard():
                    build_company_statement_snapshots(session, company.id)
                    session.commit()
            except Exception as exc:
                session.rollback()
                log.warning("machine.statement_snapshot_build_failed", ticker=ticker, error=str(exc)[:300])
        self._set_worker_state(worker_index, ticker=ticker, status="processing", last_action=f"building report {ticker}")
        self._mark_progress(f"building report {ticker}")
        try:
            with sqlite_write_guard():
                self._build_report(session, company, ticker)
                session.commit()
        except Exception as exc:
            session.rollback()
            log.warning("machine.report_build_failed", ticker=ticker, error=str(exc)[:300])

    def _pending_count(self, session: Session) -> int:
        company_count = int(session.execute(select(func.count()).select_from(Company)).scalar_one())
        report_count = int(session.execute(select(func.count()).select_from(CompanyReport)).scalar_one())
        return max(0, company_count - report_count)

    def _refresh_progress_snapshot(self, session: Session) -> dict[str, Any]:
        company_count = int(session.execute(select(func.count()).select_from(Company)).scalar_one())
        report_count = int(session.execute(select(func.count()).select_from(CompanyReport)).scalar_one())
        backlog = self._priority_backlog(session)
        with self._lock:
            self._snapshot.total_companies = company_count
            self._snapshot.reports_cached = report_count
            self._snapshot.pending_companies = backlog["pending_companies"]
            self._snapshot.runnable_companies = backlog["runnable_companies"]
            self._snapshot.blocked_companies = backlog["blocked_companies"]
            self._snapshot.blocked_examples = backlog["blocked_examples"]
        return backlog

    def _priority_backlog(self, session: Session) -> dict[str, Any]:
        rows = session.execute(
            select(
                Company.id,
                Security.ticker,
                Company.name,
                Company.entity_type,
                Security.security_type,
                CompanyReport.id,
                CompanyReport.pipeline_stage,
            )
            .join(Security, Security.company_id == Company.id)
            .outerjoin(CompanyReport, CompanyReport.company_id == Company.id)
        ).all()
        chosen_by_company: dict[Any, dict[str, Any]] = {}
        for company_id, ticker, company_name, entity_type, security_type, report_id, pipeline_stage in rows:
            if not _is_priority_operating_equity(
                ticker=ticker,
                company_name=company_name,
                entity_type=entity_type,
                security_type=security_type,
            ):
                continue
            rank = _security_rank(ticker)
            candidate = {
                "company_id": company_id,
                "ticker": ticker,
                "report_id": report_id,
                "pipeline_stage": pipeline_stage,
                "rank": rank,
            }
            existing = chosen_by_company.get(company_id)
            if existing is None or rank > existing["rank"]:
                chosen_by_company[company_id] = candidate

        runnable = 0
        blocked = 0
        blocked_examples: list[dict[str, str]] = []
        for candidate in chosen_by_company.values():
            reason = _backlog_reason(
                report_id=candidate["report_id"],
                pipeline_stage=candidate["pipeline_stage"],
            )
            if reason is None:
                continue
            if _is_runnable_backlog_reason(reason):
                runnable += 1
            else:
                blocked += 1
                if len(blocked_examples) < 10:
                    blocked_examples.append(
                        {
                            "ticker": str(candidate["ticker"]),
                            "reason": reason,
                        }
                    )
        return {
            "pending_companies": runnable + blocked,
            "runnable_companies": runnable,
            "blocked_companies": blocked,
            "blocked_examples": blocked_examples,
        }

    def _normalize_company(self, session: Session, company: Company) -> None:
        # Keep the unattended worker deterministic and fast. Validation remains
        # available in explicit/manual normalization flows, but the report loop
        # should not stall on Arelle runtime quirks.
        ingestion = CanonicalFactIngestion(session, arelle=None)
        filings = session.execute(
            select(Filing).where(Filing.company_id == company.id).order_by(Filing.filing_date.desc())
        ).scalars().all()
        for filing in filings:
            ingestion.ingest_filing(
                filing=filing,
                company=company,
                instance_url=filing.source_url,
                mapping_version=1,
            )
        session.flush()

    def _build_partial_report(
        self,
        session: Session,
        company: Company,
        ticker: str,
        *,
        terminal_reason: str | None = None,
    ) -> None:
        filings_count = _count(session, Filing, company.id)
        raw_facts_count = _count(session, RawFact, company.id)
        canonical_count = _count(session, CanonicalFact, company.id)
        latest_filing_row = session.execute(
            select(Filing)
            .where(Filing.company_id == company.id)
            .order_by(Filing.filing_date.desc(), Filing.accepted_at.desc(), Filing.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        latest_filing = latest_filing_row.filing_date if latest_filing_row else None

        report = _latest_company_report(session, company.id)
        if report is None:
            report = CompanyReport(
                company_id=company.id,
                ticker=ticker,
                company_name=company.name,
                as_of_date=date.today().isoformat(),
                stance="NEUTRAL",
            )
            session.add(report)

        report.ticker = ticker
        report.company_name = company.name
        report.as_of_date = date.today().isoformat()
        report.stance = "NEUTRAL"
        report.bullish_score = 40.0
        report.bearish_score = 60.0
        report.composite_score = 40.0
        report.data_quality_tier = "PARTIAL"
        report.pipeline_stage = "parked" if terminal_reason else _pipeline_stage(raw_facts_count, canonical_count)
        report.latest_filing_date = latest_filing.isoformat() if latest_filing else None
        report.key_stats = {
            "filings_count": filings_count,
            "raw_facts_count": raw_facts_count,
            "canonical_facts_count": canonical_count,
            "revenue": None,
            "net_income": None,
            "assets": None,
            "liabilities": None,
            "equity": None,
            "owner_earnings": None,
            "weighted_avg_diluted_shares": None,
            "eps": None,
            "overall_coverage_pct": _maybe_round(35.0 if raw_facts_count > 0 else 15.0),
            "accounting_quality_score": 40.0,
            "future_bucket": "HOLD",
            "future_reason": (
                "SEC CompanyFacts unavailable for this issuer; parked as research-only partial coverage."
                if terminal_reason
                else "Awaiting deep accountant pass."
            ),
            "terminal_reason": terminal_reason,
        }
        report.highlights = [
            f"Coverage seeded: filings {filings_count}, raw facts {raw_facts_count}, canonical facts {canonical_count}.",
            (
                "SEC CompanyFacts is unavailable for this issuer, so the accountant parked this name with partial filing-only coverage."
                if terminal_reason
                else "This is a partial accountant report created to close universe coverage quickly."
            ),
            (
                "This row is intentionally terminal for the research-only API and will not be retried by the unattended loop."
                if terminal_reason
                else "Deep canonicalization, statement builds, and final grading will continue in later passes."
            ),
        ]
        report.report_markdown = "\n".join(
            [
                f"# {ticker} {'PARKED PARTIAL REPORT' if terminal_reason else 'PARTIAL REPORT'}",
                "",
                f"{company.name} has SEC filings and {'raw facts loaded' if raw_facts_count > 0 else 'filing-only coverage loaded'}.",
                (
                    "This row is operationally valid for the research-only API even though the issuer does not expose SEC CompanyFacts for unattended enrichment."
                    if terminal_reason
                    else "This row is operationally valid for universe coverage and will be upgraded by the deeper accountant pipeline."
                ),
            ]
        )
        report.source_versions = {
            "report_machine": "V2_CONTINUOUS_MACHINE_PARTIAL",
            "terminal_reason": terminal_reason or "",
        }
        session.flush()
        upsert_company_bottleneck_snapshot(session, company=company, report=report)

    def _build_report(self, session: Session, company: Company, ticker: str) -> None:
        filings = session.execute(
            select(Filing)
            .where(Filing.company_id == company.id)
            .order_by(Filing.filing_date.desc(), Filing.accepted_at.desc(), Filing.created_at.desc())
        ).scalars().all()
        facts = session.execute(
            select(RawFact)
            .where(RawFact.company_id == company.id)
            .order_by(
                RawFact.period_end.desc(),
                RawFact.accepted_at.desc().nullslast(),
                RawFact.filed_date.desc().nullslast(),
                RawFact.created_at.desc(),
            )
        ).scalars().all()
        filings_count = len(filings)
        raw_facts_count = len(facts)
        canonical_count = _count(session, CanonicalFact, company.id)
        latest_filing_row = _latest_report_card_filing(filings)
        latest_filing = latest_filing_row.filing_date if latest_filing_row else None
        years_of_history = len({fact.period_end.year for fact in facts if fact.period_end is not None})
        gics_sector = _sector_name(company.sic_description)
        gics_industry = company.sic_description or gics_sector
        membership = membership_for_ticker(ticker)
        prior_same_form_filing = next(
            (
                filing
                for filing in filings
                if latest_filing_row is not None
                and filing.id != latest_filing_row.id
                and filing.form_type == latest_filing_row.form_type
            ),
            None,
        )
        textual_signal_bundle = build_textual_signals(
            latest_filing_row,
            prior_same_form_filing,
            sec_user_agent=get_settings().sec_user_agent,
        )
        prior_same_form_filings = [
            filing
            for filing in filings
            if latest_filing_row is not None
            and filing.id != latest_filing_row.id
            and filing.form_type == latest_filing_row.form_type
        ]
        event_signal_bundle = build_event_red_flags(
            filings,
            sec_user_agent=get_settings().sec_user_agent,
        )

        revenue_quarterly_series = _series(
            facts,
            [
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
                "SalesRevenueNet",
            ],
            period="quarterly",
        )
        revenue_annual_series = _series(
            facts,
            [
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
                "SalesRevenueNet",
            ],
            period="annual",
        )
        net_income_quarterly_series = _series(facts, ["NetIncomeLoss"], period="quarterly")
        net_income_annual_series = _series(facts, ["NetIncomeLoss"], period="annual")
        assets_series = _series(facts, ["Assets"], period="instant")
        liabilities_series = _series(facts, ["Liabilities"], period="instant")
        equity_series = _series(
            facts,
            ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
            period="instant",
        )
        ocf_quarterly_series = _series(
            facts,
            ["NetCashProvidedByUsedInOperatingActivities"],
            period="quarterly",
        )
        ocf_annual_series = _series(
            facts,
            ["NetCashProvidedByUsedInOperatingActivities"],
            period="annual",
        )
        capex_quarterly_series = _series(
            facts,
            ["PaymentsToAcquirePropertyPlantAndEquipment"],
            period="quarterly",
        )
        capex_annual_series = _series(
            facts,
            ["PaymentsToAcquirePropertyPlantAndEquipment"],
            period="annual",
        )

        revenue = _first_value(revenue_quarterly_series) or _first_value(revenue_annual_series)
        prior_revenue = _comparable_prior_value(revenue_quarterly_series) or _comparable_prior_value(revenue_annual_series)
        net_income = _first_value(net_income_quarterly_series) or _first_value(net_income_annual_series)
        assets = _first_value(assets_series)
        liabilities = _first_value(liabilities_series)
        equity = _first_value(equity_series)
        ocf = _first_value(ocf_quarterly_series) or _first_value(ocf_annual_series)
        capex = _first_value(capex_quarterly_series) or _first_value(capex_annual_series)
        diluted_shares = _latest_fact_from_concepts(
            facts,
            [
                "WeightedAverageNumberOfDilutedSharesOutstanding",
                "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
                "WeightedAverageNumberOfSharesOutstandingBasic",
                "CommonStockSharesOutstanding",
            ],
            period="instant",
        )

        revenue_growth_pct = _pct_change(revenue, prior_revenue)
        owner_earnings = None
        if ocf is not None and capex is not None:
            owner_earnings = ocf - abs(capex)
        gross_profit = _latest_fact_from_concepts(facts, ["GrossProfit"])
        cogs = _latest_fact_from_concepts(facts, ["CostOfGoodsSold", "CostOfRevenue", "CostOfGoodsAndServicesSold"])
        if gross_profit is None and revenue is not None and cogs is not None:
            gross_profit = revenue - cogs
        gross_margin_pct = _ratio_pct(gross_profit, revenue, ceiling=1000.0)
        net_margin_pct = _ratio_pct(net_income, revenue, ceiling=1000.0)
        owner_earnings_margin_pct = _safe_divide(owner_earnings, revenue)
        if owner_earnings_margin_pct is not None:
            owner_earnings_margin_pct *= 100
        dilution_growth_pct = None
        if diluted_shares is not None:
            share_series = _series(
                facts,
                [
                    "WeightedAverageNumberOfDilutedSharesOutstanding",
                    "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
                    "WeightedAverageNumberOfSharesOutstandingBasic",
                    "CommonStockSharesOutstanding",
                ],
                period="instant",
            )
            prior_shares = _comparable_prior_value(share_series)
            dilution_growth_pct = _pct_change(diluted_shares, prior_shares)

        metric_names = {
            "revenue": revenue,
            "revenue_growth_pct": revenue_growth_pct,
            "net_income": net_income,
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "owner_earnings": owner_earnings,
        }
        metric_availability_pct = (sum(1 for value in metric_names.values() if value is not None) / len(metric_names)) * 100
        filing_coverage_pct = min(100.0, filings_count * 20.0)
        canonical_mapping_pct = (canonical_count / raw_facts_count * 100.0) if raw_facts_count else 0.0
        statement_completeness_pct = min(100.0, canonical_mapping_pct * 0.85)
        quality = ResearchDataQualityEngine.assess_data_quality(
            company_id=company.cik,
            as_of_date=date.today().isoformat(),
            filing_coverage_pct=filing_coverage_pct,
            statement_completeness_pct=statement_completeness_pct,
            metric_availability_pct=metric_availability_pct,
            canonical_mapping_coverage_pct=canonical_mapping_pct,
            years_of_history=years_of_history,
            has_restatement_history=False,
        )
        factor_pack = build_accounting_factor_pack(facts)

        leverage_ratio = (liabilities / assets) if liabilities is not None and assets not in (None, 0) else None
        profitability_ratio = (net_income / revenue) if net_income is not None and revenue not in (None, 0) else None
        balance_score = _clamp(100 - ((leverage_ratio or 0.5) * 100), 0, 100) if leverage_ratio is not None else 45.0
        profitability_score = _clamp(((profitability_ratio or 0.0) * 500) + 50, 0, 100) if profitability_ratio is not None else 45.0
        growth_score = _clamp(((revenue_growth_pct or 0.0) * 2) + 50, 0, 100) if revenue_growth_pct is not None else 40.0
        cash_score = 70.0 if owner_earnings and owner_earnings > 0 else 35.0 if owner_earnings is not None else 40.0
        factor_quality_score = factor_pack.factor_quality_score
        factor_forensic_risk_score = factor_pack.factor_forensic_risk_score
        quality_inputs = [balance_score, profitability_score, cash_score, quality.research_confidence_pct]
        if factor_quality_score is not None:
            quality_inputs.append(factor_quality_score)
        accounting_quality_score = round(sum(quality_inputs) / len(quality_inputs), 2)
        heuristic_forensic_risk = _clamp(100 - ((balance_score + profitability_score) / 2), 5, 90)
        forensic_inputs = [heuristic_forensic_risk]
        if factor_forensic_risk_score is not None:
            forensic_inputs.append(factor_forensic_risk_score)
        forensic_risk_score = round(sum(forensic_inputs) / len(forensic_inputs), 2)
        composite_inputs = [accounting_quality_score, growth_score, quality.research_confidence_pct]
        if factor_quality_score is not None:
            composite_inputs.append(factor_quality_score)
        composite_score = round(sum(composite_inputs) / len(composite_inputs), 2)
        bearish_score = round(_clamp(100 - composite_score + (forensic_risk_score / 5), 0, 100), 2)
        bullish_score = round(_clamp(composite_score, 0, 100), 2)
        stance = _stance_for_score(composite_score)
        forecast_confidence_pct = _forecast_confidence(
            filings_count=filings_count,
            years_of_history=years_of_history,
            canonical_count=canonical_count,
            raw_facts_count=raw_facts_count,
            quality_score=accounting_quality_score,
        )
        revenue_forecast_next_year_pct = round(
            _clamp((revenue_growth_pct or 0.0) * 0.72 + max(0.0, accounting_quality_score - 60.0) * 0.12, -12.0, 28.0),
            2,
        )
        revenue_forecast_next_quarter_pct = round(
            _clamp((revenue_growth_pct or 0.0) * 0.45 + max(0.0, accounting_quality_score - 60.0) * 0.08, -8.0, 18.0),
            2,
        )
        margin_forecast_pct = round(
            _clamp((net_margin_pct or 6.0) + max(0.0, accounting_quality_score - 62.0) * 0.05, -5.0, 32.0),
            2,
        )
        owner_earnings_forecast = round(
            owner_earnings * (1 + (revenue_forecast_next_year_pct / 100)),
            2,
        ) if owner_earnings is not None else None
        eps = round(net_income / diluted_shares, 2) if net_income is not None and diluted_shares not in (None, 0) else None
        security_count = len({security.ticker for security in company.securities if security.ticker})
        governance_signal_bundle = build_governance_signals(
            filings,
            sec_user_agent=get_settings().sec_user_agent,
            security_count=security_count,
        )
        non_gaap_signal_bundle = build_non_gaap_signals(
            latest_filing_row,
            prior_same_form_filings,
            sec_user_agent=get_settings().sec_user_agent,
            gaap_eps=eps,
        )
        eps_forecast = round(eps * (1 + (revenue_forecast_next_year_pct / 100)), 2) if eps is not None else None
        scenario_valuations = _scenario_valuations(
            earnings_power=owner_earnings if owner_earnings and owner_earnings > 0 else net_income,
            quality_score=accounting_quality_score,
            growth_pct=revenue_forecast_next_year_pct,
            share_count=diluted_shares,
        )
        surprise_score = _expected_surprise_score(
            revenue_growth_pct=revenue_forecast_next_year_pct,
            owner_earnings=owner_earnings_forecast,
            margin_pct=margin_forecast_pct,
            confidence_pct=forecast_confidence_pct,
            accounting_quality_score=accounting_quality_score,
        )
        designation_profile = _designation_profile(
            revenue_growth_pct=revenue_forecast_next_year_pct,
            owner_earnings=owner_earnings_forecast,
            balance_score=balance_score,
            accounting_quality_score=accounting_quality_score,
            leverage_ratio=leverage_ratio,
        )
        surprise_upside_pct = None
        if scenario_valuations["bull"] is not None and scenario_valuations["base"] not in (None, 0):
            surprise_upside_pct = round(((scenario_valuations["bull"] - scenario_valuations["base"]) / scenario_valuations["base"]) * 100, 2)
        future_bucket, future_reason = _future_bucket(
            canonical_count=canonical_count,
            surprise_score=surprise_score,
            forecast_confidence_pct=forecast_confidence_pct,
            revenue_forecast_next_year_pct=revenue_forecast_next_year_pct,
        )
        research = FundamentalResearchClassificationEngine.classify(
            company_id=company.cik,
            as_of_date=date.today().isoformat(),
            accounting_quality_score=accounting_quality_score,
            owner_earnings_yield_pct=None,
            owner_earnings_growth_pct=revenue_growth_pct,
            roic_pct=profitability_ratio * 100 if profitability_ratio is not None else None,
            capital_allocation_score=balance_score,
            credit_quality_score=balance_score,
            bear_case_risk_score=bearish_score,
            forensic_risk_score=forensic_risk_score,
            valuation_range_low=None,
            valuation_range_high=None,
            current_price=None,
            negative_fcf=bool(owner_earnings is not None and owner_earnings < 0),
            declining_revenue=bool(revenue_growth_pct is not None and revenue_growth_pct < 0),
        )

        highlights = [
            f"SEC pipeline: filings {filings_count}, raw facts {raw_facts_count}, canonical facts {canonical_count}.",
            f"Data quality tier: {quality.overall_tier} at {quality.overall_coverage_pct:.1f}% overall coverage.",
            f"Revenue growth: {_fmt_pct(revenue_growth_pct)} | Owner earnings proxy: {_fmt_num(owner_earnings)} | Leverage: {_fmt_pct(leverage_ratio * 100 if leverage_ratio is not None else None)}.",
            f"Factor pack ({factor_pack.period_label}): Beneish {_fmt_num(factor_pack.beneish_m_score)} | Piotroski {_fmt_num(float(factor_pack.piotroski_f_score) if factor_pack.piotroski_f_score is not None else None)} | Altman {_fmt_num(factor_pack.altman_z_score)}.",
            f"A-HIS ledger: {_fmt_num(factor_pack.a_his_score)} / 100 | QoE {_fmt_num((factor_pack.a_his_breakdown or {}).get('quality_of_earnings'))} | TIE {_fmt_num((factor_pack.a_his_breakdown or {}).get('times_interest_earned'))}.",
            f"Forecast pack: rev next year {_fmt_pct(revenue_forecast_next_year_pct)} | EPS forecast {_fmt_num(eps_forecast)} | confidence {forecast_confidence_pct:.1f}%.",
        ]
        if non_gaap_signal_bundle.non_gaap_eps is not None:
            highlights.append(f"Non-GAAP EPS detected at {_fmt_num(non_gaap_signal_bundle.non_gaap_eps)}.")
        if factor_pack.warnings:
            highlights.append(f"Factor warnings: {'; '.join(factor_pack.warnings[:2])}.")
        report_lines = [
            f"# {ticker} {stance}",
            "",
            f"{company.name} currently ranks {stance.lower()} on the internal SEC-only accountant model.",
            f"The report is based on {filings_count} filings, {raw_facts_count} raw facts, and {canonical_count} canonical facts cached as of {date.today().isoformat()}.",
            *highlights[1:],
            f"Research classification: {research.classification}.",
        ]
        report_markdown = "\n".join(report_lines)

        _upsert_research_record(
            session,
            company_id=company.id,
            payload={
                "company_id": company.id,
                "as_of_date": date.today().isoformat(),
                "classification": research.classification,
                "classification_confidence": round(quality.research_confidence_pct / 100, 4),
                "accounting_quality_score": accounting_quality_score,
                "owner_earnings_yield_pct": None,
                "owner_earnings_growth_pct": revenue_growth_pct,
                "roic_pct": profitability_ratio * 100 if profitability_ratio is not None else None,
                "capital_allocation_score": balance_score,
                "credit_quality_score": balance_score,
                "bear_case_risk_score": bearish_score,
                "forensic_risk_score": forensic_risk_score,
                "valuation_range_low": None,
                "valuation_range_high": None,
                "current_price": None,
                "margin_of_safety_pct": None,
                "rules_triggered": [rule.rule_id for rule in research.rules_triggered],
                "rules_failed": [rule.rule_id for rule in research.rules_failed],
                "warnings": [*quality.data_quality_issues, *factor_pack.warnings],
                "classification_notes": f"{research.classification_notes}. Data quality: {quality.overall_tier}.",
                "feature_versions": {
                    "classification": research.rule_version,
                    "data_quality": quality.assessment_version,
                    "factors": factor_pack.factor_version,
                    "report_machine": "V2_CONTINUOUS_MACHINE",
                },
            },
        )

        report = _latest_company_report(session, company.id)
        if report is None:
            report = CompanyReport(company_id=company.id, ticker=ticker, company_name=company.name, as_of_date=date.today().isoformat(), stance=stance)
            session.add(report)
        current_price = _resolved_current_price(ticker, fallback=_safe_float(report.current_price))
        market_cap = (current_price * diluted_shares) if current_price is not None and diluted_shares is not None else None
        route = route_company(
            gics_sector=gics_sector,
            sic_description=company.sic_description,
            revenue=revenue,
            owner_earnings=owner_earnings,
            net_income=net_income,
        )
        report.ticker = ticker
        report.company_name = company.name
        report.as_of_date = date.today().isoformat()
        report.stance = stance
        report.bullish_score = bullish_score
        report.bearish_score = bearish_score
        report.composite_score = composite_score
        report.data_quality_tier = quality.overall_tier
        report.pipeline_stage = _pipeline_stage(raw_facts_count, canonical_count)
        report.latest_filing_date = latest_filing.isoformat() if latest_filing else None
        report.current_price = current_price
        report.key_stats = {
            "filings_count": filings_count,
            "raw_facts_count": raw_facts_count,
            "canonical_facts_count": canonical_count,
            "revenue": _maybe_round(revenue),
            "revenue_growth_pct": _maybe_round(revenue_growth_pct),
            "net_income": _maybe_round(net_income),
            "assets": _maybe_round(assets),
            "liabilities": _maybe_round(liabilities),
            "equity": _maybe_round(equity),
            "owner_earnings": _maybe_round(owner_earnings),
            "owner_earnings_margin_pct": _maybe_round(owner_earnings_margin_pct),
            "margin_pct": _maybe_round(net_margin_pct),
            "gross_margin_pct": _maybe_round(gross_margin_pct),
            "weighted_avg_diluted_shares": _maybe_round(diluted_shares),
            "dilution_growth_pct": _maybe_round(dilution_growth_pct),
            "factor_period_label": factor_pack.period_label,
            "factor_prior_period_label": factor_pack.prior_period_label,
            "beneish_m_score": _maybe_round(factor_pack.beneish_m_score),
            "piotroski_f_score": factor_pack.piotroski_f_score,
            "altman_z_score": _maybe_round(factor_pack.altman_z_score),
            "sloan_accrual_ratio": _maybe_round(factor_pack.sloan_accrual_ratio),
            "cash_based_operating_profitability": _maybe_round(factor_pack.cash_based_operating_profitability),
            "gross_profitability": _maybe_round(factor_pack.gross_profitability),
            "net_operating_assets_ratio": _maybe_round(factor_pack.net_operating_assets_ratio),
            "asset_growth_pct": _maybe_round(factor_pack.asset_growth_pct),
            "external_financing_ratio": _maybe_round(factor_pack.external_financing_ratio),
            "factor_quality_score": _maybe_round(factor_pack.factor_quality_score),
            "factor_forensic_risk_score": _maybe_round(factor_pack.factor_forensic_risk_score),
            "a_his_score": _maybe_round(factor_pack.a_his_score),
            "a_his_breakdown": factor_pack.a_his_breakdown,
            "factor_warning_count": len(factor_pack.warnings),
            "eps": _maybe_round(eps),
            "eps_forecast": _maybe_round(eps_forecast),
            "revenue_forecast_next_quarter_pct": _maybe_round(revenue_forecast_next_quarter_pct),
            "revenue_forecast_next_year_pct": _maybe_round(revenue_forecast_next_year_pct),
            "margin_forecast_pct": _maybe_round(margin_forecast_pct),
            "owner_earnings_forecast": _maybe_round(owner_earnings_forecast),
            "forecast_confidence_pct": _maybe_round(forecast_confidence_pct),
            "surprise_score": _maybe_round(surprise_score),
            "surprise_upside_pct": _maybe_round(surprise_upside_pct),
            "designation_profile": designation_profile,
            "scenario_bear_value": _maybe_round(scenario_valuations["bear"]),
            "scenario_base_value": _maybe_round(scenario_valuations["base"]),
            "scenario_bull_value": _maybe_round(scenario_valuations["bull"]),
            "overall_coverage_pct": _maybe_round(quality.overall_coverage_pct),
            "accounting_quality_score": accounting_quality_score,
            "future_bucket": future_bucket,
            "future_reason": future_reason,
            "gics_sector": gics_sector,
            "gics_industry": gics_industry,
            "route_family": route.family,
            "route_reason": route.reason,
            "lane1_supported": route.lane1_supported,
        }
        report.highlights = highlights
        report.report_markdown = report_markdown
        report.source_versions = {
            "report_machine": "V2_CONTINUOUS_MACHINE",
            "classification": research.rule_version,
            "data_quality": quality.assessment_version,
            "factors": factor_pack.factor_version,
            "accounting_ledger_overlay": "A_HIS_LEDGER_V1",
        }
        standardized_financials = {
            "revenue": _maybe_round(revenue),
            "cogs": _maybe_round(cogs),
            "gross_profit": _maybe_round(gross_profit),
            "sga": _maybe_round(_latest_fact_from_concepts(facts, ["SellingGeneralAndAdministrativeExpense"])),
            "r_and_d": _maybe_round(_latest_fact_from_concepts(facts, ["ResearchAndDevelopmentExpense"])),
            "operating_income": _maybe_round(_latest_fact_from_concepts(facts, ["OperatingIncomeLoss"])),
            "ebit": _maybe_round(_latest_fact_from_concepts(facts, ["OperatingIncomeLoss", "IncomeBeforeTaxExpenseBenefit"])),
            "ebitda_derived": _maybe_round(_derived_ebitda(facts)),
            "interest_expense": _maybe_round(_latest_fact_from_concepts(facts, ["InterestExpenseAndDebtExpense", "InterestExpense"])),
            "pretax_income": _maybe_round(_latest_fact_from_concepts(facts, ["IncomeBeforeTaxExpenseBenefit"])),
            "tax_expense": _maybe_round(_latest_fact_from_concepts(facts, ["IncomeTaxExpenseBenefit"])),
            "net_income": _maybe_round(net_income),
            "diluted_eps": _maybe_round(eps),
            "diluted_shares": _maybe_round(diluted_shares),
            "cash_and_equiv": _maybe_round(_latest_fact_from_concepts(facts, ["CashAndCashEquivalentsAtCarryingValue"])),
            "st_investments": _maybe_round(_latest_fact_from_concepts(facts, ["ShortTermInvestments"])),
            "ar_gross": _maybe_round(_latest_fact_from_concepts(facts, ["AccountsReceivableGrossCurrent"])),
            "ar_allowance": _maybe_round(_latest_fact_from_concepts(facts, ["AllowanceForDoubtfulAccountsReceivableCurrent"])),
            "ar_net": _maybe_round(_latest_fact_from_concepts(facts, ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"])),
            "inventory": _maybe_round(_latest_fact_from_concepts(facts, ["InventoryNet"])),
            "total_current_assets": _maybe_round(_latest_fact_from_concepts(facts, ["AssetsCurrent"])),
            "ppe_net": _maybe_round(_latest_fact_from_concepts(facts, ["PropertyPlantAndEquipmentNet"])),
            "goodwill": _maybe_round(_latest_fact_from_concepts(facts, ["Goodwill"])),
            "intangibles_net": _maybe_round(_latest_fact_from_concepts(facts, ["FiniteLivedIntangibleAssetsNet", "IntangibleAssetsNetExcludingGoodwill"])),
            "total_assets": _maybe_round(assets),
            "ap": _maybe_round(_latest_fact_from_concepts(facts, ["AccountsPayableCurrent"])),
            "accrued_liab": _maybe_round(_latest_fact_from_concepts(facts, ["AccruedLiabilitiesCurrent"])),
            "deferred_rev_current": _maybe_round(_latest_fact_from_concepts(facts, ["DeferredRevenueCurrent", "ContractWithCustomerLiabilityCurrent"])),
            "deferred_rev_noncurrent": _maybe_round(_latest_fact_from_concepts(facts, ["DeferredRevenueNoncurrent", "ContractWithCustomerLiabilityNoncurrent"])),
            "contract_assets_unbilled": _maybe_round(_latest_fact_from_concepts(facts, ["ContractWithCustomerAssetNet"])),
            "st_debt": _maybe_round(_latest_fact_from_concepts(facts, ["ShortTermBorrowings", "LongTermDebtCurrent"])),
            "current_portion_ltd": _maybe_round(_latest_fact_from_concepts(facts, ["LongTermDebtCurrent"])),
            "total_current_liab": _maybe_round(_latest_fact_from_concepts(facts, ["LiabilitiesCurrent"])),
            "lt_debt": _maybe_round(_latest_fact_from_concepts(facts, ["LongTermDebtNoncurrent", "LongTermDebt"])),
            "operating_lease_liab": _maybe_round(_latest_fact_from_concepts(facts, ["OperatingLeaseLiabilityNoncurrent"])),
            "total_liabilities": _maybe_round(liabilities),
            "retained_earnings": _maybe_round(_latest_fact_from_concepts(facts, ["RetainedEarningsAccumulatedDeficit"])),
            "total_equity": _maybe_round(equity),
            "cfo": _maybe_round(ocf),
            "capex": _maybe_round(capex),
            "capitalized_software": _maybe_round(_latest_fact_from_concepts(facts, ["CapitalizedComputerSoftwareGross"])),
            "capitalized_contract_costs": _maybe_round(_latest_fact_from_concepts(facts, ["CapitalizedContractCostNet"])),
            "stock_based_comp": _maybe_round(_latest_fact_from_concepts(facts, ["ShareBasedCompensation"])),
            "cfi": _maybe_round(_latest_fact_from_concepts(facts, ["NetCashProvidedByUsedInInvestingActivities"])),
            "cff": _maybe_round(_latest_fact_from_concepts(facts, ["NetCashProvidedByUsedInFinancingActivities"])),
            "dividends_paid": _maybe_round(_latest_fact_from_concepts(facts, ["PaymentsOfDividends"])),
            "buybacks": _maybe_round(_latest_fact_from_concepts(facts, ["PaymentsForRepurchaseOfCommonStock"])),
            "fcf_derived": _maybe_round(owner_earnings),
            "rpo_disclosed": _maybe_round(_latest_fact_from_concepts(facts, ["RemainingPerformanceObligation"])),
        }
        receivables_series = _series(
            facts,
            ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
            period="instant",
        )
        deferred_revenue_series = _series(
            facts,
            ["DeferredRevenueCurrent", "ContractWithCustomerLiabilityCurrent"],
            period="instant",
        )
        inventory_series = _series(facts, ["InventoryNet"], period="instant")
        cogs_quarterly_series = _series(
            facts,
            ["CostOfGoodsSold", "CostOfRevenue", "CostOfGoodsAndServicesSold"],
            period="quarterly",
        )
        cogs_annual_series = _series(
            facts,
            ["CostOfGoodsSold", "CostOfRevenue", "CostOfGoodsAndServicesSold"],
            period="annual",
        )
        sga_quarterly_series = _series(facts, ["SellingGeneralAndAdministrativeExpense"], period="quarterly")
        sga_annual_series = _series(facts, ["SellingGeneralAndAdministrativeExpense"], period="annual")
        tax_expense_annual_series = _series(facts, ["IncomeTaxExpenseBenefit"], period="annual")
        pretax_income_annual_series = _series(facts, ["IncomeBeforeTaxExpenseBenefit"], period="annual")
        current_receivables = _first_value(receivables_series)
        prior_receivables = _comparable_prior_value(receivables_series)
        current_deferred_revenue = _first_value(deferred_revenue_series)
        prior_deferred_revenue = _comparable_prior_value(deferred_revenue_series)
        current_inventory = _first_value(inventory_series)
        prior_inventory = _comparable_prior_value(inventory_series)
        current_cogs = _first_value(cogs_quarterly_series) or _first_value(cogs_annual_series)
        prior_cogs = _comparable_prior_value(cogs_quarterly_series) or _comparable_prior_value(cogs_annual_series)
        current_sga = _first_value(sga_quarterly_series) or _first_value(sga_annual_series)
        prior_sga = _comparable_prior_value(sga_quarterly_series) or _comparable_prior_value(sga_annual_series)
        prior_capex = _comparable_prior_value(capex_quarterly_series) or _comparable_prior_value(capex_annual_series)
        current_dso = _safe_divide(current_receivables * 365 if current_receivables is not None else None, revenue)
        prior_dso = _safe_divide(prior_receivables * 365 if prior_receivables is not None else None, prior_revenue)
        growth_trend_deltas = {
            "revenue_yoy_growth": _maybe_round(revenue_growth_pct),
            "receivables_yoy_growth": _maybe_round(_pct_change(current_receivables, prior_receivables)),
            "dso": _maybe_round(current_dso),
            "dso_delta_yoy": _maybe_round(_pct_change(current_dso, prior_dso)),
            "inventory_yoy_growth": _maybe_round(_pct_change(current_inventory, prior_inventory)),
            "cogs_yoy_growth": _maybe_round(_pct_change(current_cogs, prior_cogs)),
            "deferred_rev_yoy_growth": _maybe_round(_pct_change(current_deferred_revenue, prior_deferred_revenue)),
            "sga_pct_revenue": _maybe_round(_ratio_pct(
                current_sga,
                revenue,
                ceiling=1000.0,
            )),
            "sga_pct_revenue_delta": _maybe_round(_pct_change(
                _safe_divide(current_sga, revenue),
                _safe_divide(prior_sga, prior_revenue),
            )),
            "capex_intensity_pct_rev": _maybe_round(_ratio_pct(abs(capex) if capex is not None else None, revenue, ceiling=1000.0)),
            "capex_intensity_delta": _maybe_round(_pct_change(
                _safe_divide(abs(capex) if capex is not None else None, revenue),
                _safe_divide(abs(prior_capex) if prior_capex is not None else None, prior_revenue),
            )),
            "gross_margin": _maybe_round(gross_margin_pct),
            "buyback_yield": _maybe_round(_ratio_pct(
                _latest_fact_from_concepts(facts, ["PaymentsForRepurchaseOfCommonStock"]),
                assets,
                ceiling=1000.0,
            )),
            "diluted_shares_yoy_change": _maybe_round(dilution_growth_pct),
            "effective_tax_rate": _maybe_round(_ratio_pct(
                _latest_fact_from_concepts(facts, ["IncomeTaxExpenseBenefit"]),
                _latest_fact_from_concepts(facts, ["IncomeBeforeTaxExpenseBenefit"]),
                ceiling=200.0,
            )),
            "effective_tax_rate_3yr_avg": _maybe_round(_rolling_average([
                _safe_divide(_nth_value(tax_expense_annual_series, index), _nth_value(pretax_income_annual_series, index))
                for index in range(min(3, len(tax_expense_annual_series), len(pretax_income_annual_series)))
            ], multiplier=100.0)),
            "cash_tax_vs_book_tax_gap": _maybe_round(_ratio_pct(
                _latest_fact_from_concepts(facts, ["IncomeTaxesPaidNet"]),
                _latest_fact_from_concepts(facts, ["IncomeTaxExpenseBenefit"]),
                ceiling=500.0,
            )),
        }
        accrual_cash_quality = {
            "total_accruals_cf_method": _maybe_round((net_income - ocf) if net_income is not None and ocf is not None else None),
            "cash_conversion_ratio": _maybe_round(_safe_divide(ocf, net_income)),
            "fcf_ni_ratio": _maybe_round(_safe_divide(owner_earnings, net_income)),
            "net_operating_assets_pct_assets": _maybe_round(factor_pack.net_operating_assets_ratio),
            "cash_based_operating_profitability": _maybe_round(factor_pack.cash_based_operating_profitability),
            "sbc_pct_revenue": _maybe_round(_ratio_pct(
                _latest_fact_from_concepts(facts, ["ShareBasedCompensation"]),
                revenue,
                ceiling=1000.0,
            )),
            "discretionary_accruals_est": None,
            "sloan_accrual_ratio": _maybe_round(factor_pack.sloan_accrual_ratio),
        }
        forensic_scores = {
            "beneish_m_score": _maybe_round(factor_pack.beneish_m_score),
            "piotroski_f_score": factor_pack.piotroski_f_score,
            "altman_z_double_prime": _maybe_round(factor_pack.altman_z_score),
            "dechow_f_score": None,
            "montier_c_score": None,
            "ohlson_o_score": None,
            "factor_forensic_risk_score": _maybe_round(factor_pack.factor_forensic_risk_score),
        }
        positive_quality = {
            "sector_percentile_rank": None,
            "positive_quality_score": _maybe_round(factor_pack.factor_quality_score),
            "profitability_persistence_subscore": _maybe_round(factor_pack.gross_profitability * 100 if factor_pack.gross_profitability is not None else None),
            "capital_allocation_subscore": _maybe_round(balance_score),
            "margin_trajectory_subscore": _maybe_round(margin_forecast_pct),
            "balance_sheet_strength_subscore": _maybe_round(balance_score),
            "red_flag_penalty": _maybe_round(forensic_risk_score),
            "a_his_score": _maybe_round(factor_pack.a_his_score),
            "a_his_breakdown": factor_pack.a_his_breakdown,
            "composite_locked_asof": latest_filing.isoformat() if latest_filing else date.today().isoformat(),
        }
        section_payloads = {
            "standardized_financials": standardized_financials,
            "growth_trend_deltas": growth_trend_deltas,
            "accrual_cash_quality": accrual_cash_quality,
            "forensic_scores": forensic_scores,
            "positive_quality": positive_quality,
            "event_red_flags": {
                "auditor_name": event_signal_bundle.auditor_name,
                "auditor_tenure_years": event_signal_bundle.auditor_tenure_years,
                "auditor_changed_flag": event_signal_bundle.auditor_changed_flag,
                "auditor_change_date": event_signal_bundle.auditor_change_date,
                "going_concern_flag": False,
                "material_weakness_flag": False,
                "restatement_severity": "little-r" if latest_filing_row and latest_filing_row.is_amendment else "none",
                "late_filer_flag": False,
                "sec_comment_letter_flag": event_signal_bundle.sec_comment_letter_flag,
                "cfo_turnover_flag": event_signal_bundle.cfo_turnover_flag,
                "cfo_turnover_date": event_signal_bundle.cfo_turnover_date,
                "ceo_turnover_flag": event_signal_bundle.ceo_turnover_flag,
                "ceo_turnover_date": event_signal_bundle.ceo_turnover_date,
            },
            "textual_signals": {
                "yoy_filing_similarity_score": textual_signal_bundle.yoy_filing_similarity_score,
                "risk_factor_similarity_score": textual_signal_bundle.risk_factor_similarity_score,
                "mgmt_tone_score": textual_signal_bundle.mgmt_tone_score,
                "reverse_factoring_disclosed": textual_signal_bundle.reverse_factoring_disclosed,
                "pension_discount_rate": textual_signal_bundle.pension_discount_rate,
                "pension_expected_return": textual_signal_bundle.pension_expected_return,
                "related_party_revenue_pct": textual_signal_bundle.related_party_revenue_pct,
                "llm_summary": textual_signal_bundle.summary,
                "llm_model_version": None,
                "llm_confidence": None,
            },
            "non_gaap_forensics": {
                "gaap_eps": _maybe_round(eps),
                "non_gaap_eps": _maybe_round(non_gaap_signal_bundle.non_gaap_eps),
                "non_gaap_gap_pct": _maybe_round(non_gaap_signal_bundle.non_gaap_gap_pct),
                "non_gaap_gap_3yr_trend": _maybe_round(non_gaap_signal_bundle.non_gaap_gap_3yr_trend),
                "recurring_nonrecurring_flag": non_gaap_signal_bundle.recurring_nonrecurring_flag,
            },
            "governance_ownership": {
                "insider_buy_cluster_flag": governance_signal_bundle.insider_buy_cluster_flag,
                "insider_net_shares_bought_90d": _maybe_round(governance_signal_bundle.insider_net_shares_bought_90d),
                "institutional_ownership_pct": governance_signal_bundle.institutional_ownership_pct,
                "institutional_ownership_qoq_delta": governance_signal_bundle.institutional_ownership_qoq_delta,
                "short_interest_pct_float": governance_signal_bundle.short_interest_pct_float,
                "short_interest_delta": governance_signal_bundle.short_interest_delta,
                "dual_class_flag": governance_signal_bundle.dual_class_flag,
                "audit_fee_ratio": _maybe_round(governance_signal_bundle.audit_fee_ratio),
            },
            "market_data_linkage": {
                "price_asof": current_price,
                "market_cap": _maybe_round(market_cap),
                "ev": None,
                "adv_20d": None,
                "ev_ebitda": None,
                "p_fcf": _maybe_round(_safe_divide(current_price, owner_earnings / diluted_shares) if current_price is not None and owner_earnings is not None and diluted_shares not in (None, 0) else None),
            },
            "universe_tradability": {
                "in_sp500": membership.in_sp500,
                "in_russell2000": membership.in_russell2000,
                "in_nasdaq_comp": membership.in_nasdaq_comp,
                "passes_liquidity_filter": _passes_liquidity_filter(current_price=current_price, market_cap=market_cap),
                "passes_mcap_floor": bool(market_cap is not None and market_cap >= 1_000_000_000),
                "excluded_financial_reit": gics_sector in {"Financials", "Real Estate"},
                "excluded_biotech_prerevenue": _excluded_biotech_prerevenue(
                    sector=gics_sector,
                    revenue=revenue,
                    net_income=net_income,
                ),
                "excluded_recent_ipo": years_of_history < 2,
            },
        }
        grading = ReportCardGradingEngine.grade(
            GradingInputs(
                cash_oper_profitability_pctile=_percentile_proxy(
                    factor_pack.cash_based_operating_profitability,
                    scale=180.0,
                    baseline=50.0,
                ) if factor_pack.cash_based_operating_profitability is not None else None,
                capital_allocation_pctile=balance_score,
                margin_trajectory_pctile=_clamp(margin_forecast_pct + 50.0, 0.0, 100.0) if margin_forecast_pct is not None else None,
                balance_sheet_strength_pctile=balance_score,
                accrual_quality_pctile=_percentile_proxy(
                    -(factor_pack.sloan_accrual_ratio or 0.0),
                    scale=350.0,
                    baseline=60.0,
                ) if factor_pack.sloan_accrual_ratio is not None else None,
                beneish_severity=_beneish_severity(factor_pack.beneish_m_score),
                dechow_severity=None,
                altman_distress_severity=_altman_severity(factor_pack.altman_z_score),
                event_flag_severity=95.0 if latest_filing_row and latest_filing_row.is_amendment else 0.0,
                forecasted_next_q_pqc=_forecasted_next_q_pqc(
                    current_pqc=factor_pack.factor_quality_score,
                    revenue_forecast_next_year_pct=revenue_forecast_next_year_pct,
                    confidence_pct=forecast_confidence_pct,
                ),
                current_pqc=factor_pack.factor_quality_score,
                data_completeness_pct=quality.overall_coverage_pct,
                forensic_score_dispersion=_forensic_dispersion(
                    factor_pack.beneish_m_score,
                    factor_pack.altman_z_score,
                    factor_pack.factor_forensic_risk_score,
                ),
                recency_factor=1.0,
                required_sections=len(section_payloads),
                populated_sections=_populated_sections(section_payloads),
                sustained_beneish_breach=bool(factor_pack.beneish_m_score is not None and factor_pack.beneish_m_score > -1.78),
                going_concern_flag=False,
                big_r_restatement_flag=False,
                unscheduled_auditor_change_flag=event_signal_bundle.auditor_changed_flag,
                base_unit=1.0,
                sector_cap_remaining=1.0,
                sector_target=1.0,
            )
        )
        positive_quality["sector_percentile_rank"] = _maybe_round(grading.pqc)
        positive_quality["positive_quality_score"] = _maybe_round(grading.grade_score)
        positive_quality["red_flag_penalty"] = _maybe_round(grading.red_flag_penalty)
        event_red_flags = section_payloads["event_red_flags"]
        textual_signals = section_payloads["textual_signals"]
        non_gaap_forensics = section_payloads["non_gaap_forensics"]
        governance_ownership = section_payloads["governance_ownership"]
        market_data_linkage = section_payloads["market_data_linkage"]
        universe_tradability = section_payloads["universe_tradability"]
        final_verdict = {
            "schema_version": "report_card_v2",
            "pipeline_run_id": f"{company.cik}:{latest_filing_row.accession_number}" if latest_filing_row else company.cik,
            "current_action": grading.action,
            "route_family": route.family,
            "route_reason": route.reason,
            "lane1_supported": route.lane1_supported,
            "veto_triggered": bool(grading.veto_triggered or research.classification == "REJECTED_BY_RULES"),
            "veto_reason": grading.veto_reason or ("classification rejected by rules" if research.classification == "REJECTED_BY_RULES" else None),
            "last_scored_ts": datetime.now(UTC).isoformat(),
            "next_expected_filing_date": _next_expected_filing_date(latest_filing_row),
            "stance": stance,
            "composite_score": _maybe_round(composite_score),
            "grade": grading.grade,
            "grade_score": _maybe_round(grading.grade_score),
            "confidence": round(grading.confidence, 4),
            "position_size": round(grading.position_size, 4),
            "pqc": _maybe_round(grading.pqc),
            "forecast_adjustment": _maybe_round(grading.forecast_adjustment),
            "data_completeness_pct": _maybe_round(quality.overall_coverage_pct),
            "score_lineage": {
                "canonical_score_name": "positive_quality_score",
                "canonical_score_value": _maybe_round(grading.grade_score),
                "intermediate_scores": {
                    "factor_quality_score": _maybe_round(factor_pack.factor_quality_score),
                    "a_his_score": _maybe_round(factor_pack.a_his_score),
                    "legacy_composite_score": _maybe_round(composite_score),
                    "pqc": _maybe_round(grading.pqc),
                },
                "accounting_ledger_overlay": factor_pack.a_his_breakdown,
                "pqc_inputs": {
                    "profitability_persistence": _maybe_round(_percentile_proxy(factor_pack.cash_based_operating_profitability or 0.0, scale=180.0, baseline=50.0)),
                    "capital_allocation": _maybe_round(balance_score),
                    "margin_trajectory": _maybe_round(_clamp((margin_forecast_pct or 0.0) + 50.0, 0.0, 100.0)),
                    "balance_sheet_strength": _maybe_round(balance_score),
                    "accrual_quality": _maybe_round(_percentile_proxy(-(factor_pack.sloan_accrual_ratio or 0.0), scale=350.0, baseline=60.0)),
                },
                "pqc_weights": {
                    "profitability_persistence": 0.35,
                    "capital_allocation": 0.20,
                    "margin_trajectory": 0.15,
                    "balance_sheet_strength": 0.15,
                    "accrual_quality": 0.15,
                },
                "red_flag_penalty_source": {
                    "beneish_severity": _maybe_round(_beneish_severity(factor_pack.beneish_m_score)),
                    "altman_severity": _maybe_round(_altman_severity(factor_pack.altman_z_score)),
                    "event_flag_severity": 95.0 if latest_filing_row and latest_filing_row.is_amendment else 0.0,
                    "applied_penalty": _maybe_round(grading.red_flag_penalty),
                },
                "forecast_adjustment_source": {
                    "current_pqc": _maybe_round(factor_pack.factor_quality_score),
                    "forecasted_next_q_pqc": _maybe_round(_forecasted_next_q_pqc(
                        current_pqc=factor_pack.factor_quality_score,
                        revenue_forecast_next_year_pct=revenue_forecast_next_year_pct,
                        confidence_pct=forecast_confidence_pct,
                    )),
                    "applied_adjustment": _maybe_round(grading.forecast_adjustment),
                },
                "confidence_inputs": {
                    "data_completeness_pct": _maybe_round(quality.overall_coverage_pct),
                    "required_sections": len(section_payloads),
                    "populated_sections": _populated_sections(section_payloads),
                    "forensic_score_dispersion": _maybe_round(_forensic_dispersion(
                        factor_pack.beneish_m_score,
                        factor_pack.altman_z_score,
                        factor_pack.factor_forensic_risk_score,
                    ) * 100),
                    "recency_factor": 1.0,
                },
            },
        }
        # Persist the exact research valuation alongside this immutable filing card.
        # Historical cards created before this version intentionally remain unfilled.
        cc_valuation = _estimate_cc_valuation(session, report)
        final_verdict["valuation_snapshot"] = {
            "model_version": "CC_EARNINGS_POWER_V1",
            "cc_valuation": _maybe_round(cc_valuation),
            "market_price": _maybe_round(_safe_float(market_data_linkage.get("price_asof"))),
            "captured_at": datetime.now(UTC).isoformat(),
            "status": "captured" if cc_valuation is not None else "unavailable_missing_earnings_or_share_data",
        }
        final_verdict["valuation_range"] = build_valuation_range(
            scenario_values=scenario_valuations,
            cc_valuation=cc_valuation,
            confidence_pct=forecast_confidence_pct,
        )
        final_verdict["research_controls"] = build_research_controls(
            data_completeness_pct=quality.overall_coverage_pct,
            canonical_facts_count=canonical_count,
            route_family=route.family,
            lane1_supported=route.lane1_supported,
            veto_triggered=bool(grading.veto_triggered or research.classification == "REJECTED_BY_RULES"),
            grade_score=grading.grade_score,
            valuation_available=cc_valuation is not None,
        )
        session.flush()
        persist_report_card(
            session,
            company=company,
            ticker=ticker,
            report=report,
            latest_filing=latest_filing_row,
            factor_pack=factor_pack,
            standardized_financials=standardized_financials,
            growth_trend_deltas=growth_trend_deltas,
            accrual_cash_quality=accrual_cash_quality,
            forensic_scores=forensic_scores,
            positive_quality=positive_quality,
            event_red_flags=event_red_flags,
            textual_signals=textual_signals,
            non_gaap_forensics=non_gaap_forensics,
            governance_ownership=governance_ownership,
            market_data_linkage=market_data_linkage,
            universe_tradability=universe_tradability,
            final_verdict=final_verdict,
            gics_sector=gics_sector,
            gics_industry=gics_industry,
        )
        session.flush()
        sync_buy_board_candidate(session, report)
        upsert_company_bottleneck_snapshot(session, company=company, report=report)
        session.flush()


def _count(session: Session, model: Any, company_id: Any) -> int:
    return int(session.execute(select(func.count()).select_from(model).where(model.company_id == company_id)).scalar_one())


def _latest_company_report(session: Session, company_id: Any) -> CompanyReport | None:
    return session.execute(
        select(CompanyReport)
        .where(CompanyReport.company_id == company_id)
        .order_by(CompanyReport.updated_at.desc(), CompanyReport.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _latest_report_card_filing(filings: list[Filing]) -> Filing | None:
    """Select the newest filing allowed to anchor an accounting report card."""
    return next(
        (filing for filing in filings if (filing.form_type or "").upper() in _REPORT_CARD_FILING_TYPES),
        None,
    )


def _series(
    facts: list[RawFact],
    concepts: list[str],
    *,
    period: str = "any",
) -> list[tuple[date | None, float]]:
    concept_set = set(concepts)
    best_by_period_end: dict[date | None, tuple[datetime, datetime, datetime, float]] = {}
    for fact in facts:
        if fact.concept not in concept_set or fact.value_numeric is None:
            continue
        if not _matches_period_kind(fact, period=period):
            continue
        period_end = fact.period_end or fact.instant_date
        filed_at = (
            datetime.combine(fact.filed_date, datetime.min.time(), tzinfo=UTC)
            if fact.filed_date is not None
            else datetime.min.replace(tzinfo=UTC)
        )
        candidate = (
            fact.accepted_at or filed_at,
            filed_at,
            fact.created_at or datetime.min.replace(tzinfo=UTC),
            float(Decimal(fact.value_numeric)),
        )
        existing = best_by_period_end.get(period_end)
        if existing is None or candidate[:3] > existing[:3]:
            best_by_period_end[period_end] = candidate
    ordered_periods = sorted(best_by_period_end.keys(), reverse=True)
    return [(period_end, best_by_period_end[period_end][3]) for period_end in ordered_periods]


def _first_value(series: list[tuple[date | None, float]]) -> float | None:
    return series[0][1] if series else None


def _nth_value(series: list[tuple[date | None, float]], index: int) -> float | None:
    return series[index][1] if len(series) > index else None


def _comparable_prior_index(
    series: list[tuple[date | None, float]],
    *,
    min_days: int = 300,
    max_days: int = 430,
) -> int | None:
    if not series or series[0][0] is None:
        return None
    current_period_end = series[0][0]
    for index, (period_end, _value) in enumerate(series[1:], start=1):
        if period_end is None:
            continue
        delta_days = (current_period_end - period_end).days
        if min_days <= delta_days <= max_days:
            return index
    return None


def _comparable_prior_value(series: list[tuple[date | None, float]]) -> float | None:
    comparable_index = _comparable_prior_index(series)
    if comparable_index is None:
        return None
    return _nth_value(series, comparable_index)


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / abs(previous)) * 100


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _maybe_round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _latest_fact_from_concepts(
    facts: list[RawFact],
    concepts: list[str],
    period: str = "any",
) -> float | None:
    series = _series(facts, concepts, period=period)
    if series:
        return series[0][1]
    return None


def _matches_period_kind(fact: RawFact, *, period: str) -> bool:
    if period == "any":
        return True
    duration_days = _fact_duration_days(fact)
    if period == "instant":
        return duration_days == 0
    if duration_days is None:
        return False
    if period == "quarterly":
        return 70 <= duration_days <= 110
    if period == "annual":
        return 320 <= duration_days <= 380
    return False


def _fact_duration_days(fact: RawFact) -> int | None:
    if fact.period_start is None and (fact.period_end is not None or fact.instant_date is not None):
        return 0
    if fact.period_start is not None and fact.period_end is not None:
        return (fact.period_end - fact.period_start).days
    return None


def _resolved_current_price(ticker: str, *, fallback: float | None) -> float | None:
    payload = alpaca_quote(ticker)
    if payload.get("ok"):
        quote = payload.get("quote")
        if isinstance(quote, dict):
            for key in ("last", "close", "bid", "ask"):
                price = _safe_float(quote.get(key))
                if price is not None and price > 0:
                    return price
    return fallback


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _backlog_reason(*, report_id: Any, pipeline_stage: str | None) -> str | None:
    if report_id is None:
        return "missing_report"
    if pipeline_stage == "parked":
        return None
    if pipeline_stage != "reports-ready":
        return f"pipeline_{pipeline_stage or 'unknown'}"
    return None


def _is_runnable_backlog_reason(reason: str) -> bool:
    return reason in {
        "missing_report",
        "pipeline_filings-only",
        "pipeline_facts-ingested",
        "pipeline_seeded",
        "pipeline_unknown",
    }


def _upsert_research_record(session: Session, *, company_id: Any, payload: dict[str, Any]) -> None:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        stmt = pg_insert(ResearchRecord).values(**payload)
        update_columns = {
            key: value
            for key, value in payload.items()
            if key not in {"company_id", "as_of_date"}
        }
        stmt = stmt.on_conflict_do_update(
            constraint="uq_research_records_company_date",
            set_=update_columns,
        )
        session.execute(stmt)
        return

    record = session.execute(
        select(ResearchRecord).where(
            ResearchRecord.company_id == company_id,
            ResearchRecord.as_of_date == payload["as_of_date"],
        )
    ).scalar_one_or_none()
    if record is None:
        record = ResearchRecord(company_id=company_id, as_of_date=payload["as_of_date"], classification="")
        session.add(record)
    for key, value in payload.items():
        setattr(record, key, value)


def _filter_priority_rows(rows: list[tuple[Any, str, str | None, str | None, str | None]], *, limit: int) -> list[tuple[Any, str]]:
    selected: list[tuple[Any, str]] = []
    fallback: list[tuple[Any, str]] = []
    chosen_by_company: dict[Any, tuple[bool, int, str]] = {}
    for company_id, ticker, company_name, entity_type, security_type in rows:
        is_priority = _is_priority_operating_equity(
            ticker=ticker,
            company_name=company_name,
            entity_type=entity_type,
            security_type=security_type,
        )
        rank = _security_rank(ticker)
        existing = chosen_by_company.get(company_id)
        candidate = (is_priority, rank, ticker)
        if existing is None or candidate > existing:
            chosen_by_company[company_id] = candidate
    for company_id, (is_priority, _rank, ticker) in chosen_by_company.items():
        (selected if is_priority else fallback).append((company_id, ticker))
    if selected:
        return selected[:limit]
    return fallback[:limit]


def _worker_role_specs(worker_count: int) -> list[dict[str, Any]]:
    count = max(1, worker_count)
    specs: list[dict[str, Any]] = []
    for index in range(count):
        if index < len(_BASE_WORKER_ROLES):
            base = dict(_BASE_WORKER_ROLES[index])
        else:
            overflow_index = index - len(_BASE_WORKER_ROLES) + 1
            base = {
                "role": f"reports-overflow-{overflow_index}",
                "label": f"REPORTS X{overflow_index}",
                "primary_lane": "report-build",
                "fallback_lanes": ["report-refresh", "strategy"],
            }
        base["worker_id"] = index + 1
        specs.append(base)
    return specs


def _lane_sort_key(lane: str, row: dict[str, Any]) -> tuple[Any, ...]:
    filings_count = int(row.get("filings_count") or 0)
    raw_facts_count = int(row.get("raw_facts_count") or 0)
    canonical_count = int(row.get("canonical_count") or 0)
    statement_count = int(row.get("statement_count") or 0)
    report_missing = 0 if row.get("report_id") is None else 1
    report_stage = str(row.get("pipeline_stage") or "")
    report_updated_at = row.get("report_updated_at")
    updated_rank = report_updated_at or datetime(1970, 1, 1, tzinfo=UTC)
    ticker = str(row.get("ticker") or "")

    if lane == "filings":
        return (0 if filings_count == 0 else 1, report_missing, updated_rank, ticker)
    if lane == "companyfacts":
        return (0 if raw_facts_count == 0 else 1, updated_rank, ticker)
    if lane == "canonical":
        return (0 if canonical_count == 0 else 1, updated_rank, ticker)
    if lane == "statements":
        return (0 if statement_count == 0 else 1, updated_rank, ticker)
    if lane == "report-build":
        return (report_missing, 0 if report_stage != "reports-ready" else 1, updated_rank, ticker)
    if lane == "report-refresh":
        return (updated_rank, ticker)
    if lane == "strategy":
        return (updated_rank, ticker)
    return (updated_rank, ticker)


def _is_priority_operating_equity(
    *,
    ticker: str | None,
    company_name: str | None,
    entity_type: str | None,
    security_type: str | None,
) -> bool:
    normalized_ticker = (ticker or "").upper()
    normalized_name = (company_name or "").strip().lower()
    normalized_entity_type = (entity_type or "").strip().lower()
    normalized_security_type = (security_type or "").strip().lower()

    if normalized_security_type and normalized_security_type not in {"common_stock", "common"}:
        return False
    if normalized_entity_type and normalized_entity_type not in {"operating", "other"}:
        return False
    if any(marker in normalized_name for marker in _NON_OPERATING_NAME_MARKERS):
        return False
    if "-P" in normalized_ticker or normalized_ticker.endswith("-WT") or normalized_ticker.endswith("-WS"):
        return False
    return not (len(normalized_ticker) >= 5 and normalized_ticker.endswith(("W", "U", "RT", "R")))


def _security_rank(ticker: str | None) -> int:
    normalized_ticker = (ticker or "").upper()
    rank = 0
    if "-" not in normalized_ticker:
        rank += 20
    if len(normalized_ticker) <= 4:
        rank += 10
    if normalized_ticker.endswith(("WT", "WS", "W", "U", "RT", "R")):
        rank -= 20
    if "-P" in normalized_ticker:
        rank -= 30
    return rank


def _scaled_divide(numerator: float | None, denominator: float | None, *, multiplier: float) -> float | None:
    value = _safe_divide(numerator, denominator)
    if value is None:
        return None
    return value * multiplier


def _ratio_pct(numerator: float | None, denominator: float | None, *, ceiling: float) -> float | None:
    value = _scaled_divide(numerator, denominator, multiplier=100.0)
    if value is None:
        return None
    if abs(value) > ceiling:
        return None
    return value


def _passes_liquidity_filter(*, current_price: float | None, market_cap: float | None) -> bool | None:
    if current_price is None and market_cap is None:
        return None
    if current_price is not None and current_price < 5:
        return False
    return not (market_cap is not None and market_cap < 300_000_000)


def _excluded_biotech_prerevenue(*, sector: str, revenue: float | None, net_income: float | None) -> bool:
    if sector != "Healthcare":
        return False
    if revenue is None or revenue <= 1_000_000:
        return True
    return bool(net_income is not None and net_income < 0 and revenue < 25_000_000)


def _sector_name(sic_description: str | None) -> str:
    text = (sic_description or "").lower()
    if any(token in text for token in ("bank", "finance", "financial", "insurance", "asset management")):
        return "Financials"
    if any(token in text for token in ("reit", "real estate", "property", "realty")):
        return "Real Estate"
    if any(token in text for token in ("software", "computer", "semiconductor", "electronic", "internet")):
        return "Technology"
    if any(token in text for token in ("pharma", "biological", "medical", "health")):
        return "Healthcare"
    if any(token in text for token in ("oil", "gas", "energy", "pipeline")):
        return "Energy"
    if any(token in text for token in ("chemical", "mining", "steel", "paper")):
        return "Materials"
    if any(token in text for token in ("utility", "electric", "water", "telecom")):
        return "Utilities"
    if any(token in text for token in ("retail", "food", "restaurant", "apparel", "consumer")):
        return "Consumer"
    if any(token in text for token in ("media", "broadcast", "publishing", "entertainment")):
        return "Communication Services"
    return "Industrials"


def _current_action(stance: str) -> str:
    if stance == "MOST_BULLISH":
        return "BUY"
    if stance == "BULLISH":
        return "HOLD"
    if stance == "NEUTRAL":
        return "WATCH"
    if stance in {"BEARISH", "MOST_BEARISH"}:
        return "EXIT"
    return "EXCLUDED"


def _percentile_proxy(value: float, *, scale: float, baseline: float) -> float:
    return _clamp(baseline + (value * scale), 0.0, 100.0)


def _beneish_severity(beneish_m_score: float | None) -> float:
    if beneish_m_score is None:
        return 0.0
    if beneish_m_score > -1.78:
        return 95.0
    if beneish_m_score > -2.22:
        return 70.0
    return 20.0


def _altman_severity(altman_z_score: float | None) -> float:
    if altman_z_score is None:
        return 20.0
    if altman_z_score < 1.1:
        return 95.0
    if altman_z_score < 2.6:
        return 65.0
    return 15.0


def _forensic_dispersion(
    beneish_m_score: float | None,
    altman_z_score: float | None,
    factor_forensic_risk_score: float | None,
) -> float:
    severities = [
        _beneish_severity(beneish_m_score) / 100.0,
        _altman_severity(altman_z_score) / 100.0,
    ]
    if factor_forensic_risk_score is not None:
        severities.append(_clamp(factor_forensic_risk_score / 100.0, 0.0, 1.0))
    if len(severities) < 2:
        return 0.0
    spread = max(severities) - min(severities)
    return _clamp(spread, 0.0, 1.0)


def _forecasted_next_q_pqc(
    *,
    current_pqc: float | None,
    revenue_forecast_next_year_pct: float | None,
    confidence_pct: float | None,
) -> float | None:
    if current_pqc is None:
        return None
    growth_kicker = (revenue_forecast_next_year_pct or 0.0) * 0.35
    confidence_kicker = max(0.0, (confidence_pct or 0.0) - 50.0) * 0.12
    return _clamp(current_pqc + growth_kicker + confidence_kicker, 0.0, 100.0)


def _populated_sections(section_payloads: dict[str, dict[str, object]]) -> int:
    return sum(1 for payload in section_payloads.values() if _has_meaningful_payload_value(payload))


def _has_meaningful_payload_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized not in {"", "none", "unknown", "n/a", "null"}
    if isinstance(value, dict):
        return any(_has_meaningful_payload_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_meaningful_payload_value(item) for item in value)
    return True


def _next_expected_filing_date(latest_filing_row: Filing | None) -> str | None:
    if latest_filing_row is None or latest_filing_row.filing_date is None:
        return None
    form_type = (latest_filing_row.form_type or "").upper()
    if "10-K" in form_type:
        expected = latest_filing_row.filing_date + timedelta(days=365)
    elif "10-Q" in form_type:
        expected = latest_filing_row.filing_date + timedelta(days=92)
    else:
        expected = latest_filing_row.filing_date + timedelta(days=180)
    return expected.isoformat()


def _derived_ebitda(facts: list[RawFact]) -> float | None:
    operating_income = _latest_fact_from_concepts(facts, ["OperatingIncomeLoss"])
    depreciation = _latest_fact_from_concepts(
        facts,
        [
            "Depreciation",
            "DepreciationAndAmortization",
            "DepreciationDepletionAndAmortization",
        ],
    )
    if operating_income is None:
        return None
    return operating_income + (depreciation or 0.0)


def _rolling_average(values: list[float | None], *, multiplier: float = 1.0) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present) * multiplier


def _future_bucket(
    *,
    canonical_count: int,
    surprise_score: float | None,
    forecast_confidence_pct: float | None,
    revenue_forecast_next_year_pct: float | None,
) -> tuple[str, str]:
    if (
        canonical_count > 0
        and
        surprise_score is not None
        and forecast_confidence_pct is not None
        and revenue_forecast_next_year_pct is not None
        and surprise_score >= 72
        and forecast_confidence_pct >= 55
        and revenue_forecast_next_year_pct >= 10
    ):
        return ("FUTURE", "meets canonical, surprise, confidence, and next-year growth thresholds")
    if canonical_count <= 0:
        return ("STANDARD", "insufficient canonical coverage for future upside promotion")
    return ("STANDARD", "does not clear the future upside threshold stack")


def _enrich_report_forecast_fields(session: Session, report: CompanyReport) -> None:
    stats = dict(report.key_stats or {})
    filings_count = int(stats.get("filings_count") or 0)
    raw_facts_count = int(stats.get("raw_facts_count") or 0)
    canonical_count = int(stats.get("canonical_facts_count") or 0)
    quality_score = _safe_float(stats.get("accounting_quality_score")) or report.composite_score
    revenue_growth_pct = _safe_float(stats.get("revenue_growth_pct")) or 0.0
    owner_earnings = _safe_float(stats.get("owner_earnings"))
    margin_pct = _safe_float(stats.get("margin_pct"))
    assets = _safe_float(stats.get("assets"))
    liabilities = _safe_float(stats.get("liabilities"))
    diluted_shares = _safe_float(stats.get("weighted_avg_diluted_shares")) or _safe_float(stats.get("shares_outstanding"))
    if diluted_shares in (None, 0):
        diluted_shares = _estimate_share_count(session, report)
    net_income = _safe_float(stats.get("net_income"))
    leverage_ratio = _safe_divide(liabilities, assets)
    balance_score = _clamp(100 - ((leverage_ratio or 0.5) * 100), 0, 100) if leverage_ratio is not None else 45.0
    years_of_history = max(1, min(5, filings_count // 4)) if filings_count > 0 else 1

    forecast_confidence_pct = _forecast_confidence(
        filings_count=filings_count,
        years_of_history=years_of_history,
        canonical_count=canonical_count,
        raw_facts_count=raw_facts_count,
        quality_score=quality_score,
    )
    revenue_forecast_next_year_pct = round(
        _clamp((revenue_growth_pct or 0.0) * 0.72 + max(0.0, quality_score - 60.0) * 0.12, -12.0, 28.0),
        2,
    )
    revenue_forecast_next_quarter_pct = round(
        _clamp((revenue_growth_pct or 0.0) * 0.45 + max(0.0, quality_score - 60.0) * 0.08, -8.0, 18.0),
        2,
    )
    margin_forecast_pct = round(
        _clamp((margin_pct or 6.0) + max(0.0, quality_score - 62.0) * 0.05, -5.0, 32.0),
        2,
    )
    owner_earnings_forecast = round(
        owner_earnings * (1 + (revenue_forecast_next_year_pct / 100)),
        2,
    ) if owner_earnings is not None else None
    eps = _safe_float(stats.get("eps"))
    if eps is None and net_income is not None and diluted_shares not in (None, 0):
        eps = round(net_income / diluted_shares, 2)
    eps_forecast = round(eps * (1 + (revenue_forecast_next_year_pct / 100)), 2) if eps is not None else None
    scenario_valuations = _scenario_valuations(
        earnings_power=owner_earnings if owner_earnings and owner_earnings > 0 else net_income,
        quality_score=quality_score,
        growth_pct=revenue_forecast_next_year_pct,
        share_count=diluted_shares,
    )
    surprise_score = _expected_surprise_score(
        revenue_growth_pct=revenue_forecast_next_year_pct,
        owner_earnings=owner_earnings_forecast,
        margin_pct=margin_forecast_pct,
        confidence_pct=forecast_confidence_pct,
        accounting_quality_score=quality_score,
    )
    designation_profile = _designation_profile(
        revenue_growth_pct=revenue_forecast_next_year_pct,
        owner_earnings=owner_earnings_forecast,
        balance_score=balance_score,
        accounting_quality_score=quality_score,
        leverage_ratio=leverage_ratio,
    )
    surprise_upside_pct = None
    if scenario_valuations["bull"] is not None and scenario_valuations["base"] not in (None, 0):
        surprise_upside_pct = round(((scenario_valuations["bull"] - scenario_valuations["base"]) / scenario_valuations["base"]) * 100, 2)
    future_bucket, future_reason = _future_bucket(
        canonical_count=canonical_count,
        surprise_score=surprise_score,
        forecast_confidence_pct=forecast_confidence_pct,
        revenue_forecast_next_year_pct=revenue_forecast_next_year_pct,
    )

    stats.update(
        {
            "eps": _maybe_round(eps),
            "weighted_avg_diluted_shares": _maybe_round(diluted_shares),
            "shares_outstanding": _maybe_round(diluted_shares),
            "eps_forecast": _maybe_round(eps_forecast),
            "revenue_forecast_next_quarter_pct": _maybe_round(revenue_forecast_next_quarter_pct),
            "revenue_forecast_next_year_pct": _maybe_round(revenue_forecast_next_year_pct),
            "margin_forecast_pct": _maybe_round(margin_forecast_pct),
            "owner_earnings_forecast": _maybe_round(owner_earnings_forecast),
            "forecast_confidence_pct": _maybe_round(forecast_confidence_pct),
            "surprise_score": _maybe_round(surprise_score),
            "surprise_upside_pct": _maybe_round(surprise_upside_pct),
            "designation_profile": designation_profile,
            "scenario_bear_value": _maybe_round(scenario_valuations["bear"]),
            "scenario_base_value": _maybe_round(scenario_valuations["base"]),
            "scenario_bull_value": _maybe_round(scenario_valuations["bull"]),
            "future_bucket": future_bucket,
            "future_reason": future_reason,
        }
    )
    report.key_stats = stats
    flag_modified(report, "key_stats")


def backfill_report_forecast_fields(session: Session) -> dict[str, int]:
    reports = session.execute(select(CompanyReport).order_by(CompanyReport.updated_at.desc())).scalars().all()
    future_count = 0
    standard_count = 0
    for report in reports:
        _enrich_report_forecast_fields(session, report)
        if (report.key_stats or {}).get("future_bucket") == "FUTURE":
            future_count += 1
        else:
            standard_count += 1
    session.flush()
    return {
        "reports_examined": len(reports),
        "future_count": future_count,
        "standard_count": standard_count,
    }


def _forecast_confidence(
    *,
    filings_count: int,
    years_of_history: int,
    canonical_count: int,
    raw_facts_count: int,
    quality_score: float,
) -> float:
    coverage_component = min(35.0, filings_count * 1.3)
    history_component = min(20.0, years_of_history * 4.0)
    mapping_component = min(20.0, ((canonical_count / raw_facts_count) * 20.0) if raw_facts_count else 0.0)
    quality_component = min(25.0, max(0.0, quality_score - 50.0) * 0.5)
    return round(_clamp(coverage_component + history_component + mapping_component + quality_component, 8.0, 95.0), 2)


def _designation_profile(
    *,
    revenue_growth_pct: float | None,
    owner_earnings: float | None,
    balance_score: float,
    accounting_quality_score: float,
    leverage_ratio: float | None,
) -> str:
    if leverage_ratio is not None and leverage_ratio > 0.72:
        return "Balance Sheet Repair"
    if owner_earnings is not None and owner_earnings > 0 and accounting_quality_score >= 75 and balance_score >= 65:
        return "Compounder Core"
    if revenue_growth_pct is not None and revenue_growth_pct >= 18 and accounting_quality_score >= 68:
        return "Positive Surprise Setup"
    if balance_score >= 70 and accounting_quality_score >= 65:
        return "Cash Flow Quality"
    return "Developing Coverage"


def _scenario_valuations(
    *,
    earnings_power: float | None,
    quality_score: float,
    growth_pct: float | None,
    share_count: float | None = None,
) -> dict[str, float | None]:
    if earnings_power is None or earnings_power <= 0:
        return {"bear": None, "base": None, "bull": None}
    normalized_growth = max(-10.0, min(35.0, growth_pct or 0.0))
    bear_multiple = 6.0 + max(0.0, (quality_score - 55.0) / 18.0)
    base_multiple = 8.5 + max(0.0, (quality_score - 55.0) / 12.0) + max(0.0, normalized_growth / 22.0)
    bull_multiple = 11.0 + max(0.0, (quality_score - 55.0) / 9.0) + max(0.0, normalized_growth / 14.0)
    divisor = share_count if share_count and share_count > 0 else 1.0
    return {
        "bear": round((earnings_power * bear_multiple) / divisor, 2),
        "base": round((earnings_power * base_multiple) / divisor, 2),
        "bull": round((earnings_power * bull_multiple) / divisor, 2),
    }


def _expected_surprise_score(
    *,
    revenue_growth_pct: float | None,
    owner_earnings: float | None,
    margin_pct: float | None,
    confidence_pct: float,
    accounting_quality_score: float,
) -> float:
    growth_component = max(0.0, min(35.0, (revenue_growth_pct or 0.0) * 1.1))
    margin_component = max(0.0, min(20.0, (margin_pct or 0.0) * 1.6))
    quality_component = max(0.0, min(25.0, accounting_quality_score - 55.0))
    cash_component = 10.0 if owner_earnings is not None and owner_earnings > 0 else 0.0
    confidence_component = max(0.0, min(15.0, (confidence_pct - 40.0) * 0.3))
    return round(_clamp(growth_component + margin_component + quality_component + cash_component + confidence_component, 0.0, 100.0), 2)


def _fmt_num(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def _stance_for_score(score: float) -> str:
    if score >= 75:
        return "MOST_BULLISH"
    if score >= 62:
        return "BULLISH"
    if score >= 48:
        return "NEUTRAL"
    if score >= 35:
        return "BEARISH"
    return "MOST_BEARISH"


def _pipeline_stage(raw_facts_count: int, canonical_count: int) -> str:
    if canonical_count > 0:
        return "reports-ready"
    if raw_facts_count > 0:
        return "facts-ingested"
    return "filings-only"


def _safe_error_text(exc: Exception) -> str:
    text = str(exc).encode("ascii", "replace").decode("ascii")
    return text or exc.__class__.__name__


MACHINE = ContinuousResearchMachine()
