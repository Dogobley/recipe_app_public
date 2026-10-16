"""Request tests for editing recipes and their ingredient formsets."""

from decimal import Decimal

import pytest
from django.urls import reverse

from calculator.models import Ingredient, Recipe, RecipeIngredient


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


def make_recipe() -> tuple[Recipe, RecipeIngredient, Ingredient, Ingredient]:
    recipe = Recipe.objects.create(name="Bread", weight_per_unit=Decimal("750.000"))
    flour = make_ingredient()
    sugar = make_ingredient(name="Sugar")
    recipe_ingredient = RecipeIngredient.objects.create(
        recipe=recipe, ingredient=flour, quantity=Decimal("250.000"), quantity_unit="g"
    )
    return recipe, recipe_ingredient, flour, sugar


def edit_data(recipe_ingredient: RecipeIngredient, **overrides: object) -> dict[str, str]:
    values = {
        "name": "Updated bread",
        "weight_per_unit": "800",
        "ingredients-TOTAL_FORMS": "2",
        "ingredients-INITIAL_FORMS": "1",
        "ingredients-MIN_NUM_FORMS": "0",
        "ingredients-MAX_NUM_FORMS": "1000",
        "ingredients-0-id": str(recipe_ingredient.pk),
        "ingredients-0-ingredient": str(recipe_ingredient.ingredient_id),
        "ingredients-0-quantity": "300",
        "ingredients-0-quantity_unit": "g",
        "ingredients-1-ingredient": "",
        "ingredients-1-quantity": "",
        "ingredients-1-quantity_unit": "",
    }
    values.update({key: str(value) for key, value in overrides.items()})
    return values


def test_recipe_edit_page_is_prepopulated_with_recipe_and_ingredient_rows(client) -> None:
    recipe, row, flour, _ = make_recipe()

    response = client.get(reverse("recipe-edit", args=[recipe.pk]))

    assert response.status_code == 200
    assert b"Edit recipe" in response.content
    assert b'value="Bread"' in response.content
    assert b'value="750.000"' in response.content
    assert f'name="ingredients-0-id" value="{row.pk}"'.encode() in response.content
    assert f'value="{flour.pk}" selected'.encode() in response.content
    assert b'value="250.000"' in response.content
    assert response.context["formset"].total_form_count() == 2
    assert b'id="add-ingredient-row"' in response.content
    assert b"data-remove-row" in response.content


def test_recipe_edit_updates_recipe_and_existing_row_then_redirects_with_message(client) -> None:
    recipe, row, _, _ = make_recipe()

    response = client.post(reverse("recipe-edit", args=[recipe.pk]), edit_data(row, **{
        "ingredients-0-quantity": "1.25", "ingredients-0-quantity_unit": "kg"
    }), follow=True)

    recipe.refresh_from_db()
    row.refresh_from_db()
    assert response.redirect_chain == [(reverse("recipe-detail", args=[recipe.pk]), 302)]
    assert b"Recipe updated successfully." in response.content
    assert recipe.name == "Updated bread"
    assert recipe.weight_per_unit == Decimal("800.000")
    assert row.quantity == Decimal("1.250")
    assert row.quantity_unit == "kg"


def test_recipe_edit_adds_a_new_row_and_can_delete_an_existing_row_without_deleting_ingredient(client) -> None:
    recipe, row, flour, sugar = make_recipe()
    data = edit_data(row, **{
        "ingredients-0-DELETE": "on",
        "ingredients-1-ingredient": sugar.pk,
        "ingredients-1-quantity": "25",
        "ingredients-1-quantity_unit": "g",
    })

    response = client.post(reverse("recipe-edit", args=[recipe.pk]), data)

    assert response.status_code == 302
    assert not RecipeIngredient.objects.filter(pk=row.pk).exists()
    assert Ingredient.objects.filter(pk=flour.pk).exists()
    assert list(recipe.ingredients.values_list("ingredient_id", "quantity", "quantity_unit")) == [
        (sugar.pk, Decimal("25.000"), "g")
    ]


def test_recipe_edit_rejects_invalid_data_and_rolls_back_all_changes(client) -> None:
    recipe, row, flour, sugar = make_recipe()
    data = edit_data(row, **{
        "name": "Should not save",
        "weight_per_unit": "0",
        "ingredients-0-DELETE": "on",
        "ingredients-1-ingredient": sugar.pk,
        "ingredients-1-quantity": "10",
        "ingredients-1-quantity_unit": "oz",
    })

    response = client.post(reverse("recipe-edit", args=[recipe.pk]), data)

    recipe.refresh_from_db()
    row.refresh_from_db()
    assert response.status_code == 200
    assert b"greater than or equal to 0.001" in response.content
    assert b"Select a valid choice." in response.content
    assert recipe.name == "Bread"
    assert recipe.weight_per_unit == Decimal("750.000")
    assert row.ingredient_id == flour.pk
    assert row.quantity == Decimal("250.000")
    assert not RecipeIngredient.objects.filter(recipe=recipe, ingredient=sugar).exists()


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"ingredients-0-ingredient": "", "ingredients-0-quantity": "", "ingredients-0-quantity_unit": ""}, b"Add at least one ingredient to the recipe."),
        ({"ingredients-TOTAL_FORMS": "2", "ingredients-1-ingredient": "__same__", "ingredients-1-quantity": "20", "ingredients-1-quantity_unit": "g"}, b"Each ingredient may only be used once in a recipe."),
    ],
)
def test_recipe_edit_rejects_no_active_or_duplicate_ingredients(client, overrides: dict[str, str], error: bytes) -> None:
    recipe, row, flour, _ = make_recipe()
    if overrides.get("ingredients-1-ingredient") == "__same__":
        overrides["ingredients-1-ingredient"] = str(flour.pk)

    response = client.post(reverse("recipe-edit", args=[recipe.pk]), edit_data(row, **overrides))

    assert response.status_code == 200
    assert error in response.content
    assert RecipeIngredient.objects.filter(recipe=recipe).count() == 1


def test_recipe_edit_ignores_blank_extra_rows_and_returns_404_without_mutation(client) -> None:
    recipe, row, _, _ = make_recipe()

    response = client.post(reverse("recipe-edit", args=[recipe.pk]), edit_data(row))
    assert response.status_code == 302
    assert RecipeIngredient.objects.filter(recipe=recipe).count() == 1

    response = client.post(reverse("recipe-edit", args=[999999]), edit_data(row))
    assert response.status_code == 404
    assert Recipe.objects.filter(pk=recipe.pk).exists()
    assert RecipeIngredient.objects.filter(pk=row.pk).exists()
