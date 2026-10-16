"""Request tests for the recipe calculator page."""

from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from calculator.models import Ingredient, Recipe, RecipeIngredient


pytestmark = pytest.mark.django_db


def make_recipe(**overrides: object) -> Recipe:
    values: dict[str, object] = {"name": "Bread", "weight_per_unit": Decimal("750.000")}
    values.update(overrides)
    return Recipe.objects.create(**values)


def make_ingredient(**overrides: object) -> Ingredient:
    values: dict[str, object] = {
        "name": "Flour", "brand": "Mill House", "place_of_purchase": "Market",
        "package_weight": Decimal("1.000"), "package_weight_unit": "kg",
        "package_price": Decimal("4.75"),
    }
    values.update(overrides)
    return Ingredient.objects.create(**values)


def test_calculator_initial_page_lists_recipes_in_model_order_and_fields(client) -> None:
    last = make_recipe(name="Zucchini loaf")
    first = make_recipe(name="Apple bread")

    response = client.get(reverse("recipe-calculator"))

    assert response.status_code == 200
    assert response.context["form"].fields["recipe"].queryset.count() == 2
    assert response.content.index(first.name.encode()) < response.content.index(last.name.encode())
    assert b'name="recipe"' in response.content
    assert b'name="units"' in response.content
    assert b'required' in response.content


def test_calculator_empty_catalog_shows_create_recipe_action(client) -> None:
    response = client.get(reverse("recipe-calculator"))

    assert response.status_code == 200
    assert b"No recipes are available to calculate yet." in response.content
    assert reverse("recipe-create").encode() in response.content


@pytest.mark.parametrize("units", ["0", "-1", "1.5", "true", "", "not-a-number"])
def test_calculator_rejects_invalid_units_without_a_result(client, units: str) -> None:
    recipe = make_recipe()

    response = client.post(reverse("recipe-calculator"), {"recipe": recipe.pk, "units": units})

    assert response.status_code == 200
    assert "units" in response.context["form"].errors
    assert b"Enter a positive whole number." in response.content
    assert b"Calculation for" not in response.content
    assert response.context["form"]["recipe"].value() == str(recipe.pk)
    assert response.context["form"]["units"].value() == units


def test_calculator_rejects_missing_recipe_as_a_form_error(client) -> None:
    response = client.post(reverse("recipe-calculator"), {"recipe": "999999", "units": "1"})

    assert response.status_code == 200
    assert "recipe" in response.context["form"].errors
    assert b"Select a valid recipe." in response.content
    assert b"Calculation for" not in response.content


def test_calculator_displays_scaled_recipe_result_in_ingredient_order(client) -> None:
    recipe = make_recipe(name="Cake", weight_per_unit=Decimal("500.000"))
    zucchini = make_ingredient(name="Zucchini", package_price=Decimal("2.00"))
    apple = make_ingredient(name="Apple", brand="Orchard", package_price=Decimal("3.00"))
    RecipeIngredient.objects.create(recipe=recipe, ingredient=zucchini, quantity=Decimal("100.000"), quantity_unit="g")
    RecipeIngredient.objects.create(recipe=recipe, ingredient=apple, quantity=Decimal("0.200"), quantity_unit="kg")

    response = client.post(reverse("recipe-calculator"), {"recipe": recipe.pk, "units": "2"})

    assert response.status_code == 200
    for content in (b"Calculation for Cake", b"Requested units", b"2", b"Cost per unit", b"COP $0.80", b"Weight per unit", b"500 g", b"Adjusted quantity", b"0.4 kg", b"200 g", b"COP $1.20", b"COP $0.40", b"Total cost", b"COP $1.60", b"Total weight", b"600 g"):
        assert content in response.content
    assert response.content.index(b"Apple") < response.content.index(b"Zucchini")


def test_calculator_empty_recipe_displays_zero_totals_and_empty_result(client) -> None:
    recipe = make_recipe()

    response = client.post(reverse("recipe-calculator"), {"recipe": recipe.pk, "units": "3"})

    assert response.status_code == 200
    assert b"This recipe has no ingredients. Total ingredient cost and weight are zero." in response.content
    assert b"Total cost" in response.content
    assert b"Total weight" in response.content
    assert b"COP $0.00" in response.content
    assert b"0 g" in response.content


def test_calculator_is_read_only(client) -> None:
    recipe = make_recipe()
    counts_before = (Recipe.objects.count(), Ingredient.objects.count(), RecipeIngredient.objects.count())

    response = client.post(reverse("recipe-calculator"), {"recipe": recipe.pk, "units": "2"})

    assert response.status_code == 200
    assert (Recipe.objects.count(), Ingredient.objects.count(), RecipeIngredient.objects.count()) == counts_before


def test_calculator_post_requires_csrf_token() -> None:
    recipe = make_recipe()
    csrf_client = Client(enforce_csrf_checks=True)

    response = csrf_client.post(reverse("recipe-calculator"), {"recipe": recipe.pk, "units": "2"})

    assert response.status_code == 403
