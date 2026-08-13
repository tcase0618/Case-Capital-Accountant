"""Deterministic accounting policy extraction and change detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class PolicyChangeType(StrEnum):
    """Classification of detected accounting policy changes."""

    WORD_ORDER_ONLY = "WORD_ORDER_ONLY"  # Same words, different order
    ADDED_CLARIFICATION = "ADDED_CLARIFICATION"  # New detail/example added
    REMOVED_DETAIL = "REMOVED_DETAIL"  # Detail removed or simplified
    THRESHOLD_CHANGE = "THRESHOLD_CHANGE"  # Numeric threshold changed
    SCOPE_CHANGE = "SCOPE_CHANGE"  # Coverage expanded/reduced
    METHOD_CHANGE = "METHOD_CHANGE"  # Different method (e.g., FIFO vs LIFO)
    NO_CHANGE = "NO_CHANGE"  # Policies identical
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Can't compare


@dataclass(frozen=True)
class AccountingPolicy:
    """Single accounting policy extracted from filing."""

    company_id: str
    fiscal_year: int
    policy_name: str  # e.g., "Revenue Recognition", "Depreciation"
    raw_text: str  # Full extracted text from footnote
    normalized_text: str  # Whitespace/case normalized
    source_location: str  # "Note 1" or "Note 2"
    word_count: int
    extraction_status: str  # COMPLETE, PARTIAL, AMBIGUOUS
    warnings: list[str]


@dataclass(frozen=True)
class PolicyDiff:
    """Difference between two years' policies."""

    company_id: str
    policy_name: str
    prior_year: int
    current_year: int

    # Comparison
    prior_policy: AccountingPolicy
    current_policy: AccountingPolicy

    # Change detection
    change_type: PolicyChangeType
    is_material_change: bool

    # Similarity metrics
    exact_match: bool  # Identical strings
    token_similarity: float  # 0-1 scale (word-level overlap)
    edit_distance_ratio: float  # 0-1 scale (char-level similarity)
    added_tokens: list[str]  # New words in current
    removed_tokens: list[str]  # Deleted words from prior

    # Analysis
    change_summary: str  # Plain English description


