from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional


ZERO = Decimal("0.0000")
CENT = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def to_decimal(value: Any, default: Optional[Decimal] = ZERO) -> Decimal:
    if value is None or value == "":
        if default is None:
            raise ValueError("Decimal value is required")
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def q4(value: Any) -> Decimal:
    return to_decimal(value).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def q2(value: Any) -> Decimal:
    return to_decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def safe_divide(numerator: Any, denominator: Any) -> Optional[Decimal]:
    denominator_decimal = to_decimal(denominator)
    if denominator_decimal == 0:
        return None
    return q4(to_decimal(numerator) / denominator_decimal)


def parse_percentage(value: Any, default: Optional[Decimal] = ZERO) -> Decimal:
    if value is None or value == "":
        if default is None:
            raise ValueError("Percentage value is required")
        return default
    if isinstance(value, str):
        raw = value.strip().replace(",", "")
        if not raw:
            if default is None:
                raise ValueError("Percentage value is required")
            return default
        if raw.endswith("%"):
            return q4(Decimal(raw[:-1].strip()) / Decimal("100"))
        parsed = Decimal(raw)
    else:
        parsed = to_decimal(value)
    if abs(parsed) > 1:
        parsed = parsed / Decimal("100")
    return q4(parsed)
