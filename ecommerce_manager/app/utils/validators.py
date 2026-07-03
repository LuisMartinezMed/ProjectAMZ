from __future__ import annotations

from decimal import Decimal
from typing import Any

from .money import to_decimal


class ValidationError(ValueError):
    pass


def require_text(value: Any, field_name: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValidationError(f"{field_name} is required")
    return text


def require_positive_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be a whole number") from exc
    if parsed <= 0:
        raise ValidationError(f"{field_name} must be greater than zero")
    return parsed


def require_non_negative_decimal(value: Any, field_name: str) -> Decimal:
    parsed = to_decimal(value)
    if parsed < 0:
        raise ValidationError(f"{field_name} cannot be negative")
    return parsed

