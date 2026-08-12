from __future__ import annotations

from datetime import UTC, date, datetime


def parse_date(value: str | None) -> date | None:
    """Parse an SEC date. Empty or missing becomes None — never guessed."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an SEC timestamp. Empty or missing becomes None — never guessed."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def is_amendment(form_type: str | None) -> bool:
    if not form_type:
        return False
    return "/A" in form_type.upper()


def column_at(block: dict, name: str, index: int):
    values = block.get(name)
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]
