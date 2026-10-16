"""Request tests for read-only ingredient browsing pages."""

from decimal import Decimal

import pytest
from django.urls import reverse

from calculator.models import Ingredient


pytestmark = pytest.mark.django_db


def make_ingredient(**overrides: object) -> Ingredient:
    """Create a valid ingredient with distinct, visible package data."""
    values: dict[str, object] = {
        "name": "Cocoa powder",
        "brand": "Cacao Valley",
        "place_of_purchase": "Central Market",
        "package_weight": Decimal("250.000"),
        "package_weight_unit": Ingredient.WeightUnit.GRAMS,
        "package_price": Decimal("12.50"),
    }
    values.update(overrides)
    return Ingredient.objects.create(**values)


def test_ingredient_list_shows_saved_ingredients_in_model_order_with_detail_links(
    client, django_assert_num_queries
) -> None:
    """The list presents every pricing field in the model's defined order."""
    last = make_ingredient(name="Vanilla")
    first = make_ingredient(name="Almond", brand="Orchard", place_of_purchase="Grocer")
    second = make_ingredient(name="Almond", brand="Second Orchard", place_of_purchase="Bakery")

    with django_assert_num_queries(1):
        response = client.get(reverse("ingredient-list"))

    assert response.status_code == 200
    assert list(response.context["ingredients"]) == [first, second, last]
    for ingredient in (first, second, last):
        assert ingredient.name.encode() in response.content
        assert ingredient.brand.encode() in response.content
        assert ingredient.place_of_purchase.encode() in response.content
        assert f"{ingredient.package_weight.normalize():f} {ingredient.package_weight_unit}".encode() in response.content
        assert f"COP ${ingredient.package_price:.2f}".encode() in response.content
        assert reverse("ingredient-detail", args=[ingredient.pk]).encode() in response.content
    assert b'href="/ingredients/add/"' in response.content
    assert b"Add ingredient" in response.content


def test_empty_ingredient_list_shows_an_empty_state_and_create_action(client) -> None:
    """The empty list replaces the data table with a useful next action."""
    response = client.get(reverse("ingredient-list"))

    assert response.status_code == 200
    assert b"No ingredients have been added yet." in response.content
    assert b"<table" not in response.content
    assert b'href="/ingredients/add/"' in response.content
    assert b"Add ingredient" in response.content


def test_ingredient_detail_shows_complete_data_and_navigation_actions(
    client, django_assert_num_queries
) -> None:
    """The detail page exposes the selected ingredient and its future actions."""
    ingredient = make_ingredient(package_weight_unit=Ingredient.WeightUnit.KILOGRAMS)

    with django_assert_num_queries(1):
        response = client.get(reverse("ingredient-detail", args=[ingredient.pk]))

    assert response.status_code == 200
    for value in (
        ingredient.name,
        ingredient.brand,
        ingredient.place_of_purchase,
        f"{ingredient.package_weight.normalize():f} {ingredient.package_weight_unit}",
        f"COP ${ingredient.package_price:.2f}",
    ):
        assert value.encode() in response.content
    assert reverse("ingredient-list").encode() in response.content
    assert f'/ingredients/{ingredient.pk}/edit/'.encode() in response.content
    assert f'/ingredients/{ingredient.pk}/delete/'.encode() in response.content
    assert b"Back to ingredients" in response.content
    assert b"Edit ingredient" in response.content
    assert b"Delete ingredient" in response.content


def test_ingredient_detail_returns_404_for_an_unknown_identifier(client) -> None:
    """A missing ingredient must not render a generic or empty detail page."""
    response = client.get(reverse("ingredient-detail", args=[999999]))

    assert response.status_code == 404