class TokenDiffer:
    """
    Deterministic token-level comparison of text.

    Splits text into tokens (words), compares token sequences,
    calculates similarity metrics.
    """

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Split text into tokens (words, punctuation)."""
        if not text:
            return []
        tokens = text.lower().split()
        return tokens

    @staticmethod
    def token_similarity(tokens_a: list[str], tokens_b: list[str]) -> float:
        """
        Calculate Jaccard similarity between two token lists.

        Jaccard = |intersection| / |union|
        """
        if not tokens_a and not tokens_b:
            return 1.0  # Both empty = identical
        if not tokens_a or not tokens_b:
            return 0.0  # One empty, one not = dissimilar

        set_a = set(tokens_a)
        set_b = set(tokens_b)

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def edit_distance(text_a: str, text_b: str) -> int:
        """
        Calculate Levenshtein edit distance between two strings.

        Counts minimum insertions/deletions/substitutions to transform A → B.
        """
        len_a = len(text_a)
        len_b = len(text_b)

        # Create DP table
        dp = [[0] * (len_b + 1) for _ in range(len_a + 1)]

        # Initialize base cases
        for i in range(len_a + 1):
            dp[i][0] = i
        for j in range(len_b + 1):
            dp[0][j] = j

        # Fill DP table
        for i in range(1, len_a + 1):
            for j in range(1, len_b + 1):
                if text_a[i - 1] == text_b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i - 1][j],  # Delete
                        dp[i][j - 1],  # Insert
                        dp[i - 1][j - 1],  # Substitute
                    )

        return dp[len_a][len_b]

    @staticmethod
    def edit_distance_ratio(text_a: str, text_b: str) -> float:
        """
        Normalized edit distance (0-1 scale).

        0 = identical, 1 = completely different
        """
        max_len = max(len(text_a), len(text_b))
        if max_len == 0:
            return 0.0  # Both empty

        distance = TokenDiffer.edit_distance(text_a, text_b)
        return distance / max_len


class AccountingPolicyExtractor:
    """
    Extract accounting policies from filing text and detect changes.

    Core principle: Deterministic extraction + comparison (no LLM).
    """

    POLICY_KEYWORDS = {
        "Revenue Recognition": [
            "revenue",
            "recognition",
            "performance obligations",
            "transaction price",
        ],
        "Depreciation": [
            "depreciation",
            "useful life",
            "residual value",
            "straight-line",
        ],
        "Inventory": ["inventory", "lifo", "fifo", "weighted average", "lower of cost"],
        "Leases": [
            "lease",
            "rou asset",
            "asc 842",
            "operating lease",
            "finance lease",
        ],
        "Debt": ["debt", "borrowings", "effective interest", "amortization"],
        "Goodwill": ["goodwill", "impairment", "fair value"],
        "Income Taxes": ["income tax", "deferred tax", "effective tax rate"],
        "Stock Compensation": ["stock", "sbc", "equity compensation", "option"],
        "Pension": ["pension", "postretirement", "benefit obligation"],
        "Contingencies": ["contingent", "warranty", "claim"],
    }

    @staticmethod
    def extract_policies(
        raw_text: str,
        company_id: str,
        fiscal_year: int,
    ) -> dict[str, AccountingPolicy]:
        """
        Extract accounting policies from Note 1 or similar section.

        Input: Raw footnote text
        Output: Dict mapping policy name to AccountingPolicy objects
        """
        policies = {}
        warnings = []

        if not raw_text:
            warnings.append("Empty text provided for policy extraction")
            return policies

        # Normalize once
        normalized = raw_text.lower()

        # Find each policy section
        for policy_name, keywords in AccountingPolicyExtractor.POLICY_KEYWORDS.items():
            # Simple heuristic: policy exists if any keyword found
            has_policy = any(keyword in normalized for keyword in keywords)

            if has_policy:
                # Extract surrounding text (simplified; real impl would find section boundaries)
                policy_text = raw_text  # Placeholder; would extract specific section
                policy_normalized = policy_text.lower()
                word_count = len(policy_normalized.split())

                policy = AccountingPolicy(
                    company_id=company_id,
                    fiscal_year=fiscal_year,
                    policy_name=policy_name,
                    raw_text=policy_text,
                    normalized_text=policy_normalized,
                    source_location="Note 1",
                    word_count=word_count,
                    extraction_status="COMPLETE" if word_count > 20 else "PARTIAL",
                    warnings=[],
                )

                policies[policy_name] = policy

        if not policies:
            warnings.append("No accounting policies detected in text")

        return policies

    @staticmethod
    def compare_policies(
        prior_policy: AccountingPolicy,
        current_policy: AccountingPolicy,
    ) -> PolicyDiff:
        """
        Compare two years' accounting policies and detect changes.

        Input: Policies from prior year and current year
        Output: PolicyDiff with change classification and metrics
        """
        # Text comparison
        exact_match = prior_policy.normalized_text == current_policy.normalized_text

        # Token similarity
        prior_tokens = TokenDiffer.tokenize(prior_policy.normalized_text)
        current_tokens = TokenDiffer.tokenize(current_policy.normalized_text)
        token_sim = TokenDiffer.token_similarity(prior_tokens, current_tokens)

        # Edit distance
        edit_ratio = TokenDiffer.edit_distance_ratio(
            prior_policy.normalized_text, current_policy.normalized_text
        )

        # Token diff
        prior_set = set(prior_tokens)
        current_set = set(current_tokens)
        added = sorted(list(current_set - prior_set))
        removed = sorted(list(prior_set - current_set))

        # Change classification
        if exact_match:
            change_type = PolicyChangeType.NO_CHANGE
            is_material = False
            summary = "Policy unchanged from prior year"
        elif len(removed) > 0 and len(added) == 0:
            change_type = PolicyChangeType.REMOVED_DETAIL
            is_material = True
            summary = f"Policy simplified: removed {len(removed)} terms"
        elif len(added) > 0 and len(removed) == 0:
            change_type = PolicyChangeType.ADDED_CLARIFICATION
            is_material = len(added) > 5  # Material if > 5 terms added
            summary = f"Policy clarified: added {len(added)} terms"
        elif token_sim > 0.8:
            change_type = PolicyChangeType.WORD_ORDER_ONLY
            is_material = False
            summary = "Policy reworded; substance unchanged"
        elif (
            "threshold" in prior_policy.normalized_text
            or "threshold" in current_policy.normalized_text
        ):
            change_type = PolicyChangeType.THRESHOLD_CHANGE
            is_material = True
            summary = "Numeric threshold changed"
        else:
            change_type = PolicyChangeType.SCOPE_CHANGE
            is_material = True
            summary = "Policy scope or method changed"

        return PolicyDiff(
            company_id=prior_policy.company_id,
            policy_name=prior_policy.policy_name,
            prior_year=prior_policy.fiscal_year,
            current_year=current_policy.fiscal_year,
            prior_policy=prior_policy,
            current_policy=current_policy,
            change_type=change_type,
            is_material_change=is_material,
            exact_match=exact_match,
            token_similarity=token_sim,
            edit_distance_ratio=edit_ratio,
            added_tokens=added,
            removed_tokens=removed,
            change_summary=summary,
        )

    @staticmethod
    def detect_policy_changes(
        prior_policies: dict[str, AccountingPolicy],
        current_policies: dict[str, AccountingPolicy],
    ) -> list[PolicyDiff]:
        """
        Compare entire policy set across two years and identify changes.

        Input: Policies from two years
        Output: List of PolicyDiff objects (one per policy)
        """
        diffs = []

        # Compare policies present in both years
        for policy_name in prior_policies:
            if policy_name in current_policies:
                diff = AccountingPolicyExtractor.compare_policies(
                    prior_policies[policy_name],
                    current_policies[policy_name],
                )
                diffs.append(diff)

        # New policies (in current but not prior)
        for policy_name in current_policies:
            if policy_name not in prior_policies:
                # Synthetic diff showing new policy
                current = current_policies[policy_name]
                diff = PolicyDiff(
                    company_id=current.company_id,
                    policy_name=policy_name,
                    prior_year=current.fiscal_year - 1,
                    current_year=current.fiscal_year,
                    prior_policy=None,  # type: ignore
                    current_policy=current,
                    change_type=PolicyChangeType.ADDED_CLARIFICATION,
                    is_material_change=True,
                    exact_match=False,
                    token_similarity=0.0,
                    edit_distance_ratio=1.0,
                    added_tokens=list(set(current.normalized_text.split())),
                    removed_tokens=[],
                    change_summary=f"New policy: {policy_name}",
                )
                diffs.append(diff)

        return diffs

    @staticmethod
    def summarize_changes(diffs: list[PolicyDiff]) -> dict[str, int]:
        """
        Count policy changes by type.

        Returns dict mapping change type to count.
        """
        summary: dict[str, int] = {
            "NO_CHANGE": 0,
            "WORD_ORDER_ONLY": 0,
            "ADDED_CLARIFICATION": 0,
            "REMOVED_DETAIL": 0,
            "THRESHOLD_CHANGE": 0,
            "SCOPE_CHANGE": 0,
            "METHOD_CHANGE": 0,
            "MATERIAL_CHANGES": 0,
        }

        for diff in diffs:
            change_type_str = diff.change_type.value
            summary[change_type_str] = summary.get(change_type_str, 0) + 1

            if diff.is_material_change:
                summary["MATERIAL_CHANGES"] += 1

        return summary
