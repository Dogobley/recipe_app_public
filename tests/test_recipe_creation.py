"""Request and form tests for creating recipes with ingredient formsets."""

from decimal import Decimal

import pytest
from django.urls import reverse

from calculator.forms import RecipeIngredientFormSet
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


def creation_data(ingredient: Ingredient, **overrides: object) -> dict[str, str]:
    values = {
        "name": "Bread",
        "weight_per_unit": "750",
        "ingredients-TOTAL_FORMS": "1",
        "ingredients-INITIAL_FORMS": "0",
        "ingredients-MIN_NUM_FORMS": "0",
        "ingredients-MAX_NUM_FORMS": "1000",
        "ingredients-0-ingredient": str(ingredient.pk),
        "ingredients-0-quantity": "250",
        "ingredients-0-quantity_unit": "g",
    }
    values.update({key: str(value) for key, value in overrides.items()})
    return values


def test_recipe_create_page_has_recipe_fields_initial_row_and_dynamic_row_contract(client) -> None:
    ingredient = make_ingredient()

    response = client.get(reverse("recipe-create"))

    assert response.status_code == 200
    assert b'name="name"' in response.content
    assert b'name="weight_per_unit"' in response.content
    assert b'name="ingredients-0-ingredient"' in response.content
    assert str(ingredient.pk).encode() in response.content
    assert b'name="ingredients-0-quantity"' in response.content
    assert b'name="ingredients-0-quantity_unit"' in response.content
    assert b'id="id_ingredients-TOTAL_FORMS"' in response.content
    assert b'id="empty-ingredient-form"' in response.content
    assert b"__prefix__" in response.content
    assert b'id="add-ingredient-row"' in response.content
    assert b"data-remove-row" in response.content
    assert b'input[name$="-DELETE"]' in response.content


def test_valid_recipe_creation_saves_all_rows_once_and_redirects_with_message(client) -> None:
    flour = make_ingredient()
    sugar = make_ingredient(name="Sugar")
    data = creation_data(
        flour,
        **{
            "ingredients-TOTAL_FORMS": "2",
            "ingredients-1-ingredient": sugar.pk,
            "ingredients-1-quantity": "1.5",
            "ingredients-1-quantity_unit": "kg",
        },
    )

    response = client.post(reverse("recipe-create"), data, follow=True)

    recipe = Recipe.objects.get()
    assert response.redirect_chain == [(reverse("recipe-detail", args=[recipe.pk]), 302)]
    assert b"Recipe added successfully." in response.content
    assert recipe.name == "Bread"
    assert recipe.weight_per_unit == Decimal("750.000")
    assert list(recipe.ingredients.values_list("ingredient", "quantity", "quantity_unit")) == [
        (flour.pk, Decimal("250.000"), "g"),
        (sugar.pk, Decimal("1.500"), "kg"),
    ]


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("name", "", b"This field is required."),
        ("weight_per_unit", "0", b"greater than or equal to 0.001"),
        ("weight_per_unit", "nope", b"Enter a number."),
        ("ingredients-0-ingredient", "", b"This field is required."),
        ("ingredients-0-quantity", "0", b"greater than or equal to 0.001"),
        ("ingredients-0-quantity", "nope", b"Enter a number."),
        ("ingredients-0-quantity_unit", "oz", b"Select a valid choice."),
    ],
)
def test_invalid_recipe_creation_shows_relevant_error_and_saves_nothing(
    client, field: str, value: str, error: bytes
) -> None:
    ingredient = make_ingredient()

    response = client.post(reverse("recipe-create"), creation_data(ingredient, **{field: value}))

    assert response.status_code == 200
    assert error in response.content
    assert Recipe.objects.count() == 0
    assert RecipeIngredient.objects.count() == 0


def test_duplicate_active_ingredients_show_formset_error_and_save_nothing(client) -> None:
    ingredient = make_ingredient()
    data = creation_data(
        ingredient,
        **{
            "ingredients-TOTAL_FORMS": "2",
            "ingredients-1-ingredient": ingredient.pk,
            "ingredients-1-quantity": "25",
            "ingredients-1-quantity_unit": "g",
        },
    )

    response = client.post(reverse("recipe-create"), data)

    assert response.status_code == 200
    assert b"Each ingredient may only be used once in a recipe." in response.content
    assert Recipe.objects.count() == 0
    assert RecipeIngredient.objects.count() == 0


def test_blank_extra_row_is_ignored_but_no_completed_rows_is_rejected(client) -> None:
    ingredient = make_ingredient()
    data = creation_data(
        ingredient,
        **{
            "ingredients-TOTAL_FORMS": "2",
            "ingredients-1-ingredient": "",
            "ingredients-1-quantity": "",
            "ingredients-1-quantity_unit": "",
        },
    )

    response = client.post(reverse("recipe-create"), data)

    assert response.status_code == 302
    assert Recipe.objects.count() == 1
    assert RecipeIngredient.objects.count() == 1

    response = client.post(
        reverse("recipe-create"),
        creation_data(
            ingredient,
            **{
                "ingredients-0-ingredient": "",
                "ingredients-0-quantity": "",
                "ingredients-0-quantity_unit": "",
            },
        ),
    )
    assert response.status_code == 200
    assert b"Add at least one ingredient to the recipe." in response.content
    assert Recipe.objects.count() == 1
    assert RecipeIngredient.objects.count() == 1


def test_deleted_new_row_is_not_saved(client) -> None:
    flour = make_ingredient()
    sugar = make_ingredient(name="Sugar")
    data = creation_data(
        flour,
        **{
            "ingredients-TOTAL_FORMS": "2",
            "ingredients-1-ingredient": sugar.pk,
            "ingredients-1-quantity": "25",
            "ingredients-1-quantity_unit": "g",
            "ingredients-1-DELETE": "on",
        },
    )

    response = client.post(reverse("recipe-create"), data)

    assert response.status_code == 302
    assert RecipeIngredient.objects.count() == 1
    assert RecipeIngredient.objects.get().ingredient_id == flour.pk


def test_invalid_ingredient_row_rolls_back_recipe_and_other_rows(client) -> None:
    flour = make_ingredient()
    sugar = make_ingredient(name="Sugar")
    data = creation_data(
        flour,
        **{
            "ingredients-TOTAL_FORMS": "2",
            "ingredients-1-ingredient": sugar.pk,
            "ingredients-1-quantity": "0",
            "ingredients-1-quantity_unit": "g",
        },
    )

    response = client.post(reverse("recipe-create"), data)

    assert response.status_code == 200
    assert Recipe.objects.count() == 0
    assert RecipeIngredient.objects.count() == 0


def test_recipe_ingredient_formset_uses_ingredient_choices_and_detects_duplicate_rows() -> None:
    flour = make_ingredient()
    formset = RecipeIngredientFormSet(
        data=creation_data(
            flour,
            **{
                "ingredients-TOTAL_FORMS": "2",
                "ingredients-1-ingredient": flour.pk,
                "ingredients-1-quantity": "25",
                "ingredients-1-quantity_unit": "g",
            },
        ),
        instance=Recipe(),
    )

    assert not formset.is_valid()
    assert "Each ingredient may only be used once in a recipe." in formset.non_form_errors()
