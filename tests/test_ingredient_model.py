"""Model tests for ingredient package pricing data."""

from decimal import Decimal

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from calculator.models import Ingredient


pytestmark = pytest.mark.django_db


def make_ingredient(**overrides: object) -> Ingredient:
    """Build a valid unsaved ingredient, allowing a test to override fields."""
    values: dict[str, object] = {
        "name": "Flour",
        "brand": "Mill House",
        "place_of_purchase": "Market",
        "package_weight": Decimal("1.250"),
        "package_weight_unit": Ingredient.WeightUnit.KILOGRAMS,
        "package_price": Decimal("4.75"),
    }
    values.update(overrides)
    return Ingredient(**values)


def test_ingredient_stores_all_required_package_pricing_fields() -> None:
    ingredient = make_ingredient()
    ingredient.full_clean()
    ingredient.save()

    stored = Ingredient.objects.get(pk=ingredient.pk)
    assert stored.name == "Flour"
    assert stored.brand == "Mill House"
    assert stored.place_of_purchase == "Market"
    assert stored.package_weight == Decimal("1.250")
    assert stored.package_weight_unit == Ingredient.WeightUnit.KILOGRAMS
    assert stored.package_price == Decimal("4.75")


@pytest.mark.parametrize("field", ["name", "brand", "place_of_purchase"])
def test_ingredient_requires_its_descriptive_fields(field: str) -> None:
    ingredient = make_ingredient(**{field: ""})

    with pytest.raises(ValidationError, match=field):
        ingredient.full_clean()


@pytest.mark.parametrize("unit", [Ingredient.WeightUnit.GRAMS, Ingredient.WeightUnit.KILOGRAMS])
def test_ingredient_accepts_supported_package_weight_units(unit: str) -> None:
    ingredient = make_ingredient(package_weight_unit=unit)

    ingredient.full_clean()


def test_ingredient_rejects_an_unsupported_package_weight_unit() -> None:
    ingredient = make_ingredient(package_weight_unit="oz")

    with pytest.raises(ValidationError, match="package_weight_unit"):
        ingredient.full_clean()


@pytest.mark.parametrize("field", ["package_weight", "package_price"])
@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-0.01")])
def test_ingredient_model_validation_rejects_non_positive_package_values(
    field: str, value: Decimal
) -> None:
    ingredient = make_ingredient(**{field: value})

    with pytest.raises(ValidationError, match=field):
        ingredient.full_clean()


@pytest.mark.parametrize("field", ["package_weight", "package_price"])
@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_ingredient_database_constraints_reject_non_positive_package_values(
    field: str, value: Decimal
) -> None:
    values = {
        "name": f"Ingredient {field} {value}",
        "brand": "Brand",
        "place_of_purchase": "Shop",
        "package_weight": Decimal("1.000"),
        "package_weight_unit": Ingredient.WeightUnit.GRAMS,
        "package_price": Decimal("1.00"),
    }
    values[field] = value

    with pytest.raises(IntegrityError):
        Ingredient.objects.create(**values)


def test_ingredient_preserves_fractional_weight_and_price() -> None:
    ingredient = make_ingredient(
        package_weight=Decimal("250.125"),
        package_price=Decimal("3.45"),
    )
    ingredient.save()

    stored = Ingredient.objects.get(pk=ingredient.pk)
    assert stored.package_weight == Decimal("250.125")
    assert stored.package_price == Decimal("3.45")


def test_ingredients_are_ordered_by_name_then_primary_key() -> None:
    third = make_ingredient(name="Zucchini")
    first = make_ingredient(name="Almond")
    second = make_ingredient(name="Almond", brand="Second brand")
    for ingredient in (third, first, second):
        ingredient.save()

    assert list(Ingredient.objects.values_list("pk", flat=True)) == [first.pk, second.pk, third.pk]


def test_ingredient_string_representation_is_its_name() -> None:
    ingredient = make_ingredient(name="Cocoa powder")

    assert str(ingredient) == "Cocoa powder"


def test_ingredient_is_registered_with_package_and_pricing_details_in_admin() -> None:
    registered_admin = admin.site._registry[Ingredient]

    assert registered_admin.list_display == (
        "name",
        "brand",
        "place_of_purchase",
        "package_weight",
        "package_weight_unit",
        "package_price",
    )
