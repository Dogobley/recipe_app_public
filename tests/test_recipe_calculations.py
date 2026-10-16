"""Tests for recipe scaling and aggregation domain calculations."""

from decimal import Decimal, localcontext

import pytest

from calculator.models import Ingredient, Recipe, RecipeIngredient
from calculator.services.recipes import InvalidUnitCountError, calculate_recipe


pytestmark = pytest.mark.django_db


def make_ingredient(**overrides: object) -> Ingredient:
    values: dict[str, object] = {
        "name": "Flour",
        "brand": "Mill House",
        "place_of_purchase": "Market",
        "package_weight": Decimal("1.000"),
        "package_weight_unit": "kg",
        "package_price": Decimal("4.75"),
    }
    values.update(overrides)
    return Ingredient.objects.create(**values)


def make_recipe(**overrides: object) -> Recipe:
    values: dict[str, object] = {"name": "Bread", "weight_per_unit": Decimal("750.000")}
    values.update(overrides)
    return Recipe.objects.create(**values)


def add_ingredient(recipe: Recipe, ingredient: Ingredient, quantity: str, unit: str) -> RecipeIngredient:
    return RecipeIngredient.objects.create(
        recipe=recipe,
        ingredient=ingredient,
        quantity=Decimal(quantity),
        quantity_unit=unit,
    )


def test_calculate_recipe_returns_one_scaled_row_and_unscaled_totals_for_one_unit() -> None:
    recipe = make_recipe(weight_per_unit=Decimal("500.000"))
    flour = make_ingredient(package_price=Decimal("6.00"))
    add_ingredient(recipe, flour, "250.000", "g")

    result = calculate_recipe(recipe, 1)

    assert len(result.ingredient_results) == 1
    row = result.ingredient_results[0]
    assert row.ingredient == flour
    assert row.scaled_quantity == Decimal("250.000")
    assert row.unit == "g"
    assert row.normalized_weight_grams == Decimal("250.000")
    assert row.ingredient_cost == Decimal("1.500000")
    assert result.cost_per_unit == Decimal("1.500000")
    assert result.weight_per_unit == Decimal("500.000")
    assert result.total_ingredient_cost == Decimal("1.500000")
    assert result.total_normalized_weight == Decimal("250.000")


def test_calculate_recipe_scales_each_row_and_total_for_many_units() -> None:
    recipe = make_recipe()
    flour = make_ingredient(name="Flour", package_price=Decimal("6.00"))
    yeast = make_ingredient(
        name="Yeast", package_weight=Decimal("100.000"), package_weight_unit="g", package_price=Decimal("2.50")
    )
    add_ingredient(recipe, flour, "250.000", "g")
    add_ingredient(recipe, yeast, "10.000", "g")

    result = calculate_recipe(recipe, 3)

    assert [row.ingredient for row in result.ingredient_results] == [flour, yeast]
    assert [row.scaled_quantity for row in result.ingredient_results] == [
        Decimal("750.000"), Decimal("30.000")
    ]
    assert [row.ingredient_cost for row in result.ingredient_results] == [
        Decimal("4.500000"), Decimal("0.75000")
    ]
    assert result.cost_per_unit == Decimal("1.750000")
    assert result.total_ingredient_cost == Decimal("5.250000")
    assert result.total_normalized_weight == Decimal("780.000")


def test_calculate_recipe_aggregates_mixed_quantity_units_in_grams() -> None:
    recipe = make_recipe()
    flour = make_ingredient(name="Flour")
    water = make_ingredient(name="Water", brand="Spring", package_price=Decimal("1.00"))
    add_ingredient(recipe, flour, "0.250", "kg")
    add_ingredient(recipe, water, "500.000", "g")

    result = calculate_recipe(recipe, 2)

    assert [row.unit for row in result.ingredient_results] == ["kg", "g"]
    assert [row.normalized_weight_grams for row in result.ingredient_results] == [
        Decimal("500.000"), Decimal("1000.000")
    ]
    assert result.total_normalized_weight == Decimal("1500.000")


def test_calculate_recipe_retains_decimal_precision_without_display_rounding() -> None:
    recipe = make_recipe()
    ingredient = make_ingredient(
        package_weight=Decimal("3.000"), package_weight_unit="g", package_price=Decimal("10.12")
    )
    add_ingredient(recipe, ingredient, "0.123", "g")

    with localcontext() as context:
        context.prec = 40
        result = calculate_recipe(recipe, 7)
        expected_cost = Decimal("0.123") * Decimal("7") * Decimal("10.12") / Decimal("3.000")

    row = result.ingredient_results[0]
    assert row.ingredient_cost == expected_cost
    assert result.cost_per_unit == Decimal("0.123") * Decimal("10.12") / Decimal("3.000")
    assert all(
        isinstance(value, Decimal)
        for value in (
            row.scaled_quantity,
            row.normalized_weight_grams,
            row.ingredient_cost,
            result.cost_per_unit,
            result.weight_per_unit,
            result.total_ingredient_cost,
            result.total_normalized_weight,
        )
    )


def test_calculate_recipe_returns_zero_ingredient_totals_for_an_empty_recipe() -> None:
    recipe = make_recipe()

    result = calculate_recipe(recipe, 4)

    assert result.ingredient_results == ()
    assert result.cost_per_unit == Decimal("0")
    assert result.total_ingredient_cost == Decimal("0")
    assert result.total_normalized_weight == Decimal("0")
    assert result.weight_per_unit == Decimal("750.000")


@pytest.mark.parametrize(
    "unit_count",
    [
        0,
        -1,
        1.0,
        1.5,
        Decimal("1"),
        Decimal("1.5"),
        Decimal("NaN"),
        "1",
        "one",
        "",
        " ",
        None,
        True,
        False,
        [],
        {},
    ],
)
def test_calculate_recipe_rejects_non_positive_or_non_whole_unit_counts(unit_count: object) -> None:
    with pytest.raises(InvalidUnitCountError, match="positive whole number"):
        calculate_recipe(make_recipe(), unit_count)  # type: ignore[arg-type]
