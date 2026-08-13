"""Deterministic filing text parser for extracting normalized accounting text."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class TextSourceType(StrEnum):
    """Origin of text content."""

    ITEM_1A_RISK_FACTORS = "ITEM_1A_RISK_FACTORS"
    ITEM_7_MD_A = "ITEM_7_MD_A"
    ITEM_8_FINANCIAL_STATEMENTS = "ITEM_8_FINANCIAL_STATEMENTS"
    NOTE_1_ACCOUNTING_POLICIES = "NOTE_1_ACCOUNTING_POLICIES"
    NOTE_2_REVENUE = "NOTE_2_REVENUE"
    NOTE_3_LEASES = "NOTE_3_LEASES"
    NOTE_5_DEBT = "NOTE_5_DEBT"
    NOTE_7_ACQUISITIONS = "NOTE_7_ACQUISITIONS"
    NOTE_8_GOODWILL_IMPAIRMENT = "NOTE_8_GOODWILL_IMPAIRMENT"
    NOTE_10_INCOME_TAXES = "NOTE_10_INCOME_TAXES"
    NOTE_15_CONTINGENCIES = "NOTE_15_CONTINGENCIES"
    NOTE_16_SUBSEQUENT = "NOTE_16_SUBSEQUENT"
    FOOTNOTE_REFERENCE = "FOOTNOTE_REFERENCE"
    OTHER_DISCLOSURE = "OTHER_DISCLOSURE"


@dataclass(frozen=True)
class NormalizedSentence:
    """Single normalized sentence with source tracking."""

    original_text: str  # Raw sentence from filing
    normalized_text: str  # Whitespace normalized, lowercase
    source: TextSourceType
    source_path: str  # Filing location (e.g., "NOTE_1" or "MD&A")
    sentence_index: int  # Position in document
    word_count: int  # Number of words for filtering
    extraction_status: str  # CLEAN, HAS_TABLES, HAS_XBRL, AMBIGUOUS


@dataclass(frozen=True)
class FilingText:
    """Complete normalized filing text with structure."""

    company_id: str
    fiscal_year: int
    fiscal_quarter: int | None

    # Text organization
    title: str  # "Form 10-K" or "Form 10-Q"
    submission_date: str  # YYYY-MM-DD

    # Parsed sections
    sentences: list[NormalizedSentence]  # All normalized sentences
    total_sections: int  # Number of distinct sections parsed
    total_words: int  # Total word count

    # Quality metrics
    coverage_pct: float  # % of filing text successfully parsed (0-100)
    has_tables: bool  # Filing contains embedded tables
    has_xbrl_tags: bool  # XBRL markup detected
    encoding: str  # Character encoding used (UTF-8 typical)

    # Metadata
    extraction_status: str  # COMPLETE, PARTIAL, FAILED
    warnings: list[str]


class FilingTextParser:
    """
    Deterministic filing text parser for extracting and normalizing text content.

    Core principle: Extract raw text from SEC filings and normalize for
    downstream analysis (no LLM, no semantic interpretation).
    """

    SENTENCE_SPLIT_DELIMITERS = {".": 1.0, "?": 1.0, "!": 1.0}  # Common sentence ends
    MIN_SENTENCE_LENGTH = 3  # Words; shorter = noise
    MAX_SENTENCE_LENGTH = 200  # Words; longer = complex/tables

    @staticmethod
    def split_into_sentences(text: str) -> list[str]:
        """
        Split text into sentences using deterministic delimiters.

        Handles common cases:
        - Period followed by space and capital letter (new sentence)
        - Question marks and exclamation points
        - Abbreviations (Dr., Inc., etc.) — skipped for now
        """
        if not text:
            return []

        sentences = []
        current = []

        for char in text:
            current.append(char)

            if char in FilingTextParser.SENTENCE_SPLIT_DELIMITERS:
                sentence = "".join(current).strip()
                if sentence:
                    sentences.append(sentence)
                current = []

        if current:
            remaining = "".join(current).strip()
            if remaining:
                sentences.append(remaining)

        return sentences

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text for comparison: lowercase, compress whitespace.

        Not removing words or stemming (deterministic only).
        """
        if not text:
            return ""

        # Compress multiple spaces/tabs/newlines into single space
        normalized = " ".join(text.split())

        # Lowercase for comparison
        normalized = normalized.lower()

        # Remove common XBRL tags (e.g., <ix:nonfraction>123</ix:nonfraction>)
        # Keep original structure for now; tag removal in separate step

        return normalized

    @staticmethod
    def parse_filing_text(
        raw_text: str,
        company_id: str,
        fiscal_year: int,
        source_type: TextSourceType = TextSourceType.ITEM_8_FINANCIAL_STATEMENTS,
        fiscal_quarter: int | None = None,
    ) -> FilingText:
        """
        Parse and normalize filing text into structured NormalizedSentence objects.

        Input: Raw text from SEC filing
        Output: FilingText with normalized sentences, metrics, quality assessment
        """
        warnings = []

        # Step 1: Split into sentences
        raw_sentences = FilingTextParser.split_into_sentences(raw_text)

        if not raw_sentences:
            warnings.append("No sentences extracted from text")
            return FilingText(
                company_id=company_id,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                title="UNKNOWN",
                submission_date="",
                sentences=[],
                total_sections=0,
                total_words=0,
                coverage_pct=0.0,
                has_tables=False,
                has_xbrl_tags=False,
                encoding="UTF-8",
                extraction_status="FAILED",
                warnings=warnings,
            )

        # Step 2: Normalize each sentence
        normalized_sentences = []
        total_word_count = 0

        for idx, raw_sent in enumerate(raw_sentences):
            normalized = FilingTextParser.normalize_text(raw_sent)
            word_count = len(normalized.split())

            # Quality checks
            status = "CLEAN"
            if word_count < FilingTextParser.MIN_SENTENCE_LENGTH:
                status = "AMBIGUOUS"  # Too short; likely fragment or table
                warnings.append(f"Sentence {idx} too short: {word_count} words")
            elif word_count > FilingTextParser.MAX_SENTENCE_LENGTH:
                status = "HAS_TABLES"  # Likely table or complex structure
                warnings.append(f"Sentence {idx} too long: {word_count} words")

            # XBRL tag detection
            if "<ix:" in raw_sent or "<ixt:" in raw_sent:
                status = "HAS_XBRL"

            sent_obj = NormalizedSentence(
                original_text=raw_sent,
                normalized_text=normalized,
                source=source_type,
                source_path=source_type.value,
                sentence_index=idx,
                word_count=word_count,
                extraction_status=status,
            )

            normalized_sentences.append(sent_obj)
            total_word_count += word_count

        # Step 3: Calculate coverage
        total_raw_words = len(raw_text.split())
        coverage = (total_word_count / total_raw_words * 100) if total_raw_words > 0 else 0

        # Step 4: Detect tables and XBRL
        has_tables = any(s.extraction_status == "HAS_TABLES" for s in normalized_sentences)
        has_xbrl = any(s.extraction_status == "HAS_XBRL" for s in normalized_sentences)

        # Determine extraction status
        if len(normalized_sentences) == 0:
            extraction_status = "FAILED"
        elif coverage < 50:
            extraction_status = "PARTIAL"
        else:
            extraction_status = "COMPLETE"

        return FilingText(
            company_id=company_id,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            title="Form 10-K",  # Default; could be parsed from text
            submission_date="",
            sentences=normalized_sentences,
            total_sections=1,  # Could count distinct source_path values
            total_words=total_word_count,
            coverage_pct=coverage,
            has_tables=has_tables,
            has_xbrl_tags=has_xbrl,
            encoding="UTF-8",
            extraction_status=extraction_status,
            warnings=warnings,
        )

    @staticmethod
    def filter_sentences(
        filing_text: FilingText,
        min_words: int = 5,
        max_words: int = 150,
        source_type: TextSourceType | None = None,
    ) -> list[NormalizedSentence]:
        """
        Filter sentences by length and source type for downstream analysis.

        Use case: Only analyze sentences of reasonable length and from specific sections.
        """
        filtered = []

        for sent in filing_text.sentences:
            # Length filter
            if sent.word_count < min_words or sent.word_count > max_words:
                continue

            # Source type filter
            if source_type is not None and sent.source != source_type:
                continue

            # Quality filter (skip XBRL-heavy or table sentences)
            if sent.extraction_status == "HAS_TABLES":
                continue

            filtered.append(sent)

        return filtered

    @staticmethod
    def extract_accounting_language(filing_text: FilingText) -> dict[str, list[str]]:
        """
        Extract sentences by accounting topic (rough categorization).

        Returns dict mapping topic to list of normalized sentences.
        """
        topics = {
            "revenue_recognition": [],
            "leases": [],
            "debt": [],
            "acquisitions": [],
            "goodwill": [],
            "income_taxes": [],
            "pension": [],
            "stock_compensation": [],
            "derivatives": [],
            "contingencies": [],
        }

        # Topic keywords (deterministic matching)
        keyword_map = {
            "revenue_recognition": [
                "revenue",
                "recognition",
                "performance obligations",
                "transaction price",
            ],
            "leases": ["lease", "rou asset", "asc 842", "operating lease", "finance lease"],
            "debt": ["debt", "borrowings", "notes payable", "bond", "credit facility"],
            "acquisitions": ["acquisition", "business combination", "purchase price allocation"],
            "goodwill": ["goodwill", "impairment", "fair value"],
            "income_taxes": ["income tax", "deferred tax", "tax rate", "effective tax"],
            "pension": ["pension", "retirement", "postretirement", "benefit obligation"],
            "stock_compensation": ["stock", "sbc", "equity compensation", "option", "rsu"],
            "derivatives": ["derivative", "hedge", "fair value"],
            "contingencies": ["contingent", "lawsuit", "claim", "warranty"],
        }

        for sent in filing_text.sentences:
            normalized = sent.normalized_text
            for topic, keywords in keyword_map.items():
                if any(keyword in normalized for keyword in keywords):
                    topics[topic].append(normalized)
                    break  # Assign to first matching topic

        return topics
