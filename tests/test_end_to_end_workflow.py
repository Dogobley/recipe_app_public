"""Cross-feature workflow tests driven entirely through Django's test client."""

from decimal import Decimal

import pytest
from django.urls import reverse

from calculator.models import Ingredient, Recipe, RecipeIngredient
from calculator.services.recipes import calculate_recipe


pytestmark = pytest.mark.django_db


def ingredient_data(**overrides: object) -> dict[str, str]:
    values: dict[str, object] = {
        "name": "Flour",
        "brand": "Mill House",
        "place_of_purchase": "Market",
        "package_weight": "1.250",
        "package_weight_unit": "kg",
        "package_price": "10.01",
    }
    values.update(overrides)
    return {key: str(value) for key, value in values.items()}


def recipe_data(
    flour: Ingredient,
    cocoa: Ingredient,
    **overrides: object,
) -> dict[str, str]:
    values: dict[str, object] = {
        "name": "Fractional cake",
        "weight_per_unit": "137.500",
        "ingredients-TOTAL_FORMS": "2",
        "ingredients-INITIAL_FORMS": "0",
        "ingredients-MIN_NUM_FORMS": "0",
        "ingredients-MAX_NUM_FORMS": "1000",
        "ingredients-0-ingredient": cocoa.pk,
        "ingredients-0-quantity": "12.500",
        "ingredients-0-quantity_unit": "g",
        "ingredients-1-ingredient": flour.pk,
        "ingredients-1-quantity": "0.125",
        "ingredients-1-quantity_unit": "kg",
    }
    values.update(overrides)
    return {key: str(value) for key, value in values.items()}


def edit_data(recipe: Recipe, flour_row: RecipeIngredient, cocoa_row: RecipeIngredient) -> dict[str, str]:
    return {
        "name": "Updated fractional cake",
        "weight_per_unit": "510.250",
        "ingredients-TOTAL_FORMS": "2",
        "ingredients-INITIAL_FORMS": "2",
        "ingredients-MIN_NUM_FORMS": "0",
        "ingredients-MAX_NUM_FORMS": "1000",
        "ingredients-0-id": str(cocoa_row.pk),
        "ingredients-0-ingredient": str(cocoa_row.ingredient_id),
        "ingredients-0-quantity": "0.500",
        "ingredients-0-quantity_unit": "kg",
        "ingredients-1-id": str(flour_row.pk),
        "ingredients-1-ingredient": str(flour_row.ingredient_id),
        "ingredients-1-quantity": "10.000",
        "ingredients-1-quantity_unit": "g",
    }


def create_workflow_recipe(client) -> tuple[Ingredient, Ingredient, Recipe]:
    flour_response = client.post(reverse("ingredient-create"), ingredient_data(), follow=True)
    assert flour_response.status_code == 200
    cocoa_response = client.post(
        reverse("ingredient-create"),
        ingredient_data(
            name="Cocoa",
            brand="Cacao Valley",
            place_of_purchase="Specialty shop",
            package_weight="250.000",
            package_weight_unit="g",
            package_price="1.01",
        ),
        follow=True,
    )
    assert cocoa_response.status_code == 200
    flour = Ingredient.objects.get(name="Flour")
    cocoa = Ingredient.objects.get(name="Cocoa")

    response = client.post(reverse("recipe-create"), recipe_data(flour, cocoa), follow=True)
    assert response.status_code == 200
    return flour, cocoa, Recipe.objects.get(name="Fractional cake")


def test_complete_workflow_scales_fractional_g_and_kg_ingredients(client) -> None:
    """A real browser-style workflow displays every scaled result consistently."""
    _, _, recipe = create_workflow_recipe(client)

    response = client.post(reverse("recipe-calculator"), {"recipe": recipe.pk, "units": "3"})

    assert response.status_code == 200
    for visible_value in (
        b"Calculation for Fractional cake",
        b"Requested units",
        b"3",
        b"Cost per unit",
        b"COP $1.05",
        b"Weight per unit",
        b"137.5 g",
        b"Cocoa",
        b"37.5 g",
        b"COP $0.15",
        b"Flour",
        b"0.375 kg",
        b"COP $3.00",
        b"Total cost",
        b"COP $3.15",
        b"Total weight",
        b"412.5 g",
    ):
        assert visible_value in response.content


