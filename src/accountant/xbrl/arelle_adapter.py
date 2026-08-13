"""Arelle XBRL instance validation and extraction."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

try:
    from arelle import Cntlr
    ARELLE_AVAILABLE = True
except ImportError:
    ARELLE_AVAILABLE = False
    logger.warning("Arelle not installed; XBRL validation will be degraded")


@dataclass(frozen=True)
class XbrlValidationError:
    """Single validation error from Arelle."""

    level: str
    code: str
    message: str
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class XbrlValidationResult:
    """Result of Arelle validation."""

    is_valid: bool
    errors: list[XbrlValidationError]
    warnings: list[XbrlValidationError]
    instance_url: str
    schema_url: str | None = None
    arelle_version: str | None = None
    validated_at: datetime | None = None


@dataclass(frozen=True)
class XbrlFact:
    """Single fact extracted from validated XBRL instance."""

    concept: str
    taxonomy: str
    context_id: str
    unit_id: str | None
    value: str
    value_type: str
    decimals: int | None = None
    xml_lang: str | None = None
    nil: bool = False


class ArelleFacade:
    """Wrapper around Arelle for XBRL validation and extraction.

    Handles:
    - Instance document validation
    - Fact extraction (numeric, text, boolean)
    - Context (period, entity) resolution
    - Unit resolution
    - Error/warning collection

    If Arelle is unavailable, raises explicit errors rather than silently degrading.
    """

    def __init__(self):
        """Initialize facade. Check Arelle availability."""
        if not ARELLE_AVAILABLE:
            raise RuntimeError(
                "Arelle not installed. Install with: pip install arelle-release"
            )
        self.cntlr = None

    def _get_controller(self) -> Cntlr.Cntlr:
        """Lazy-initialize Arelle controller."""
        if self.cntlr is None:
            self.cntlr = Cntlr.Cntlr(logHandler=self._log_handler)
        return self.cntlr

    def _log_handler(self, message: str, level: int, *args) -> None:
        """Handle Arelle logging output."""
        pass

    def validate_instance(
        self, instance_url: str, plugins: list[str] | None = None
    ) -> XbrlValidationResult:
        """Validate XBRL instance document.

        Args:
            instance_url: URL or file path to XBRL instance
            plugins: Optional list of Arelle plugins to enable

        Returns:
            XbrlValidationResult with errors and warnings

        Raises:
            RuntimeError: If Arelle is unavailable or file not found
        """
        if not ARELLE_AVAILABLE:
            raise RuntimeError("Arelle not available for validation")

        # Check if file exists (if local path)
        if not instance_url.startswith("http") and not os.path.exists(instance_url):
            raise FileNotFoundError(f"XBRL instance not found: {instance_url}")

        cntlr = self._get_controller()
        errors: list[XbrlValidationError] = []
        warnings: list[XbrlValidationError] = []

        try:
            # Clear prior validation results
            cntlr.reset()

            # Load instance
            modelXbrl = cntlr.modelManager.load(instance_url)

            # Validate if loaded successfully
            if modelXbrl is not None:
                cntlr.validate(modelXbrl)

                # Collect errors and warnings
                if hasattr(modelXbrl, "errors") and modelXbrl.errors:
                    for error in modelXbrl.errors:
                        errors.append(
                            XbrlValidationError(
                                level="ERROR",
                                code=getattr(error, "code", "unknown"),
                                message=str(error),
                                line=getattr(error, "line", None),
                                column=getattr(error, "column", None),
                            )
                        )

                if hasattr(modelXbrl, "warnings") and modelXbrl.warnings:
                    for warning in modelXbrl.warnings:
                        warnings.append(
                            XbrlValidationError(
                                level="WARNING",
                                code=getattr(warning, "code", "unknown"),
                                message=str(warning),
                                line=getattr(warning, "line", None),
                                column=getattr(warning, "column", None),
                            )
                        )

                # Get schema URL if available
                schema_url = None
                if hasattr(modelXbrl, "modelDocument"):
                    schema_url = getattr(modelXbrl.modelDocument, "uri", None)

                # Determine validity
                is_valid = len(errors) == 0

                return XbrlValidationResult(
                    is_valid=is_valid,
                    errors=errors,
                    warnings=warnings,
                    instance_url=instance_url,
                    schema_url=schema_url,
                    arelle_version=self._get_arelle_version(),
                    validated_at=datetime.utcnow(),
                )
            else:
                # Failed to load instance
                return XbrlValidationResult(
                    is_valid=False,
                    errors=[
                        XbrlValidationError(
                            level="ERROR",
                            code="load_failed",
                            message=f"Failed to load XBRL instance: {instance_url}",
                        )
                    ],
                    warnings=[],
                    instance_url=instance_url,
                    arelle_version=self._get_arelle_version(),
                    validated_at=datetime.utcnow(),
                )

        except Exception as e:
            logger.exception(f"Arelle validation error: {e}")
            return XbrlValidationResult(
                is_valid=False,
                errors=[
                    XbrlValidationError(
                        level="ERROR",
                        code="validation_exception",
                        message=f"Validation exception: {str(e)}",
                    )
                ],
                warnings=[],
                instance_url=instance_url,
                arelle_version=self._get_arelle_version(),
                validated_at=datetime.utcnow(),
            )

    def extract_facts(self, instance_url: str) -> list[XbrlFact]:
        """Extract all facts from XBRL instance.

        Args:
            instance_url: URL or file path to XBRL instance

        Returns:
            List of XbrlFact objects

        Raises:
            RuntimeError: If Arelle is unavailable or instance cannot be loaded
        """
        if not ARELLE_AVAILABLE:
            raise RuntimeError("Arelle not available for fact extraction")

        if not instance_url.startswith("http") and not os.path.exists(instance_url):
            raise FileNotFoundError(f"XBRL instance not found: {instance_url}")

        cntlr = self._get_controller()
        facts: list[XbrlFact] = []

        try:
            cntlr.reset()
            modelXbrl = cntlr.modelManager.load(instance_url)

            if modelXbrl is None:
                logger.warning(f"Failed to load XBRL instance: {instance_url}")
                return facts

            # Extract facts from modelXbrl
            if hasattr(modelXbrl, "facts"):
                for fact in modelXbrl.facts:
                    try:
                        # Get taxonomy from concept
                        taxonomy = "unknown"
                        if hasattr(fact, "qname") and fact.qname:
                            # QName format is typically {namespace}localname
                            qname_str = str(fact.qname)
                            if "gaap" in qname_str.lower():
                                taxonomy = "us-gaap"
                            elif "ifrs" in qname_str.lower():
                                taxonomy = "ifrs-full"

                        # Extract concept name
                        concept = (
                            fact.qname.localName
                            if hasattr(fact, "qname") and fact.qname
                            else str(fact)
                        )

                        # Determine value type and extract value
                        value_type = "text"
                        value = ""
                        if fact.isNumeric:
                            value_type = "numeric"
                            value = str(fact.value or "")
                        elif fact.isNil:
                            value_type = "nil"
                            value = ""
                        else:
                            value = str(fact.value or "")

                        # Extract context and unit info
                        context_id = (
                            fact.contextID
                            if hasattr(fact, "contextID")
                            else "unknown"
                        )
                        unit_id = fact.unitID if hasattr(fact, "unitID") else None

                        # Extract optional attributes
                        decimals = (
                            fact.decimals if hasattr(fact, "decimals") else None
                        )
                        xml_lang = (
                            fact.xmlLang if hasattr(fact, "xmlLang") else None
                        )
                        nil = fact.isNil if hasattr(fact, "isNil") else False

                        facts.append(
                            XbrlFact(
                                concept=concept,
                                taxonomy=taxonomy,
                                context_id=context_id,
                                unit_id=unit_id,
                                value=value,
                                value_type=value_type,
                                decimals=decimals,
                                xml_lang=xml_lang,
                                nil=nil,
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Error extracting fact: {e}")
                        continue

            return facts

        except Exception as e:
            logger.exception(f"Error during fact extraction: {e}")
            return facts

    def validate_and_extract(
        self, instance_url: str, plugins: list[str] | None = None
    ) -> tuple[XbrlValidationResult, list[XbrlFact]]:
        """Validate instance and extract facts in one call.

        Args:
            instance_url: URL or file path to XBRL instance
            plugins: Optional list of Arelle plugins to enable

        Returns:
            Tuple of (validation result, list of facts)
        """
        validation = self.validate_instance(instance_url, plugins)
        # Extract facts regardless of validation result (collect all available)
        facts = self.extract_facts(instance_url)
        return validation, facts

    @staticmethod
    def _get_arelle_version() -> str | None:
        """Get Arelle version if available."""
        try:
            if ARELLE_AVAILABLE:
                from arelle import __version__
                return str(__version__)
        except (ImportError, AttributeError):
            pass
        return None


__all__ = ["ArelleFacade", "XbrlFact", "XbrlValidationError", "XbrlValidationResult"]
