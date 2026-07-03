from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional


def parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError as exc:
        raise ValueError(f"Invalid date: {value!r}") from exc


def require_date(value: Any, field_name: str = "date") -> date:
    parsed = parse_date(value)
    if parsed is None:
        raise ValueError(f"{field_name} is required")
    return parsed

