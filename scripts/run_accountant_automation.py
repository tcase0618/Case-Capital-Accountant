from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg

from accountant.config import get_settings


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_DIR = REPO_ROOT / "artifacts" / "automation"

AI_SIC_KEYWORDS = (
    "semiconductors",
    "semiconductor",
    "software",
    "prepackaged software",
    "computer programming",
    "data processing",
    "information retrieval",
    "computer integrated systems",
    "computer communications",
    "electronic computers",
    "computer peripheral",
    "computer storage",
)
AI_NAME_KEYWORDS = (
    "artificial intelligence",
    "machine learning",
    "cerebras",
    "palantir",
    "nvidia",
    "super micro computer",
    "soundhound ai",
    "c3.ai",
    "bigbear.ai",
    "guardforce ai",
    "applied digital",
    "coreweave",
    "datadog",
    "snowflake",
)
ENERGY_KEYWORDS = (
    "oil",
    "gas",
    "petroleum",
    "natural gas",
    "crude",
    "drilling",
    "coal",
    "pipeline",
    "energy",
    "electric services",
    "power",
    "solar",
    "renewable",
    "uranium",
    "nuclear",
    "metal mining",
    "gold and silver ores",
    "lithium",
    "battery",
)


@dataclass
class StepResult:
    name: str
    returncode: int
    started_at: str
    finished_at: str
    log_path: str


def main() -> int:
    args = _parse_args()
    AUTOMATION_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    summary_path = AUTOMATION_DIR / f"accountant_automation_{run_id}.json"
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")

    steps: list[StepResult] = []
    before = _database_snapshot(dsn)

    if not args.skip_import:
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "import_stale_sec_filings.py"),
            "--workers",
            str(args.import_workers),
        ]
        if args.from_date:
            command += ["--from-date", args.from_date]
        if args.to_date:
            command += ["--to-date", args.to_date]
        steps.append(_run_step("import_stale_sec_filings", command, run_id))

    if not args.skip_stale_refresh:
        steps.append(
            _run_step(
                "refresh_stale_core_reports",
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "refresh_stale_core_reports.py"),
                    "--workers",
                    str(args.refresh_workers),
                    "--log-level",
                    args.log_level,
                ],
                run_id,
            )
        )

    if args.refresh_all_scores:
        steps.append(
            _run_step(
                "refresh_all_report_scores",
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "refresh_all_report_scores.py"),
                    "--workers",
                    str(args.score_workers),
                ],
                run_id,
            )
        )

    steps.append(
        _run_step(
            "refresh_bottleneck_cache",
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "refresh_bottleneck_cache.py"),
            ],
            run_id,
        )
    )

    after = _database_snapshot(dsn)
    bottleneck_summary = _write_company_bottlenecks(dsn, run_id=run_id)
    readiness = _readiness_snapshot(dsn, stale_core_report_cards=_remaining_stale_from_logs(steps))
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "before": before,
        "after": after,
        "delta": {
            "filings_estimate": after["filings_count_estimate"] - before["filings_count_estimate"],
            "report_cards": after["report_cards_count"] - before["report_cards_count"],
            "company_reports": after["company_reports_count"] - before["company_reports_count"],
        },
        "steps": [step.__dict__ for step in steps],
        "readiness": readiness,
        "bottlenecks": bottleneck_summary,
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2), flush=True)
    return 1 if any(step.returncode != 0 for step in steps) else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the unattended Accountant maintenance cycle.")
    parser.add_argument("--from-date", default=None)
    parser.add_argument("--to-date", default=None)
    parser.add_argument("--import-workers", type=int, default=8)
    parser.add_argument("--refresh-workers", type=int, default=8)
    parser.add_argument("--score-workers", type=int, default=3)
    parser.add_argument("--log-level", default="WARNING")
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--skip-stale-refresh", action="store_true")
    parser.add_argument("--refresh-all-scores", action="store_true")
    return parser.parse_args()


