from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompanyRoute:
    family: str
    reason: str
    lane1_supported: bool


def route_company(
    *,
    gics_sector: str | None,
    sic_description: str | None,
    revenue: float | None,
    owner_earnings: float | None,
    net_income: float | None,
) -> CompanyRoute:
    sector = (gics_sector or "").strip().lower()
    sic = (sic_description or "").strip().lower()

    if _is_financial(sector=sector, sic=sic):
        return CompanyRoute(
            family="financials",
            reason="financial statements require reserve and capital-specific model",
            lane1_supported=False,
        )
    if _is_reit_or_asset_heavy(sector=sector, sic=sic):
        return CompanyRoute(
            family="reit_asset_heavy",
            reason="asset-heavy / REIT issuer requires FFO and asset-value model",
            lane1_supported=False,
        )
    if _is_ai_compute(sector=sector, sic=sic):
        return CompanyRoute(
            family="ai_compute",
            reason="AI / compute issuer needs growth, capacity, dilution, and cash-burn aware scoring",
            lane1_supported=True,
        )
    if _is_energy_resources(sector=sector, sic=sic):
        return CompanyRoute(
            family="energy_resources",
            reason="energy/resources issuer needs commodity, reserve, depletion, and leverage-aware scoring",
            lane1_supported=True,
        )
    if _is_pre_revenue(revenue=revenue, owner_earnings=owner_earnings, net_income=net_income):
        return CompanyRoute(
            family="pre_revenue",
            reason="pre-revenue or cash-burning issuer belongs in runway/dilution model",
            lane1_supported=False,
        )
    if _is_general_bucket(sector=sector, sic=sic):
        return CompanyRoute(
            family="general",
            reason="issuer does not yet fit a dedicated accounting strategy lane",
            lane1_supported=False,
        )
    return CompanyRoute(
        family="operating_company",
        reason="operating issuer supports Lane 1 forensic quality model",
        lane1_supported=True,
    )


def _is_financial(*, sector: str, sic: str) -> bool:
    if sector == "financials":
        return True
    markers = ("bank", "financial", "finance", "insurance", "asset management", "broker")
    return any(marker in sic for marker in markers)


def _is_reit_or_asset_heavy(*, sector: str, sic: str) -> bool:
    if sector in {"real estate", "utilities"}:
        return True
    markers = ("reit", "real estate", "realty", "property", "pipeline", "utility")
    return any(marker in sic for marker in markers)


def _is_ai_compute(*, sector: str, sic: str) -> bool:
    markers = (
        "semiconductor",
        "software",
        "computer",
        "data processing",
        "information retrieval",
        "communications equipment",
        "electronic components",
    )
    return any(marker in sic for marker in markers) or sector in {"information technology", "communication services"}


def _is_energy_resources(*, sector: str, sic: str) -> bool:
    markers = (
        "oil",
        "gas",
        "petroleum",
        "coal",
        "mining",
        "drilling",
        "pipeline",
        "energy",
        "electric services",
        "metal",
    )
    return any(marker in sic for marker in markers) or sector in {"energy", "materials"}


def _is_pre_revenue(*, revenue: float | None, owner_earnings: float | None, net_income: float | None) -> bool:
    if revenue is None or revenue <= 0:
        return True
    return bool(owner_earnings is not None and owner_earnings < 0 and (net_income is None or net_income < 0))


def _is_general_bucket(*, sector: str, sic: str) -> bool:
    if not sector and not sic:
        return True
    markers = (
        "holding",
        "shell",
        "blank check",
        "acquisition",
        "spac",
        "partnership",
        "trust",
        "fund",
    )
    if any(marker in sic for marker in markers):
        return True
    return sector in {"other", "unknown"}
