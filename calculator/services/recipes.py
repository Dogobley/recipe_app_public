"""Recipe scaling and cost aggregation domain services.

The service in this module deliberately has no HTTP, form, or template
dependencies.  It reads a recipe's persisted ingredient rows but never writes
calculation results back to the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from calculator.services.costs import calculate_ingredient_cost
from calculator.services.weights import normalize_weight

if TYPE_CHECKING:
    from calculator.models import Ingredient, Recipe


class InvalidUnitCountError(ValueError):
    """Raised when a requested recipe unit count is not a positive integer.

    Valid counts are Python ``int`` values greater than zero.  Booleans are
    rejected explicitly even though they are subclasses of ``int``.  Decimal,
    string, blank, fractional, and non-finite inputs are also rejected so the
    caller cannot accidentally request a partial recipe unit.
    """


@dataclass(frozen=True)
class RecipeIngredientResult:
    """The scaled, unrounded calculation result for one recipe ingredient."""

    ingredient: Ingredient
    scaled_quantity: Decimal
    unit: str
    normalized_weight_grams: Decimal
    ingredient_cost: Decimal

    @property
    def quantity(self) -> Decimal:
        """Return the scaled quantity using the stored ingredient unit."""
        return self.scaled_quantity

    @property
    def quantity_unit(self) -> str:
        """Return the stored unit for :attr:`scaled_quantity`."""
        return self.unit


@dataclass(frozen=True)
class RecipeCalculation:
    """The unrounded totals and ingredient rows for a recipe request."""

    ingredient_results: tuple[RecipeIngredientResult, ...]
    cost_per_unit: Decimal
    weight_per_unit: Decimal
    total_ingredient_cost: Decimal
    total_normalized_weight: Decimal

    @property
    def total_cost(self) -> Decimal:
        """Return the total ingredient cost for the requested units."""
        return self.total_ingredient_cost

    @property
    def total_weight(self) -> Decimal:
        """Return the aggregated ingredient weight in canonical grams."""
        return self.total_normalized_weight


def calculate_recipe(recipe: Recipe, unit_count: int) -> RecipeCalculation:
    """Scale ``recipe`` for a positive whole-number ``unit_count``.

    Each persisted recipe-ingredient row produces exactly one result row.  Its
    quantity stays in its stored unit while ``normalized_weight_grams`` and
    all recipe totals use grams.  Costs are calculated from current ingredient
    package data and retain the active :mod:`decimal` context precision; no
    display rounding is applied.

    A recipe with no ingredient rows returns an empty ``ingredient_results``
    tuple and zero-valued ingredient totals.  ``weight_per_unit`` remains the
    recipe's stored finished-product weight and is not derived from its
    ingredient rows.

    Raises:
        InvalidUnitCountError: If ``unit_count`` is not a positive Python
            integer.  See :class:`InvalidUnitCountError` for rejected inputs.
    """
    validated_unit_count = _validate_unit_count(unit_count)
    multiplier = Decimal(validated_unit_count)

    ingredient_results: list[RecipeIngredientResult] = []
    cost_per_unit = Decimal("0")
    total_ingredient_cost = Decimal("0")
    total_normalized_weight = Decimal("0")

    for recipe_ingredient in recipe.ingredients.select_related("ingredient").all():
        ingredient = recipe_ingredient.ingredient
        scaled_quantity = recipe_ingredient.quantity * multiplier
        normalized_weight_grams = normalize_weight(
            scaled_quantity, recipe_ingredient.quantity_unit
        )
        cost = calculate_ingredient_cost(
            ingredient.package_price,
            ingredient.package_weight,
            ingredient.package_weight_unit,
            scaled_quantity,
            recipe_ingredient.quantity_unit,
        ).requested_cost
        unscaled_cost = calculate_ingredient_cost(
            ingredient.package_price,
            ingredient.package_weight,
            ingredient.package_weight_unit,
            recipe_ingredient.quantity,
            recipe_ingredient.quantity_unit,
        ).requested_cost

        ingredient_results.append(
            RecipeIngredientResult(
                ingredient=ingredient,
                scaled_quantity=scaled_quantity,
                unit=recipe_ingredient.quantity_unit,
                normalized_weight_grams=normalized_weight_grams,
                ingredient_cost=cost,
            )
        )
        cost_per_unit += unscaled_cost
        total_ingredient_cost += cost
        total_normalized_weight += normalized_weight_grams

    return RecipeCalculation(
        ingredient_results=tuple(ingredient_results),
        cost_per_unit=cost_per_unit,
        weight_per_unit=recipe.weight_per_unit,
        total_ingredient_cost=total_ingredient_cost,
        total_normalized_weight=total_normalized_weight,
    )


def _validate_unit_count(unit_count: int) -> int:
    """Return a valid positive unit count or raise a domain-specific error."""
    if isinstance(unit_count, bool) or not isinstance(unit_count, int) or unit_count <= 0:
        raise InvalidUnitCountError("Unit count must be a positive whole number.")
    return unit_count
