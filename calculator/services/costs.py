"""Ingredient cost calculations expressed with :class:`decimal.Decimal`.

The functions in this module are domain services: they deliberately do not
depend on Django models, HTTP requests, or presentation formatting.  Weights
are normalized to grams before pricing and the returned values retain the
active Decimal context precision without display rounding.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from calculator.services.weights import DecimalInput, normalize_weight


class InvalidPackagePriceError(ValueError):
    """Raised when a package price is not a finite, positive decimal value.

    Prices may be supplied as ``Decimal`` instances, integers, or decimal
    strings.  Floats, booleans, blank strings, non-numeric values, NaN,
    infinity, zero, and negative values are invalid.  Invalid package and
    requested weights raise ``InvalidWeightError`` from ``weights``.
    """


@dataclass(frozen=True)
class IngredientCost:
    """The unrounded costs for one requested ingredient quantity.

    ``cost_per_gram`` is the package price divided by its normalized package
    weight. ``requested_cost`` is the normalized requested weight multiplied by
    that cost per gram. Neither value is display-rounded.
    """

    cost_per_gram: Decimal
    requested_cost: Decimal


def calculate_ingredient_cost(
    package_price: DecimalInput,
    package_weight: DecimalInput,
    package_weight_unit: str,
    requested_quantity: DecimalInput,
    requested_quantity_unit: str,
) -> IngredientCost:
    """Calculate unrounded costs for a requested amount of an ingredient.

    Both package and requested quantities accept only the exact ``"g"`` and
    ``"kg"`` units and are independently normalized to grams.  All valid
    arithmetic is Decimal arithmetic; no rounding or coercion is applied.

    Raises:
        InvalidPackagePriceError: If ``package_price`` is not a finite,
            positive supported decimal input.
        InvalidWeightError: If either quantity or unit is invalid. See
            :func:`calculator.services.weights.normalize_weight`.
    """
    decimal_package_price = _as_positive_package_price(package_price)
    package_weight_grams = normalize_weight(package_weight, package_weight_unit)
    requested_weight_grams = normalize_weight(requested_quantity, requested_quantity_unit)

    cost_per_gram = decimal_package_price / package_weight_grams
    return IngredientCost(
        cost_per_gram=cost_per_gram,
        requested_cost=requested_weight_grams * cost_per_gram,
    )


def _as_positive_package_price(package_price: DecimalInput) -> Decimal:
    """Validate and convert a supported package price to ``Decimal``."""
    if isinstance(package_price, bool) or isinstance(package_price, float):
        raise InvalidPackagePriceError(
            "Package price must be a decimal, integer, or decimal string."
        )

    try:
        decimal_package_price = Decimal(package_price)
    except (InvalidOperation, TypeError, ValueError):
        raise InvalidPackagePriceError("Package price must be a valid decimal value.") from None

    if not decimal_package_price.is_finite() or decimal_package_price <= 0:
        raise InvalidPackagePriceError(
            "Package price must be a finite positive decimal value."
        )

    return decimal_package_price
