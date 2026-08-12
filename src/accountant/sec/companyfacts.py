"""SEC CompanyFacts API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from accountant.config import Settings
from accountant.sec.client import SecClient


@dataclass(frozen=True)
class CompanyFact:
    """Single fact value from CompanyFacts API."""

    value: str | int | float
    accession: str
    form: str
    filed: str
    frame: str | None
    units: str
    start: str | None
    end: str | None
    instant: str | None
    decimals: int | None


@dataclass(frozen=True)
class CompanyConceptMetadata:
    """Metadata for a concept within CompanyFacts."""

    taxonomy: str
    label: str
    description: str | None


class CompanyFactsClient:
    """Client for SEC CompanyFacts API."""

    def __init__(self, settings: Settings, sec_client: SecClient | None = None):
        """Initialize CompanyFacts client.

        Args:
            settings: Configuration
            sec_client: Existing SecClient instance (optional)
        """
        self.settings = settings
        self.sec_client = sec_client or SecClient(settings=settings)
        self._facts_cache: dict[tuple[str, str, str], list[CompanyFact]] = {}

    def __enter__(self) -> CompanyFactsClient:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        """Close HTTP client."""
        if hasattr(self.sec_client, "close"):
            self.sec_client.close()

    def get_company_facts(self, cik: str) -> dict[str, dict[str, Any]]:
        """Retrieve CompanyFacts for a CIK.

        Args:
            cik: 10-digit zero-padded CIK

        Returns:
            Dict mapping taxonomy → concept → facts list
        """
        cik = self.sec_client.normalize_cik(cik)
        cik_no_zeros = self.sec_client.cik_without_leading_zeros(cik)

        url = f"{self.settings.sec_base_data}/api/xbrl/companyfacts/CIK{cik_no_zeros}.json"
        facts_data = self.sec_client._get_json(url)

        return facts_data

    def get_company_concept(
        self, cik: str, taxonomy: str, concept: str
    ) -> dict[str, Any]:
        """Retrieve history for a single concept.

        Args:
            cik: 10-digit zero-padded CIK
            taxonomy: Taxonomy (e.g., 'us-gaap')
            concept: Concept name (e.g., 'Revenue')

        Returns:
            Dict with concept metadata and units/values
        """
        cik = self.sec_client.normalize_cik(cik)
        cik_no_zeros = self.sec_client.cik_without_leading_zeros(cik)

        url = (
            f"{self.settings.sec_base_data}/api/xbrl/"
            f"companyconcept/CIK{cik_no_zeros}/{taxonomy}/{concept}.json"
        )
        concept_data = self.sec_client._get_json(url)

        return concept_data