def _run_step(name: str, command: list[str], run_id: str) -> StepResult:
    started = datetime.now(UTC)
    log_path = AUTOMATION_DIR / f"{run_id}_{name}.log"
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        log.write(f"$ {' '.join(command)}\n\n")
        log.flush()
        proc = subprocess.run(
            command,
            cwd=REPO_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    finished = datetime.now(UTC)
    return StepResult(
        name=name,
        returncode=proc.returncode,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        log_path=str(log_path),
    )


def _database_snapshot(dsn: str) -> dict[str, Any]:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select
              (select count(*) from company_reports),
              (select count(*) from report_cards),
              (select count(*) from statement_snapshots)
            """
        )
        row = cur.fetchone()
        cur.execute(
            """
            select filing_date::text, coalesce(accepted_at::text, '')
            from filings
            order by filing_date desc
            limit 1
            """
        )
        latest = cur.fetchone() or ("", "")
        estimates = _table_estimates(cur, ["filings", "canonical_facts", "raw_facts"])
    return {
        "filings_count_estimate": estimates["filings"],
        "max_filing_date": latest[0],
        "max_accepted_at_for_latest_filing_date": latest[1],
        "company_reports_count": int(row[0]),
        "report_cards_count": int(row[1]),
        "statement_snapshots_count": int(row[2]),
        "canonical_facts_count_estimate": estimates["canonical_facts"],
        "raw_facts_count_estimate": estimates["raw_facts"],
    }


def _table_estimates(cur: Any, table_names: list[str]) -> dict[str, int]:
    cur.execute(
        """
        select relname, greatest(reltuples::bigint, 0)
        from pg_class
        where relname = any(%s)
        """,
        (table_names,),
    )
    rows = {name: int(count) for name, count in cur.fetchall()}
    return {name: rows.get(name, 0) for name in table_names}


def _remaining_stale_from_logs(steps: list[StepResult]) -> int | None:
    for step in reversed(steps):
        if step.name != "refresh_stale_core_reports":
            continue
        text = Path(step.log_path).read_text(encoding="utf-8", errors="replace")
        marker = "remaining_stale="
        index = text.rfind(marker)
        if index == -1:
            return None
        value = text[index + len(marker):].split()[0].strip()
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _readiness_snapshot(dsn: str, *, stale_core_report_cards: int | None) -> dict[str, Any]:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            with latest_reports as (
                select data_quality_tier, pipeline_stage, count(*) count
                from company_reports
                group by data_quality_tier, pipeline_stage
            )
            select
              (select jsonb_object_agg(coalesce(data_quality_tier, 'NULL') || ':' || coalesce(pipeline_stage, 'NULL'), count) from latest_reports)
            """
        )
        quality_counts = cur.fetchone()[0]
    return {
        "stale_core_report_cards": stale_core_report_cards,
        "quality_stage_counts": quality_counts or {},
    }