def test_recipe_and_ingredient_edits_affect_later_calculations_without_mutating_composition(client) -> None:
    flour, cocoa, recipe = create_workflow_recipe(client)
    cocoa_row = RecipeIngredient.objects.get(recipe=recipe, ingredient=cocoa)
    flour_row = RecipeIngredient.objects.get(recipe=recipe, ingredient=flour)

    response = client.post(
        reverse("recipe-edit", args=[recipe.pk]), edit_data(recipe, flour_row, cocoa_row), follow=True
    )
    assert response.status_code == 200
    recipe.refresh_from_db()
    cocoa_row.refresh_from_db()
    flour_row.refresh_from_db()
    assert recipe.name == "Updated fractional cake"
    assert recipe.weight_per_unit == Decimal("510.250")
    assert (cocoa_row.quantity, cocoa_row.quantity_unit) == (Decimal("0.500"), "kg")
    assert (flour_row.quantity, flour_row.quantity_unit) == (Decimal("10.000"), "g")

    updated_response = client.post(reverse("recipe-calculator"), {"recipe": recipe.pk, "units": "2"})
    for visible_value in (b"Updated fractional cake", b"COP $2.10", b"1 kg", b"20 g", b"COP $4.04", b"COP $0.16", b"COP $4.20", b"1020 g"):
        assert visible_value in updated_response.content

    composition_before_price_edit = list(
        RecipeIngredient.objects.filter(recipe=recipe).order_by("pk").values_list(
            "ingredient_id", "quantity", "quantity_unit"
        )
    )
    price_edit = ingredient_data(package_price="20.01")
    response = client.post(reverse("ingredient-edit", args=[flour.pk]), price_edit, follow=True)
    assert response.status_code == 200
    flour.refresh_from_db()
    assert flour.package_price == Decimal("20.01")
    assert list(
        RecipeIngredient.objects.filter(recipe=recipe).order_by("pk").values_list(
            "ingredient_id", "quantity", "quantity_unit"
        )
    ) == composition_before_price_edit

    repriced_response = client.post(reverse("recipe-calculator"), {"recipe": recipe.pk, "units": "2"})
    assert b"COP $4.36" in repriced_response.content
    assert calculate_recipe(recipe, 2).total_ingredient_cost == Decimal("4.36016")


def test_referenced_ingredient_cannot_be_deleted_and_recipe_remains_calculable(client) -> None:
    flour, _, recipe = create_workflow_recipe(client)

    response = client.post(reverse("ingredient-delete", args=[flour.pk]), follow=True)

    assert response.status_code == 200
    assert b"cannot be deleted because it is used by a recipe" in response.content
    assert Ingredient.objects.filter(pk=flour.pk).exists()
    assert RecipeIngredient.objects.filter(recipe=recipe, ingredient=flour).exists()
    calculation_response = client.post(reverse("recipe-calculator"), {"recipe": recipe.pk, "units": "3"})
    assert calculation_response.status_code == 200
    assert b"COP $3.15" in calculation_response.content


def test_invalid_recipe_creation_and_edit_preserve_existing_records_with_visible_errors(client) -> None:
    flour, cocoa, recipe = create_workflow_recipe(client)
    recipe_count_before = Recipe.objects.count()
    row_count_before = RecipeIngredient.objects.count()

    invalid_creation = recipe_data(
        flour,
        cocoa,
        name="Rejected recipe",
        **{"ingredients-1-quantity": "0"},
    )
    response = client.post(reverse("recipe-create"), invalid_creation)
    assert response.status_code == 200
    assert b"greater than or equal to 0.001" in response.content
    assert Recipe.objects.count() == recipe_count_before
    assert RecipeIngredient.objects.count() == row_count_before

    cocoa_row = RecipeIngredient.objects.get(recipe=recipe, ingredient=cocoa)
    flour_row = RecipeIngredient.objects.get(recipe=recipe, ingredient=flour)
    original_recipe = (recipe.name, recipe.weight_per_unit)
    original_rows = list(
        RecipeIngredient.objects.filter(recipe=recipe).order_by("pk").values_list(
            "pk", "ingredient_id", "quantity", "quantity_unit"
        )
    )
    invalid_edit = edit_data(recipe, flour_row, cocoa_row)
    invalid_edit.update(
        {
            "name": "Should not persist",
            "weight_per_unit": "0",
            "ingredients-1-ingredient": str(cocoa.pk),
        }
    )
    response = client.post(reverse("recipe-edit", args=[recipe.pk]), invalid_edit)
    assert response.status_code == 200
    assert b"greater than or equal to 0.001" in response.content
    assert b"Each ingredient may only be used once in a recipe." in response.content
    recipe.refresh_from_db()
    assert (recipe.name, recipe.weight_per_unit) == original_recipe
    assert list(
        RecipeIngredient.objects.filter(recipe=recipe).order_by("pk").values_list(
            "pk", "ingredient_id", "quantity", "quantity_unit"
        )
    ) == original_rows


def test_calculator_rounds_half_up_for_display_while_retaining_domain_precision(client) -> None:
    ingredient_response = client.post(
        reverse("ingredient-create"),
        ingredient_data(name="Rounding spice", package_weight="100", package_weight_unit="g", package_price="1.00"),
    )
    assert ingredient_response.status_code == 302
    ingredient = Ingredient.objects.get(name="Rounding spice")
    response = client.post(
        reverse("recipe-create"),
        {
            "name": "Rounding recipe",
            "weight_per_unit": "0.500",
            "ingredients-TOTAL_FORMS": "1",
            "ingredients-INITIAL_FORMS": "0",
            "ingredients-MIN_NUM_FORMS": "0",
            "ingredients-MAX_NUM_FORMS": "1000",
            "ingredients-0-ingredient": ingredient.pk,
            "ingredients-0-quantity": "0.500",
            "ingredients-0-quantity_unit": "g",
        },
    )
    assert response.status_code == 302
    recipe = Recipe.objects.get(name="Rounding recipe")

    response = client.post(reverse("recipe-calculator"), {"recipe": recipe.pk, "units": "1"})
    calculation = calculate_recipe(recipe, 1)
    assert calculation.ingredient_results[0].ingredient_cost == Decimal("0.005")
    assert calculation.total_ingredient_cost == Decimal("0.005")
    assert b"COP $0.01" in response.content
