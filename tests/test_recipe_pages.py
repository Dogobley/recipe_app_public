"""Request tests for read-only recipe browsing pages."""

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


def test_recipe_list_shows_recipes_in_model_order_with_detail_links(client, django_assert_num_queries) -> None:
    last = make_recipe(name="Zucchini loaf", weight_per_unit=Decimal("400.000"))
    first = make_recipe(name="Apple bread", weight_per_unit=Decimal("500.000"))
    second = make_recipe(name="Apple bread", weight_per_unit=Decimal("550.000"))

    with django_assert_num_queries(1):
        response = client.get(reverse("recipe-list"))

    assert response.status_code == 200
    assert list(response.context["recipes"]) == [first, second, last]
    for recipe in (first, second, last):
        assert recipe.name.encode() in response.content
        assert f"{recipe.weight_per_unit.normalize():f} g".encode() in response.content
        assert reverse("recipe-detail", args=[recipe.pk]).encode() in response.content
    assert b'href="/recipes/add/"' in response.content
    assert b"Add recipe" in response.content


def test_empty_recipe_list_shows_empty_state_and_create_action(client) -> None:
    response = client.get(reverse("recipe-list"))

    assert response.status_code == 200
    assert b"No recipes have been added yet." in response.content
    assert b"<table" not in response.content
    assert b'href="/recipes/add/"' in response.content


def test_recipe_detail_shows_ordered_ingredient_quantities_and_actions(client, django_assert_num_queries) -> None:
    recipe = make_recipe(name="Cake")
    zucchini = make_ingredient(name="Zucchini")
    apple = make_ingredient(name="Apple")
    RecipeIngredient.objects.create(recipe=recipe, ingredient=zucchini, quantity=Decimal("1.500"), quantity_unit="kg")
    RecipeIngredient.objects.create(recipe=recipe, ingredient=apple, quantity=Decimal("250.000"), quantity_unit="g")

    with django_assert_num_queries(2):
        response = client.get(reverse("recipe-detail", args=[recipe.pk]))

    assert response.status_code == 200
    assert recipe.name.encode() in response.content
    assert b"750 g" in response.content
    assert response.content.index(b"Apple") < response.content.index(b"Zucchini")
    assert b"250 g" in response.content
    assert b"1.5 kg" in response.content
    for href, label in (
        (b'/recipes/', b"Back to recipes"),
        (f"/recipes/{recipe.pk}/edit/".encode(), b"Edit recipe"),
        (f"/recipes/{recipe.pk}/delete/".encode(), b"Delete recipe"),
        (f"/calculator/?recipe={recipe.pk}".encode(), b"Calculate recipe"),
    ):
        assert href in response.content
        assert label in response.content


def test_recipe_detail_shows_ingredient_empty_state(client) -> None:
    recipe = make_recipe()

    response = client.get(reverse("recipe-detail", args=[recipe.pk]))

    assert response.status_code == 200
    assert b"This recipe has no ingredients yet." in response.content
    assert b"<table" not in response.content


def test_recipe_detail_returns_404_for_an_unknown_identifier(client) -> None:
    response = client.get(reverse("recipe-detail", args=[999999]))

    assert response.status_code == 404
