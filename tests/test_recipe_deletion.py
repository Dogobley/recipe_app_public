"""Request tests for recipe deletion confirmation and effects."""

from decimal import Decimal

import pytest
from django.urls import reverse

from calculator.models import Ingredient, Recipe, RecipeIngredient


pytestmark = pytest.mark.django_db


def make_recipe(**overrides: object) -> Recipe:
    values: dict[str, object] = {"name": "Bread", "weight_per_unit": Decimal("750.000")}
    values.update(overrides)
    return Recipe.objects.create(**values)


def make_ingredient(**overrides: object) -> Ingredient:
    values: dict[str, object] = {
        "name": "Flour",
        "brand": "Mill House",
        "place_of_purchase": "Market",
        "package_weight": Decimal("1.000"),
        "package_weight_unit": Ingredient.WeightUnit.KILOGRAMS,
        "package_price": Decimal("4.75"),
    }
    values.update(overrides)
    return Ingredient.objects.create(**values)


def make_row(recipe: Recipe, ingredient: Ingredient) -> RecipeIngredient:
    return RecipeIngredient.objects.create(
        recipe=recipe,
        ingredient=ingredient,
        quantity=Decimal("250.000"),
        quantity_unit=RecipeIngredient.QuantityUnit.GRAMS,
    )


def test_recipe_delete_confirmation_shows_recipe_cascade_warning_and_cancel_link(client) -> None:
    recipe = make_recipe(name="Sourdough")

    response = client.get(reverse("recipe-delete", args=[recipe.pk]))

    assert response.status_code == 200
    assert b"Sourdough" in response.content
    assert b"recipe ingredient rows will also be removed" in response.content
    assert f'href="{reverse("recipe-detail", args=[recipe.pk])}"'.encode() in response.content
    assert b">Cancel<" in response.content
    assert b'name="csrfmiddlewaretoken"' in response.content


def test_recipe_delete_get_never_changes_data_and_cancel_returns_to_detail(client) -> None:
    recipe = make_recipe()
    row = make_row(recipe, make_ingredient())

    response = client.get(reverse("recipe-delete", args=[recipe.pk]))

    assert response.status_code == 200
    assert Recipe.objects.filter(pk=recipe.pk).exists()
    assert RecipeIngredient.objects.filter(pk=row.pk).exists()


def test_recipe_delete_post_removes_recipe_and_rows_preserves_shared_ingredients_and_shows_message(client) -> None:
    recipe = make_recipe(name="Bread")
    other_recipe = make_recipe(name="Cake")
    shared = make_ingredient(name="Flour")
    exclusive = make_ingredient(name="Yeast")
    deleted_shared_row = make_row(recipe, shared)
    deleted_exclusive_row = make_row(recipe, exclusive)
    retained_shared_row = make_row(other_recipe, shared)

    response = client.post(reverse("recipe-delete", args=[recipe.pk]), follow=True)

    assert response.redirect_chain == [(reverse("recipe-list"), 302)]
    assert response.status_code == 200
    assert b"Recipe Bread deleted successfully." in response.content
    assert not Recipe.objects.filter(pk=recipe.pk).exists()
    assert not RecipeIngredient.objects.filter(pk__in=[deleted_shared_row.pk, deleted_exclusive_row.pk]).exists()
    assert RecipeIngredient.objects.filter(pk=retained_shared_row.pk).exists()
    assert Ingredient.objects.filter(pk=shared.pk).exists()
    assert Ingredient.objects.filter(pk=exclusive.pk).exists()


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_recipe_delete_rejects_unsupported_methods_without_changing_data(client, method: str) -> None:
    recipe = make_recipe()
    row = make_row(recipe, make_ingredient())

    response = getattr(client, method)(reverse("recipe-delete", args=[recipe.pk]))

    assert response.status_code == 405
    assert Recipe.objects.filter(pk=recipe.pk).exists()
    assert RecipeIngredient.objects.filter(pk=row.pk).exists()


def test_recipe_delete_post_requires_csrf_token(client) -> None:
    recipe = make_recipe()
    csrf_client = client.__class__(enforce_csrf_checks=True)

    response = csrf_client.post(reverse("recipe-delete", args=[recipe.pk]))

    assert response.status_code == 403
    assert Recipe.objects.filter(pk=recipe.pk).exists()


def test_recipe_delete_returns_404_for_unknown_recipe_without_changing_data(client) -> None:
    surviving_recipe = make_recipe()
    row = make_row(surviving_recipe, make_ingredient())

    response = client.post(reverse("recipe-delete", args=[999999]))

    assert response.status_code == 404
    assert Recipe.objects.filter(pk=surviving_recipe.pk).exists()
    assert RecipeIngredient.objects.filter(pk=row.pk).exists()
