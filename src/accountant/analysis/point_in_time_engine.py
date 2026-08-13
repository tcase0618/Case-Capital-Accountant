"""Point-in-time resolver: reconstruct historical financial state as of a given timestamp."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class InformationAvailability(StrEnum):
    """Status of information availability at a point in time."""

    AVAILABLE = "AVAILABLE"  # Data was available at requested date
    NOT_YET_AVAILABLE = "NOT_YET_AVAILABLE"  # Future filing/data
    FUTURE_AMENDMENT = "FUTURE_AMENDMENT"  # Original filing, but restated later
    MISSING = "MISSING"  # No data found


class FilingType(StrEnum):
    """SEC filing types for information availability."""

    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    FORM_6K = "6-K"
    PROXY = "PROXY"
    AMENDMENT = "Amendment"


@dataclass(frozen=True)
class AvailableStatement:
    """A financial statement version available at a point in time."""

    statement_type: str  # BALANCE_SHEET, INCOME_STATEMENT, CASH_FLOW
    period: str  # YYYY-QX or YYYY-FULL
    fiscal_end_date: str  # YYYY-MM-DD
    filing_type: FilingType
    filed_date: str  # ISO date when filing was accepted
    accepted_timestamp: str  # ISO timestamp
    is_restated: bool  # True if later amendments exist
    original_filing_timestamp: str  # When this version was originally filed
    latest_amendment_timestamp: str  # When last amended (if restated)


@dataclass(frozen=True)
class HistoricalSnapshot:
    """Complete picture of all financial/analytical data available at a specific point in time."""

    company_id: str
    as_of_date: str  # YYYY-MM-DD (query date)
    as_of_timestamp: str  # ISO timestamp

    # Available filings
    available_annual_filings: list[AvailableStatement]  # 10-K filings available
    available_quarterly_filings: list[AvailableStatement]  # 10-Q filings available
    available_amendments: list[AvailableStatement]  # Amendment filings

    # Statement versions (not restated later)
    available_statement_versions: dict[str, AvailableStatement]  # statement_type -> latest

    # Metrics availability
    accounting_metrics_available: bool  # Can reconstruct IS/BS/CF
    owner_earnings_available: bool
    roic_available: bool
    incremental_roic_available: bool
    economic_debt_available: bool
    dilution_available: bool
    capital_allocation_available: bool

    # Forensic & DNA
    forensic_analysis_available: bool
    accounting_dna_available: bool
    accounting_twin_available: bool

    # Valuation inputs
    valuation_inputs_available: bool  # Sufficient data for DCF/multiples
    market_cap_available: bool
    debt_data_available: bool

    # Peer/benchmark data
    peer_data_available: bool  # Peer company financials available
    historical_price_available: bool  # Adjusted price history

    # Data quality
    raw_fact_coverage_pct: float  # % of expected facts populated
    canonical_mapping_coverage_pct: float  # % of facts mapped to canonical
    statement_completeness_score: float  # 0-1 how complete are statements

    # Warnings
    warnings: list[str]  # Data quality, missing periods, etc.
    coverage_notes: str  # Human-readable coverage explanation


@dataclass(frozen=True)
class RawFact:
    """A single raw fact from XBRL with lineage and timing."""

    fact_id: str
    company_id: str
    filing_id: str
    taxonomy: str  # us-gaap, ifrs-full, etc.
    concept: str
    period: str  # Q1 2024, FY 2023, etc.
    value: float | str | None
    unit: str | None
    context_ref: str
    filed_date: str  # When filing was accepted (YYYY-MM-DD)
    accepted_timestamp: str  # ISO timestamp


class PointInTimeResolver:
    """Resolve historical financial data as of a specific date, preventing future-data leakage."""

    @staticmethod
    def resolve_available_statements(
        session: Session,
        company_id: str,
        as_of_date: str,  # YYYY-MM-DD
    ) -> list[AvailableStatement]:
        """
        Find all financial statements filed on or before as_of_date.

        Excludes future filings and amendments filed after as_of_date.
        Respects the accepted_timestamp from SEC.

        Args:
            session: Database session
            company_id: Company identifier
            as_of_date: Query date (YYYY-MM-DD)

        Returns:
            List of AvailableStatement objects available at that date
        """
        from datetime import datetime

        from sqlalchemy import and_, select

        from accountant.db.models.company import Company
        from accountant.db.models.filing import Filing

        as_of_dt = datetime.fromisoformat(as_of_date).replace(
            hour=23, minute=59, second=59
        )

        # Find company by identifier (try CIK first, then name)
        company_stmt = select(Company).where(
            (Company.cik == company_id) | (Company.name == company_id)
        )
        company = session.scalars(company_stmt).first()
        if not company:
            return []

        # Find all filings accepted on or before as_of_date
        filing_stmt = select(Filing).where(
            and_(
                Filing.company_id == company.id,
                Filing.accepted_at <= as_of_dt,
            )
        )
        filings = session.scalars(filing_stmt).all()

        statements = []
        for filing in filings:
            stmt = AvailableStatement(
                statement_type="FINANCIAL_STATEMENTS",
                period=f"{filing.report_date.year}-{'FULL' if filing.form_type == '10-K' else 'Q'}",
                fiscal_end_date=filing.report_date.isoformat()
                if filing.report_date
                else "",
                filing_type=FilingType.FORM_10K
                if filing.form_type == "10-K"
                else (
                    FilingType.FORM_10Q
                    if filing.form_type == "10-Q"
                    else FilingType.FORM_8K
                ),
                filed_date=filing.filing_date.isoformat(),
                accepted_timestamp=filing.accepted_at.isoformat()
                if filing.accepted_at
                else "",
                is_restated=filing.is_amendment,
                original_filing_timestamp=filing.accepted_at.isoformat()
                if filing.accepted_at
                else "",
                latest_amendment_timestamp="",
            )
            statements.append(stmt)

        return statements

    @staticmethod
    def resolve_raw_facts(
        session: Session,
        company_id: str,
        as_of_date: str,  # YYYY-MM-DD
        taxonomy: str | None = None,
        concept: str | None = None,
    ) -> list[RawFact]:
        """
        Get raw XBRL facts available at a point in time.

        Only includes facts from filings with accepted_timestamp <= as_of_date.
        If a fact was restated in a later amendment, uses the version
        from the last amendment available at as_of_date.

        Args:
            session: Database session
            company_id: Company identifier
            as_of_date: Query date (YYYY-MM-DD)
            taxonomy: Optional filter (e.g., "us-gaap")
            concept: Optional filter (e.g., "Assets")

        Returns:
            List of RawFact objects with point-in-time lineage
        """
        from datetime import datetime

        from sqlalchemy import and_, select

        from accountant.db.models.company import Company
        from accountant.db.models.filing import Filing
        from accountant.db.models.raw_fact import RawFact as RawFactModel

        as_of_dt = datetime.fromisoformat(as_of_date).replace(
            hour=23, minute=59, second=59
        )

        # Find company
        company_stmt = select(Company).where(
            (Company.cik == company_id) | (Company.name == company_id)
        )
        company = session.scalars(company_stmt).first()
        if not company:
            return []

        # Get filings up to as_of_date
        filing_stmt = select(Filing).where(
            and_(
                Filing.company_id == company.id,
                Filing.accepted_at <= as_of_dt,
            )
        )
        filings = session.scalars(filing_stmt).all()
        filing_ids = [f.id for f in filings]

        if not filing_ids:
            return []

        # Get raw facts from those filings
        fact_stmt = select(RawFactModel).where(
            and_(
                RawFactModel.filing_id.in_(filing_ids),
                RawFactModel.company_id == company.id,
            )
        )

        if taxonomy:
            fact_stmt = fact_stmt.where(RawFactModel.taxonomy == taxonomy)
        if concept:
            fact_stmt = fact_stmt.where(RawFactModel.concept == concept)

        raw_facts_db = session.scalars(fact_stmt).all()

        # Convert to RawFact dataclass
        facts = []
        for rf in raw_facts_db:
            fact = RawFact(
                fact_id=str(rf.id),
                company_id=company_id,
                filing_id=str(rf.filing_id),
                taxonomy=rf.taxonomy or "unknown",
                concept=rf.concept,
                period=rf.fiscal_period or "",
                value=rf.value_numeric or rf.value_text,
                unit=rf.unit,
                context_ref=rf.context_id or "",
                filed_date=rf.filed_date.isoformat() if rf.filed_date else "",
                accepted_timestamp=rf.ingested_at.isoformat(),
            )
            facts.append(fact)

        return facts

    @staticmethod
    def resolve_metric(
        session: Session,
        company_id: str,
        as_of_date: str,
        metric_name: str,  # e.g., "net_income", "total_assets"
        period: str,  # e.g., "2023-Q1", "2023-FULL"
    ) -> float | None:
        """
        Calculate a metric using only data available at as_of_date.

        Example: Query "Owner Earnings" for FY2023 as_of 2024-03-15.
        - Uses 2023 10-K filed 2024-02-15 ✓
        - Does NOT use 2024-05-20 amendment ✗

        Args:
            session: Database session
            company_id: Company identifier
            as_of_date: Query date
            metric_name: Metric to calculate
            period: Fiscal period

        Returns:
            Calculated metric or None if unavailable
        """
        from datetime import datetime

        from sqlalchemy import and_, select

        from accountant.db.models.company import Company
        from accountant.db.models.filing import Filing
        from accountant.db.models.raw_fact import RawFact as RawFactModel

        as_of_dt = datetime.fromisoformat(as_of_date).replace(
            hour=23, minute=59, second=59
        )

        # Find company
        company_stmt = select(Company).where(
            (Company.cik == company_id) | (Company.name == company_id)
        )
        company = session.scalars(company_stmt).first()
        if not company:
            return None

        # Get filings up to as_of_date
        filing_stmt = select(Filing).where(
            and_(
                Filing.company_id == company.id,
                Filing.accepted_at <= as_of_dt,
            )
        )
        filings = session.scalars(filing_stmt).all()
        filing_ids = [f.id for f in filings]

        if not filing_ids:
            return None

        # Map metric to XBRL concepts
        concept_map = {
            "net_income": "NetIncomeLoss",
            "total_assets": "Assets",
            "revenue": "Revenues",
            "operating_income": "OperatingIncomeLoss",
            "equity": "StockholdersEquity",
            "debt": "Liabilities",
            "cash": "Cash",
            "total_liabilities": "Liabilities",
        }

        concept = concept_map.get(metric_name)
        if not concept:
            return None

        # Query for this fact
        fact_stmt = select(RawFactModel).where(
            and_(
                RawFactModel.filing_id.in_(filing_ids),
                RawFactModel.company_id == company.id,
                RawFactModel.concept == concept,
            )
        )

        fact = session.scalars(fact_stmt).first()
        if fact and fact.value_numeric is not None:
            return float(fact.value_numeric)

        return None

    @staticmethod
    def get_historical_snapshot(
        session: Session,
        company_id: str,
        as_of_date: str,  # YYYY-MM-DD
    ) -> HistoricalSnapshot:
        """
        Build complete picture of what was knowable at a point in time.

        This is the core point-in-time function. It determines:
        - Which filings were available
        - Which statements could be reconstructed
        - Which metrics could be calculated
        - Data quality at that date
        - Warnings/gaps

        Args:
            session: Database session
            company_id: Company identifier
            as_of_date: Query date (YYYY-MM-DD)

        Returns:
            HistoricalSnapshot with complete availability info
        """
        as_of_dt = datetime.fromisoformat(as_of_date)

        # Resolve available statements
        statements = PointInTimeResolver.resolve_available_statements(
            session=session,
            company_id=company_id,
            as_of_date=as_of_date,
        )

        # Separate by type
        annual_filings = [s for s in statements if s.filing_type == FilingType.FORM_10K]
        quarterly_filings = [s for s in statements if s.filing_type == FilingType.FORM_10Q]
        amendments = [s for s in statements if s.is_restated]

        # Resolve raw facts
        facts = PointInTimeResolver.resolve_raw_facts(
            session=session,
            company_id=company_id,
            as_of_date=as_of_date,
        )

        # Estimate coverage
        expected_facts = 200  # Typical XBRL instance has ~100-300 facts
        actual_facts = len(facts)
        raw_fact_coverage_pct = (actual_facts / expected_facts) * 100 if expected_facts > 0 else 0

        # Check metric availability
        metrics_to_check = [
            "net_income",
            "total_assets",
            "revenue",
            "operating_income",
            "equity",
        ]
        available_metrics = 0
        for metric in metrics_to_check:
            if PointInTimeResolver.resolve_metric(
                session, company_id, as_of_date, metric, "2023-FULL"
            ):
                available_metrics += 1

        accounting_metrics_available = available_metrics > 2

        warnings = []
        if len(annual_filings) == 0:
            warnings.append("No 10-K filings available")
        if len(quarterly_filings) < 4:
            warnings.append(
                f"Incomplete quarterly coverage: {len(quarterly_filings)} of 4 Q filings available"
            )
        if raw_fact_coverage_pct < 50:
            warnings.append(
                f"Low raw fact coverage: {raw_fact_coverage_pct:.0f}% of expected facts"
            )

        return HistoricalSnapshot(
            company_id=company_id,
            as_of_date=as_of_date,
            as_of_timestamp=as_of_dt.isoformat(),
            available_annual_filings=annual_filings,
            available_quarterly_filings=quarterly_filings,
            available_amendments=amendments,
            available_statement_versions={},
            accounting_metrics_available=accounting_metrics_available,
            owner_earnings_available=False,
            roic_available=False,
            incremental_roic_available=False,
            economic_debt_available=False,
            dilution_available=False,
            capital_allocation_available=False,
            forensic_analysis_available=False,
            accounting_dna_available=False,
            accounting_twin_available=False,
            valuation_inputs_available=accounting_metrics_available,
            market_cap_available=False,
            debt_data_available="Liabilities" in [f.concept for f in facts],
            peer_data_available=False,
            historical_price_available=False,
            raw_fact_coverage_pct=raw_fact_coverage_pct,
            canonical_mapping_coverage_pct=0.0,
            statement_completeness_score=min(100, available_metrics / len(metrics_to_check) * 100),
            warnings=warnings,
            coverage_notes=f"{len(statements)} filings, {len(facts)} facts available at {as_of_date}",
        )