def _write_company_bottlenecks(dsn: str, *, run_id: str) -> dict[str, Any]:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select ticker, company_name, focus_family, sic, sic_description, stance, score,
                   model_family, model_family_score, data_quality_tier, latest_filing_date,
                   bottlenecks, management_bottlenecks
            from company_bottleneck_snapshots
            order by ticker
            """
        )
        columns = [desc.name for desc in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    csv_path = AUTOMATION_DIR / f"{run_id}_company_bottlenecks.csv"
    family_counts: Counter[str] = Counter()
    overall_counts: Counter[str] = Counter()
    family_bottlenecks: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    output_rows: list[dict[str, Any]] = []

    for row in rows:
        family = row.get("focus_family") or "General"
        family_counts[family] += 1
        top = row.get("bottlenecks") or [{"category": "No major blocker detected", "detail": "No deterministic blocker triggered"}]
        categories = [str(item.get("category") or "") for item in top[:3]]
        details = [str(item.get("detail") or "") for item in top[:3]]
        for item in top[:3]:
            category = str(item.get("category") or "")
            detail = str(item.get("detail") or "")
            if not category:
                continue
            overall_counts[category] += 1
            family_bottlenecks[family][category] += 1
            if len(examples[family][category]) < 8:
                examples[family][category].append(f"{row['ticker']}: {detail}")
        output_rows.append(
            {
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "focus_family": family,
                "sic": row.get("sic"),
                "sic_description": row.get("sic_description"),
                "stance": row.get("stance"),
                "score": row.get("score"),
                "model_family": row.get("model_family"),
                "model_family_score": row.get("model_family_score"),
                "data_quality_tier": row.get("data_quality_tier"),
                "latest_filing_date": row.get("latest_filing_date"),
                "bottleneck_1": categories[0] if len(categories) > 0 else "",
                "bottleneck_1_detail": details[0] if len(details) > 0 else "",
                "bottleneck_2": categories[1] if len(categories) > 1 else "",
                "bottleneck_2_detail": details[1] if len(details) > 1 else "",
                "bottleneck_3": categories[2] if len(categories) > 2 else "",
                "bottleneck_3_detail": details[2] if len(details) > 2 else "",
                "management_bottlenecks": json.dumps(row.get("management_bottlenecks") or []),
            }
        )

    if output_rows:
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(output_rows[0].keys()))
            writer.writeheader()
            writer.writerows(output_rows)

    return {
        "companies_analyzed": len(rows),
        "output_csv": str(csv_path),
        "focus_family_counts": dict(family_counts),
        "ai_compute_top_bottlenecks": _top_family_payload("AI / compute", family_bottlenecks, examples),
        "energy_resources_top_bottlenecks": _top_family_payload("Energy / resources", family_bottlenecks, examples),
        "overall_top_bottlenecks": [
            {"category": category, "company_count": count}
            for category, count in overall_counts.most_common(15)
        ],
    }


def _top_family_payload(
    family: str,
    family_bottlenecks: dict[str, Counter[str]],
    examples: dict[str, dict[str, list[str]]],
) -> list[dict[str, Any]]:
    return [
        {
            "category": category,
            "company_count": count,
            "examples": examples[family][category],
        }
        for category, count in family_bottlenecks[family].most_common(10)
    ]


def _company_bottlenecks(row: dict[str, Any]) -> list[tuple[str, str]]:
    stats = _as_dict(row.get("key_stats"))
    items: list[tuple[float, str, str]] = []

    def add(severity: float, category: str, detail: str) -> None:
        items.append((severity, category, detail))

    revenue = _float(stats.get("revenue"))
    revenue_growth = _float(stats.get("revenue_growth_pct"))
    net_income = _float(stats.get("net_income"))
    owner_earnings = _float(stats.get("owner_earnings"))
    owner_margin = _float(stats.get("owner_earnings_margin_pct"))
    margin = _float(stats.get("margin_pct"))
    assets = _float(stats.get("assets"))
    liabilities = _float(stats.get("liabilities"))
    dilution = _float(stats.get("dilution_growth_pct"))
    coverage = _float(stats.get("overall_coverage_pct"))
    accounting_quality = _float(stats.get("accounting_quality_score"))
    a_his = _float(stats.get("a_his_score"))
    factor_warnings = _float(stats.get("factor_warning_count"))
    eps_forecast = _float(stats.get("eps_forecast"))
    leverage = liabilities / assets * 100 if liabilities is not None and assets and assets > 0 else None

    if row.get("data_quality_tier") in {"INSUFFICIENT", "PARTIAL"} or (coverage is not None and coverage < 55):
        add(90, "Insufficient earnings-data coverage", f"tier={row.get('data_quality_tier')}, coverage={_fmt(coverage, '%')}")
    if factor_warnings and factor_warnings > 0:
        add(82, "Missing/incomplete accounting factor pack", f"factor warnings={factor_warnings:.0f}")
    elif any(stats.get(key) is None for key in ("beneish_m_score", "piotroski_f_score", "altman_z_score")):
        add(68, "Missing/incomplete accounting factor pack", "Beneish/Piotroski/Altman unavailable")
    if revenue is None or revenue_growth is None:
        add(70, "Revenue visibility gap", f"revenue={_fmt(revenue)}, revenue growth={_fmt(revenue_growth, '%')}")
    elif revenue_growth < 0:
        add(82 + min(abs(revenue_growth), 30) / 2, "Revenue contraction", f"revenue growth={_fmt(revenue_growth, '%')}")
    elif revenue_growth < 5:
        add(55, "Slow revenue growth", f"revenue growth={_fmt(revenue_growth, '%')}")
    if owner_earnings is None:
        add(62, "Owner-earnings visibility gap", "owner earnings proxy=N/A")
    elif owner_earnings < 0:
        add(84, "Negative owner earnings / cash burn", f"owner earnings={owner_earnings:,.0f}, owner margin={_fmt(owner_margin, '%')}")
    if net_income is not None and net_income < 0:
        add(82, "Net losses / weak profitability", f"net income={net_income:,.0f}, margin={_fmt(margin, '%')}")
    elif margin is not None and margin < 5:
        add(62, "Thin profit margin", f"margin={_fmt(margin, '%')}")
    if leverage is not None:
        if leverage >= 90:
            add(92, "Very high leverage", f"liabilities/assets={leverage:.1f}%")
        elif leverage >= 75:
            add(78, "High leverage", f"liabilities/assets={leverage:.1f}%")
        elif leverage >= 60:
            add(60, "Elevated leverage", f"liabilities/assets={leverage:.1f}%")
    if dilution is not None:
        if dilution >= 25:
            add(92, "Severe dilution", f"share count growth={_fmt(dilution, '%')}")
        elif dilution >= 10:
            add(78, "Material dilution", f"share count growth={_fmt(dilution, '%')}")
    if accounting_quality is not None and accounting_quality < 50:
        add(75, "Weak accounting quality score", f"accounting quality={_fmt(accounting_quality)}")
    if a_his is not None and a_his < 50:
        add(76, "Weak A-HIS accounting ledger score", f"A-HIS={_fmt(a_his)}")
    if eps_forecast is not None and eps_forecast < 0:
        add(70, "Negative EPS forecast", f"CC EPS forecast={eps_forecast:.2f}")

    by_category: dict[str, tuple[float, str]] = {}
    for severity, category, detail in items:
        if category not in by_category or severity > by_category[category][0]:
            by_category[category] = (severity, detail)
    return [
        (category, detail)
        for category, (_severity, detail) in sorted(by_category.items(), key=lambda item: item[1][0], reverse=True)[:3]
    ]


def _classify_family(ticker: str, name: str, sic_description: str | None) -> str:
    sic = (sic_description or "").lower()
    company = (name or "").lower()
    normalized_ticker = (ticker or "").upper()
    if (
        any(keyword in sic for keyword in AI_SIC_KEYWORDS)
        or any(keyword in company for keyword in AI_NAME_KEYWORDS)
        or normalized_ticker in {"AI", "NVDA", "PLTR", "SMCI", "SOUN", "BBAI"}
    ):
        return "AI / compute"
    if any(keyword in sic for keyword in ENERGY_KEYWORDS) or any(keyword in company for keyword in ENERGY_KEYWORDS):
        return "Energy / resources"
    return "General"


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return {}


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _fmt(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}{suffix}"


if __name__ == "__main__":
    raise SystemExit(main())
