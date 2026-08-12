from __future__ import annotations

import re

from accountant.domain.exceptions import AccountantError

_CIK_DIGITS = re.compile(r"^\d{1,10}$")


def normalize_cik(cik: str | int) -> str:
    """Return a 10-digit zero-padded CIK. Refuse non-numeric input."""
    if cik is None:
        raise AccountantError("CIK is required")
    raw = str(cik).strip()
    if raw.lower().startswith("cik"):
        raw = raw[3:]
    raw = raw.lstrip("0") or "0"
    if not _CIK_DIGITS.match(raw) and raw != "0":
        raise AccountantError(f"malformed CIK: {cik!r}")
    if not str(cik).strip().replace("CIK", "").replace("cik", "").isdigit():
        candidate = str(cik).strip()
        if candidate.lower().startswith("cik"):
            candidate = candidate[3:]
        if not candidate.isdigit():
            raise AccountantError(f"malformed CIK: {cik!r}")
    digits = str(cik).strip()
    if digits.lower().startswith("cik"):
        digits = digits[3:]
    if not digits.isdigit():
        raise AccountantError(f"malformed CIK: {cik!r}")
    if len(digits) > 10:
        raise AccountantError(f"malformed CIK: {cik!r}")
    return digits.zfill(10)


def cik_without_leading_zeros(cik: str | int) -> str:
    """CIK path segment used in EDGAR archive URLs."""
    return str(int(normalize_cik(cik)))
