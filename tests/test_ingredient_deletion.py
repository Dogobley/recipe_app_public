"""Request tests for the safe ingredient deletion flow."""

from decimal import Decimal

import pytest
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory
from django.urls import reverse

from calculator.models import Ingredient, Recipe, RecipeIngredient


pytestmark = pytest.mark.django_db


def make_ingredient(**overrides: object) -> Ingredient:
    """Persist a valid ingredient for deletion requests."""
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


def test_delete_confirmation_displays_the_ingredient_and_permanence_warning(client) -> None:
    ingredient = make_ingredient(name="Cocoa powder")

    response = client.get(reverse("ingredient-delete", args=[ingredient.pk]))

    assert response.status_code == 200
    assert b"Cocoa powder" in response.content
    assert b"permanently delete" in response.content
    assert b"csrfmiddlewaretoken" in response.content
    assert Ingredient.objects.filter(pk=ingredient.pk).exists()


def test_delete_confirmation_cancel_returns_to_detail_without_changing_data(client) -> None:
    ingredient = make_ingredient()

    response = client.get(reverse("ingredient-delete", args=[ingredient.pk]))

    assert response.status_code == 200
    assert reverse("ingredient-detail", args=[ingredient.pk]).encode() in response.content
    assert Ingredient.objects.filter(pk=ingredient.pk).exists()


def test_delete_post_removes_unreferenced_ingredient_shows_message_and_uses_prg(client) -> None:
    ingredient = make_ingredient(name="Unused vanilla")

    response = client.post(reverse("ingredient-delete", args=[ingredient.pk]))

    assert response.status_code == 302
    assert response.url == reverse("ingredient-list")
    assert not Ingredient.objects.filter(pk=ingredient.pk).exists()
    assert b"Ingredient Unused vanilla deleted successfully." in client.get(response.url).content


def test_delete_post_for_recipe_ingredient_preserves_records_and_shows_named_error(client) -> None:
    ingredient = make_ingredient(name="Protected flour")
    recipe = Recipe.objects.create(name="Bread", weight_per_unit=Decimal("500.000"))
    row = RecipeIngredient.objects.create(
        recipe=recipe,
        ingredient=ingredient,
        quantity=Decimal("300.000"),
        quantity_unit=RecipeIngredient.QuantityUnit.GRAMS,
    )

    response = client.post(reverse("ingredient-delete", args=[ingredient.pk]))

    assert response.status_code == 302
    assert response.url == reverse("ingredient-detail", args=[ingredient.pk])
    assert Ingredient.objects.filter(pk=ingredient.pk).exists()
    assert Recipe.objects.filter(pk=recipe.pk).exists()
    assert RecipeIngredient.objects.filter(pk=row.pk).exists()
    content = client.get(response.url).content
    assert b"Protected flour" in content
    assert b"cannot be deleted because it is used by a recipe" in content


def test_delete_get_never_deletes_and_unsupported_method_is_rejected(client) -> None:
    ingredient = make_ingredient()
    url = reverse("ingredient-delete", args=[ingredient.pk])

    get_response = client.get(url)
    put_response = client.put(url, data="", content_type="application/x-www-form-urlencoded")

    assert get_response.status_code == 200
    assert Ingredient.objects.filter(pk=ingredient.pk).exists()
    assert put_response.status_code == 405
    assert put_response.headers["Allow"] == "GET, POST"


def test_delete_post_requires_csrf_token() -> None:
    ingredient = make_ingredient()
    csrf_client = Client(enforce_csrf_checks=True)
    url = reverse("ingredient-delete", args=[ingredient.pk])

    denied_response = csrf_client.post(url)
    request = RequestFactory().get(url)
    token = get_token(request)
    csrf_client.cookies["csrftoken"] = token
    allowed_response = csrf_client.post(url, HTTP_X_CSRFTOKEN=token)

    assert denied_response.status_code == 403
    assert allowed_response.status_code == 302
    assert not Ingredient.objects.filter(pk=ingredient.pk).exists()


def test_delete_of_unknown_ingredient_returns_404_without_changing_data(client) -> None:
    existing = make_ingredient()

    response = client.post(reverse("ingredient-delete", args=[999999]))

    assert response.status_code == 404
    assert Ingredient.objects.filter(pk=existing.pk).exists()
