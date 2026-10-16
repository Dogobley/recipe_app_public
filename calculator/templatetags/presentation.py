"""Reusable, display-only Decimal formatting for server-rendered pages."""

from __future__ import annotations

from decimal import Decimal, DecimalException, ROUND_HALF_UP

from django import template


register = template.Library()

_CENT = Decimal("0.01")
_THOUSANDTH = Decimal("0.001")
_MISSING_VALUE = "—"


def _as_finite_decimal(value: object) -> Decimal | None:
    """Return a finite Decimal without routing values through float precision."""
    if value is None or isinstance(value, bool) or isinstance(value, float):
        return None
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (DecimalException, TypeError, ValueError):
        return None
    return decimal_value if decimal_value.is_finite() else None


def _round_for_display(value: object, quantum: Decimal) -> Decimal | None:
    """Round a valid value for display only, normalizing a possible negative zero."""
    decimal_value = _as_finite_decimal(value)
    if decimal_value is None:
        return None
    try:
        rounded = decimal_value.quantize(quantum, rounding=ROUND_HALF_UP)
    except DecimalException:
        return None
    return Decimal("0") if rounded == 0 else rounded


@register.filter(name="currency")
def format_currency(value: object) -> str:
    """Format a monetary value as COP with two ROUND_HALF_UP decimal places."""
    rounded = _round_for_display(value, _CENT)
    if rounded is None:
        return _MISSING_VALUE
    return f"COP ${rounded:.2f}"


@register.filter(name="weight")
def format_weight(value: object, unit: object) -> str:
    """Format a gram or kilogram value with its explicit unit label."""
    if unit not in {"g", "kg"}:
        return _MISSING_VALUE
    rounded = _round_for_display(value, _THOUSANDTH)
    if rounded is None:
        return _MISSING_VALUE
    number = "0" if rounded == 0 else f"{rounded:f}".rstrip("0").rstrip(".")
    return f"{number} {unit}"
