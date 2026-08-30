from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

DB_PATH = Path("data/accountant.db")


def main() -> None:
    if not DB_PATH.exists():
        print(json.dumps({"ok": False, "reason": "database_missing"}))
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    rows = cur.execute(
        """
        select ticker, standardized_financials, growth_trend_deltas, accrual_cash_quality,
               textual_signals, event_red_flags, governance_ownership, market_data_linkage,
               universe_tradability, final_verdict
        from report_cards
        order by created_at desc
        """
    ).fetchall()

    counters = Counter()
    samples: dict[str, list[dict[str, object]]] = {
        "missing_lineage": [],
        "suspicious_ratios": [],
        "missing_market_data": [],
        "empty_governance": [],
    }

    for row in rows:
        (
            ticker,
            standardized_financials_raw,
            growth_raw,
            accrual_raw,
            textual_raw,
            event_raw,
            governance_raw,
            market_raw,
            tradability_raw,
            verdict_raw,
        ) = row
        standardized_financials = json.loads(standardized_financials_raw or "{}")
        growth = json.loads(growth_raw or "{}")
        accrual = json.loads(accrual_raw or "{}")
        textual = json.loads(textual_raw or "{}")
        event = json.loads(event_raw or "{}")
        governance = json.loads(governance_raw or "{}")
        market = json.loads(market_raw or "{}")
        tradability = json.loads(tradability_raw or "{}")
        verdict = json.loads(verdict_raw or "{}")

        counters["rows"] += 1
        if not verdict.get("score_lineage"):
            counters["missing_lineage"] += 1
            _maybe_append(samples["missing_lineage"], {"ticker": ticker})
        if market.get("price_asof") is None:
            counters["missing_price"] += 1
            _maybe_append(
                samples["missing_market_data"],
                {"ticker": ticker, "market_cap": market.get("market_cap")},
            )
        if not _has_meaningful(governance):
            counters["empty_governance"] += 1
            _maybe_append(samples["empty_governance"], {"ticker": ticker})
        if textual.get("yoy_filing_similarity_score") is None:
            counters["missing_textual_similarity"] += 1
        if event.get("sec_comment_letter_flag"):
            counters["sec_comment_letter_flagged"] += 1
        if tradability.get("passes_liquidity_filter") is None:
            counters["missing_liquidity_flag"] += 1

        suspicious = []
        gross_margin = _as_float(growth.get("gross_margin"))
        sga_pct = _as_float(growth.get("sga_pct_revenue"))
        sbc_pct = _as_float(accrual.get("sbc_pct_revenue"))
        dso = _as_float(growth.get("dso"))
        if gross_margin is not None and abs(gross_margin) > 500:
            suspicious.append(f"gross_margin={gross_margin}")
        if sga_pct is not None and abs(sga_pct) > 1000:
            suspicious.append(f"sga_pct_revenue={sga_pct}")
        if sbc_pct is not None and abs(sbc_pct) > 500:
            suspicious.append(f"sbc_pct_revenue={sbc_pct}")
        if dso is not None and dso > 365:
            suspicious.append(f"dso={dso}")
        if suspicious:
            counters["suspicious_ratio_rows"] += 1
            _maybe_append(samples["suspicious_ratios"], {"ticker": ticker, "issues": suspicious})

        if standardized_financials.get("diluted_shares") is None:
            counters["missing_diluted_shares"] += 1
        if (
            market.get("market_cap") is None
            and market.get("price_asof") is not None
            and standardized_financials.get("diluted_shares") is not None
        ):
            counters["market_cap_compute_gap"] += 1

    con.close()
    print(
        json.dumps(
            {
                "ok": True,
                "counts": dict(counters),
                "samples": samples,
            },
            indent=2,
        )
    )


def _as_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_meaningful(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        return value.strip() not in {"", "none", "null"}
    if isinstance(value, dict):
        return any(_has_meaningful(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_meaningful(item) for item in value)
    return True


def _maybe_append(target: list[dict[str, object]], payload: dict[str, object]) -> None:
    if len(target) < 10:
        target.append(payload)


if __name__ == "__main__":
    main()
