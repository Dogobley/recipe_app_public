"""Request and form tests for ingredient create and edit flows."""

from decimal import Decimal

import pytest
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory
from django.urls import reverse

from calculator.models import Ingredient


pytestmark = pytest.mark.django_db


def ingredient_data(**overrides: str) -> dict[str, str]:
    """Return a complete, valid ingredient submission."""
    values = {
        "name": "Cocoa powder",
        "brand": "Cacao Valley",
        "place_of_purchase": "Central Market",
        "package_weight": "250.125",
        "package_weight_unit": "g",
        "package_price": "12.50",
    }
    values.update(overrides)
    return values


def make_ingredient(**overrides: object) -> Ingredient:
    """Persist an ingredient suitable for edit requests."""
    values: dict[str, object] = {
        "name": "Flour",
        "brand": "Mill House",
        "place_of_purchase": "Market",
        "package_weight": Decimal("1.250"),
        "package_weight_unit": Ingredient.WeightUnit.KILOGRAMS,
        "package_price": Decimal("4.75"),
    }
    values.update(overrides)
    return Ingredient.objects.create(**values)


def test_create_get_displays_every_required_ingredient_field(client) -> None:
    response = client.get(reverse("ingredient-create"))

    assert response.status_code == 200
    assert response.context["form"].instance.pk is None
    for field in (
        "name",
        "brand",
        "place_of_purchase",
        "package_weight",
        "package_weight_unit",
        "package_price",
    ):
        assert f'name="{field}"'.encode() in response.content
        assert f'<label class="form-label" for="id_{field}">'.encode() in response.content
    assert b"csrfmiddlewaretoken" in response.content


def test_create_post_saves_one_ingredient_sets_success_message_and_uses_prg(client) -> None:
    response = client.post(reverse("ingredient-create"), ingredient_data())

    ingredient = Ingredient.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("ingredient-detail", args=[ingredient.pk])
    assert ingredient.name == "Cocoa powder"
    assert ingredient.package_weight == Decimal("250.125")

    detail_response = client.get(response.url)
    assert b"Ingredient added successfully." in detail_response.content


def test_edit_get_is_prepopulated_with_the_selected_ingredient(client) -> None:
    ingredient = make_ingredient()

    response = client.get(reverse("ingredient-edit", args=[ingredient.pk]))

    assert response.status_code == 200
    form = response.context["form"]
    assert form.instance == ingredient
    assert form.initial["name"] == ingredient.name
    assert form.initial["brand"] == ingredient.brand
    assert form.initial["place_of_purchase"] == ingredient.place_of_purchase
    assert form.initial["package_weight"] == ingredient.package_weight
    assert form.initial["package_weight_unit"] == ingredient.package_weight_unit
    assert form.initial["package_price"] == ingredient.package_price


def test_edit_post_updates_selected_ingredient_without_creating_another_and_uses_prg(client) -> None:
    ingredient = make_ingredient()
    data = ingredient_data(name="Dutch cocoa", package_weight_unit="kg", package_price="18.25")

    response = client.post(reverse("ingredient-edit", args=[ingredient.pk]), data)

    assert response.status_code == 302
    assert response.url == reverse("ingredient-detail", args=[ingredient.pk])
    assert Ingredient.objects.count() == 1
    ingredient.refresh_from_db()
    assert ingredient.name == "Dutch cocoa"
    assert ingredient.package_weight_unit == Ingredient.WeightUnit.KILOGRAMS
    assert ingredient.package_price == Decimal("18.25")

    detail_response = client.get(response.url)
    assert b"Ingredient updated successfully." in detail_response.content


@pytest.mark.parametrize(
    "field",
    ["name", "brand", "place_of_purchase", "package_weight", "package_weight_unit", "package_price"],
)
def test_create_required_field_errors_are_specific_and_do_not_save(client, field: str) -> None:
    data = ingredient_data(**{field: ""})

    response = client.post(reverse("ingredient-create"), data)

    assert response.status_code == 200
    assert field in response.context["form"].errors
    assert Ingredient.objects.count() == 0


@pytest.mark.parametrize(
    "field, value",
    [
        ("package_weight_unit", "oz"),
        ("package_weight", "not-a-number"),
        ("package_price", "not-a-number"),
        ("package_weight", "0"),
        ("package_weight", "-1"),
        ("package_price", "0"),
        ("package_price", "-1"),
    ],
)
def test_create_invalid_package_values_display_field_errors_and_do_not_save(
    client, field: str, value: str
) -> None:
    response = client.post(reverse("ingredient-create"), ingredient_data(**{field: value}))

    assert response.status_code == 200
    assert field in response.context["form"].errors
    assert response.context["form"].errors[field]
    assert Ingredient.objects.count() == 0


def test_invalid_create_preserves_every_other_submitted_value(client) -> None:
    data = ingredient_data(package_price="invalid-price")

    response = client.post(reverse("ingredient-create"), data)

    assert response.status_code == 200
    form = response.context["form"]
    for field, value in data.items():
        assert form[field].value() == value
    assert b"invalid-price" in response.content
    assert Ingredient.objects.count() == 0


def test_invalid_edit_preserves_submitted_values_and_leaves_existing_ingredient_unchanged(client) -> None:
    ingredient = make_ingredient()
    data = ingredient_data(name="Attempted update", package_weight="0")

    response = client.post(reverse("ingredient-edit", args=[ingredient.pk]), data)

    assert response.status_code == 200
    assert response.context["form"]["name"].value() == "Attempted update"
    assert response.context["form"]["package_weight"].value() == "0"
    ingredient.refresh_from_db()
    assert ingredient.name == "Flour"
    assert ingredient.package_weight == Decimal("1.250")
    assert Ingredient.objects.count() == 1


def test_edit_of_an_unknown_ingredient_returns_404(client) -> None:
    response = client.get(reverse("ingredient-edit", args=[999999]))

    assert response.status_code == 404


@pytest.mark.parametrize("url_name", ["ingredient-create", "ingredient-edit"])
def test_create_and_edit_reject_unsupported_http_methods(client, url_name: str) -> None:
    ingredient = make_ingredient() if url_name == "ingredient-edit" else None
    url = reverse(url_name, args=[ingredient.pk]) if ingredient else reverse(url_name)

    response = client.put(url, data="name=Nope", content_type="application/x-www-form-urlencoded")

    assert response.status_code == 405
    assert response.headers["Allow"] == "GET, POST"


def test_create_post_requires_a_valid_csrf_token() -> None:
    csrf_client = Client(enforce_csrf_checks=True)

    denied_response = csrf_client.post(reverse("ingredient-create"), ingredient_data())
    request = RequestFactory().get(reverse("ingredient-create"))
    token = get_token(request)
    csrf_client.cookies["csrftoken"] = token
    allowed_response = csrf_client.post(
        reverse("ingredient-create"), ingredient_data(), HTTP_X_CSRFTOKEN=token
    )

    assert denied_response.status_code == 403
    assert allowed_response.status_code == 302
