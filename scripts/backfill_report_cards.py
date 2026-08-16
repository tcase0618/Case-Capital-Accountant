from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError

from accountant.db import Base, create_db_engine, create_session_factory
from accountant.db.models import Company, CompanyReport, Filing, ReportCard, Security
from accountant.research.report_cards import _build_report_card_id, _pointer_hash


def main() -> None:
    engine = create_db_engine()
    import accountant.db.models.report_card  # noqa: F401

    Base.metadata.create_all(bind=engine)
    factory = create_session_factory(engine)
    session = factory()
    try:
        company_rows = session.execute(
            select(Company.id).distinct()
            .join(CompanyReport, CompanyReport.company_id == Company.id)
            .order_by(Company.id.asc())
        ).all()
        seen_company_ids: set[object] = set()
        rows: list[tuple[Company, CompanyReport, Security]] = []
        for (company_id,) in company_rows:
            if company_id in seen_company_ids:
                continue
            seen_company_ids.add(company_id)
            company = session.get(Company, company_id)
            if company is None:
                continue
            report = session.execute(
                select(CompanyReport).where(CompanyReport.company_id == company_id).limit(1)
            ).scalar_one_or_none()
            security = session.execute(
                select(Security)
                .where(Security.company_id == company_id)
                .order_by(Security.ticker.asc())
                .limit(1)
            ).scalar_one_or_none()
            if report is None or security is None:
                continue
            rows.append((company, report, security))
    finally:
        session.close()

    started = datetime.now(UTC)
    inserted = 0
    skipped = 0
    errors = 0
    print(f"[{started.isoformat()}] fast backfill report_cards companies={len(rows)}", flush=True)

    session = factory()
    try:
        for index, (company, report, security) in enumerate(rows, start=1):
            try:
                latest_filing = session.execute(
                    select(Filing)
                    .where(Filing.company_id == company.id)
                    .order_by(Filing.filing_date.desc(), Filing.accepted_at.desc(), Filing.created_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if latest_filing is None or latest_filing.filing_date is None:
                    skipped += 1
                    continue

                report_card_id = _build_report_card_id(
                    cik=company.cik,
                    filing_type=latest_filing.form_type,
                    period_of_report=latest_filing.report_date,
                    filed_date=latest_filing.filing_date,
                )
                existing = session.execute(
                    select(ReportCard.id).where(ReportCard.report_card_id == report_card_id)
                ).scalar_one_or_none()
                if existing is not None:
                    skipped += 1
                    continue

                prior = session.execute(
                    select(ReportCard)
                    .where(ReportCard.company_id == company.id, ReportCard.filed_date < latest_filing.filing_date)
                    .order_by(desc(ReportCard.filed_date), desc(ReportCard.created_at))
                    .limit(1)
                ).scalar_one_or_none()
                stats = dict(report.key_stats or {})
                card = ReportCard(
                    company_id=company.id,
                    report_card_id=report_card_id,
                    cik=company.cik,
                    ticker=report.ticker,
                    company_name=report.company_name,
                    sic_code=company.sic,
                    gics_sector=str(_pick(stats, "gics_sector")),
                    gics_industry=str(_pick(stats, "gics_industry") or (company.sic_description or "Unclassified")[:120]),
                    exchange=security.exchange,
                    filing_type=latest_filing.form_type,
                    period_of_report=latest_filing.report_date,
                    filed_date=latest_filing.filing_date,
                    accepted_at=latest_filing.accepted_at,
                    accession_number=latest_filing.accession_number,
                    source_url=latest_filing.source_url,
                    raw_filing_sha256=_pointer_hash(latest_filing.accession_number, latest_filing.source_url),
                    is_restatement=bool(latest_filing.is_amendment),
                    restates_report_card_id=prior.report_card_id if latest_filing.is_amendment and prior else None,
                    tag_map_version="CANONICAL_MAPPING_V1",
                    prior_report_card_id=prior.report_card_id if prior else None,
                    standardized_financials={
                        "revenue": _pick(stats, "revenue"),
                        "net_income": _pick(stats, "net_income"),
                        "total_assets": _pick(stats, "assets"),
                        "total_liabilities": _pick(stats, "liabilities"),
                        "total_equity": _pick(stats, "equity"),
                        "cfo": _pick(stats, "owner_earnings"),
                        "diluted_eps": _pick(stats, "eps"),
                        "diluted_shares": _pick(stats, "weighted_avg_diluted_shares"),
                    },
                    growth_trend_deltas={
                        "revenue_yoy_growth": _pick(stats, "revenue_growth_pct"),
                        "diluted_shares_yoy_change": _pick(stats, "dilution_growth_pct"),
                        "gross_margin": _pick(stats, "margin_pct"),
                    },
                    accrual_cash_quality={
                        "cash_based_operating_profitability": _pick(stats, "cash_based_operating_profitability"),
                        "net_operating_assets_pct_assets": _pick(stats, "net_operating_assets_ratio"),
                        "sloan_accrual_ratio": _pick(stats, "sloan_accrual_ratio"),
                        "fcf_ni_ratio": None,
                        "cash_conversion_ratio": None,
                    },
                    forensic_scores={
                        "beneish_m_score": _pick(stats, "beneish_m_score"),
                        "piotroski_f_score": _pick(stats, "piotroski_f_score"),
                        "altman_z_double_prime": _pick(stats, "altman_z_score"),
                        "factor_quality_score": _pick(stats, "factor_quality_score"),
                        "factor_forensic_risk_score": _pick(stats, "factor_forensic_risk_score"),
                    },
                    positive_quality={
                        "positive_quality_score": _pick(stats, "factor_quality_score") or _pick(stats, "accounting_quality_score"),
                        "red_flag_penalty": _pick(stats, "factor_forensic_risk_score"),
                        "composite_locked_asof": latest_filing.filing_date.isoformat(),
                    },
                    event_red_flags={
                        "restatement_severity": "little-r" if latest_filing.is_amendment else "none",
                        "late_filer_flag": False,
                        "going_concern_flag": False,
                        "material_weakness_flag": False,
                    },
                    textual_signals={
                        "llm_summary": None,
                        "llm_model_version": None,
                        "llm_confidence": None,
                    },
                    non_gaap_forensics={
                        "gaap_eps": _pick(stats, "eps"),
                        "non_gaap_eps": None,
                    },
                    governance_ownership={},
                    market_data_linkage={
                        "price_asof": report.current_price,
                        "market_cap": None,
                    },
                    universe_tradability={
                        "excluded_recent_ipo": False,
                    },
                    final_verdict={
                        "current_action": _action_for_stance(report.stance),
                        "veto_triggered": False,
                        "veto_reason": None,
                        "last_scored_ts": report.updated_at.isoformat() if report.updated_at else None,
                        "stance": report.stance,
                        "composite_score": report.composite_score,
                    },
                )
                session.add(card)
                inserted += 1
                if index % 100 == 0:
                    session.commit()
                    print(
                        f"[{index}/{len(rows)}] inserted={inserted} skipped={skipped} errors={errors} last={report.ticker}",
                        flush=True,
                    )
            except IntegrityError:
                session.rollback()
                skipped += 1
            except Exception as exc:
                session.rollback()
                errors += 1
                print(f"[{index}/{len(rows)}] error ticker={report.ticker} message={str(exc)[:240]}", flush=True)

        session.commit()
    finally:
        session.close()

    ended = datetime.now(UTC)
    print(
        f"[{ended.isoformat()}] completed inserted={inserted} skipped={skipped} errors={errors} "
        f"duration_seconds={(ended - started).total_seconds():.1f}",
        flush=True,
    )
    engine.dispose()


def _pick(stats: dict[str, object], key: str) -> object | None:
    value = stats.get(key)
    return None if value == "" else value


def _action_for_stance(stance: str) -> str:
    if stance == "MOST_BULLISH":
        return "BUY"
    if stance == "BULLISH":
        return "HOLD"
    if stance == "NEUTRAL":
        return "WATCH"
    if stance in {"BEARISH", "MOST_BEARISH"}:
        return "EXIT"
    return "EXCLUDED"


if __name__ == "__main__":
    main()
