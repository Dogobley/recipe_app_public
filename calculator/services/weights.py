"""Weight normalization utilities used by calculation services.

All calculations use grams as their canonical weight unit.  These utilities are
deliberately independent of Django so they can be used by any interface.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Union


DecimalInput = Union[Decimal, int, str]


class InvalidWeightError(ValueError):
    """Raised when a weight quantity or unit is not a valid positive decimal.

    Valid units are exactly ``"g"`` and ``"kg"``.  Quantities must be finite,
    positive decimal values; values such as blank strings, NaN, infinity,
    booleans, and floats are rejected to keep binary floating-point values out
    of domain calculations.
    """


_GRAMS_PER_KILOGRAM = Decimal("1000")
_SUPPORTED_UNITS = frozenset({"g", "kg"})


def normalize_weight(quantity: DecimalInput, unit: str) -> Decimal:
    """Return a positive ``quantity`` expressed in canonical grams.

    ``quantity`` may be a :class:`~decimal.Decimal`, integer, or decimal string.
    The accepted unit values are case-sensitive: only ``"g"`` and ``"kg"``.
    No rounding is applied to a valid result.

    Raises:
        InvalidWeightError: If the quantity is not a finite positive decimal or
            the unit is unsupported.
    """
    if not isinstance(unit, str) or unit not in _SUPPORTED_UNITS:
        raise InvalidWeightError("Weight unit must be exactly 'g' or 'kg'.")

    decimal_quantity = _as_positive_decimal(quantity)
    if unit == "g":
        return decimal_quantity
    return decimal_quantity * _GRAMS_PER_KILOGRAM


def _as_positive_decimal(quantity: DecimalInput) -> Decimal:
    """Validate and convert a supported quantity input to ``Decimal``."""
    if isinstance(quantity, bool) or isinstance(quantity, float):
        raise InvalidWeightError("Weight quantity must be a decimal, integer, or decimal string.")

    try:
        decimal_quantity = Decimal(quantity)
    except (InvalidOperation, TypeError, ValueError):
        raise InvalidWeightError("Weight quantity must be a valid decimal value.") from None

    if not decimal_quantity.is_finite() or decimal_quantity <= 0:
        raise InvalidWeightError("Weight quantity must be a finite positive decimal value.")

    return decimal_quantity
