"""Model tests for recipes and their ingredient rows."""

from decimal import Decimal

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from calculator.models import Ingredient, Recipe, RecipeIngredient


pytestmark = pytest.mark.django_db


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


def make_recipe(**overrides: object) -> Recipe:
    values: dict[str, object] = {"name": "Bread", "weight_per_unit": Decimal("750.000")}
    values.update(overrides)
    return Recipe.objects.create(**values)


def make_recipe_ingredient(**overrides: object) -> RecipeIngredient:
    values: dict[str, object] = {
        "recipe": make_recipe(),
        "ingredient": make_ingredient(),
        "quantity": Decimal("250.000"),
        "quantity_unit": RecipeIngredient.QuantityUnit.GRAMS,
    }
    values.update(overrides)
    return RecipeIngredient(**values)


def test_recipe_stores_required_fields_and_uses_name_as_its_display() -> None:
    recipe = make_recipe(name="Sourdough", weight_per_unit=Decimal("825.500"))

    assert recipe.name == "Sourdough"
    assert recipe.weight_per_unit == Decimal("825.500")
    assert str(recipe) == "Sourdough"


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_recipe_validation_rejects_non_positive_weight_per_unit(value: Decimal) -> None:
    recipe = Recipe(name="Bread", weight_per_unit=value)

    with pytest.raises(ValidationError, match="weight_per_unit"):
        recipe.full_clean()


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_recipe_database_constraint_rejects_non_positive_weight_per_unit(value: Decimal) -> None:
    with pytest.raises(IntegrityError):
        Recipe.objects.create(name=f"Invalid {value}", weight_per_unit=value)


def test_recipes_are_ordered_by_name_then_primary_key() -> None:
    third = make_recipe(name="Zucchini loaf")
    first = make_recipe(name="Apple bread")
    second = make_recipe(name="Apple bread")

    assert list(Recipe.objects.values_list("pk", flat=True)) == [first.pk, second.pk, third.pk]


def test_recipe_ingredient_links_recipes_and_ingredients_many_to_many() -> None:
    recipe_one = make_recipe(name="Bread")
    recipe_two = make_recipe(name="Cake")
    flour = make_ingredient(name="Flour")
    sugar = make_ingredient(name="Sugar")
    first = make_recipe_ingredient(recipe=recipe_one, ingredient=flour)
    second = make_recipe_ingredient(recipe=recipe_one, ingredient=sugar)
    third = make_recipe_ingredient(recipe=recipe_two, ingredient=flour)
    for row in (first, second, third):
        row.save()

    assert list(recipe_one.ingredients.all()) == [first, second]
    assert list(flour.recipe_ingredients.all()) == [first, third]


@pytest.mark.parametrize("unit", [RecipeIngredient.QuantityUnit.GRAMS, RecipeIngredient.QuantityUnit.KILOGRAMS])
def test_recipe_ingredient_accepts_supported_quantity_units(unit: str) -> None:
    row = make_recipe_ingredient(quantity_unit=unit)

    row.full_clean()


def test_recipe_ingredient_rejects_an_unsupported_quantity_unit() -> None:
    row = make_recipe_ingredient(quantity_unit="oz")

    with pytest.raises(ValidationError, match="quantity_unit"):
        row.full_clean()


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_recipe_ingredient_validation_rejects_non_positive_quantity(value: Decimal) -> None:
    row = make_recipe_ingredient(quantity=value)

    with pytest.raises(ValidationError, match="quantity"):
        row.full_clean()


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_recipe_ingredient_database_constraint_rejects_non_positive_quantity(value: Decimal) -> None:
    with pytest.raises(IntegrityError):
        RecipeIngredient.objects.create(
            recipe=make_recipe(name=f"Recipe {value}"),
            ingredient=make_ingredient(name=f"Ingredient {value}"),
            quantity=value,
            quantity_unit=RecipeIngredient.QuantityUnit.GRAMS,
        )


def test_recipe_ingredient_validation_and_database_constraint_reject_duplicate_pair() -> None:
    recipe = make_recipe()
    ingredient = make_ingredient()
    RecipeIngredient.objects.create(
        recipe=recipe,
        ingredient=ingredient,
        quantity=Decimal("250.000"),
        quantity_unit=RecipeIngredient.QuantityUnit.GRAMS,
    )
    duplicate = make_recipe_ingredient(recipe=recipe, ingredient=ingredient)

    with pytest.raises(ValidationError, match="Recipe ingredient with this Recipe and Ingredient already exists"):
        duplicate.full_clean()
    with pytest.raises(IntegrityError):
        duplicate.save()


def test_recipe_ingredients_are_ordered_by_ingredient_name_then_primary_key() -> None:
    recipe = make_recipe()
    zucchini = make_recipe_ingredient(recipe=recipe, ingredient=make_ingredient(name="Zucchini"))
    apple_first = make_recipe_ingredient(recipe=recipe, ingredient=make_ingredient(name="Apple"))
    apple_second = make_recipe_ingredient(recipe=recipe, ingredient=make_ingredient(name="Apple", brand="Other"))
    for row in (zucchini, apple_first, apple_second):
        row.save()

    assert list(RecipeIngredient.objects.values_list("pk", flat=True)) == [apple_first.pk, apple_second.pk, zucchini.pk]


def test_deleting_recipe_deletes_its_rows_but_not_ingredients() -> None:
    recipe = make_recipe()
    ingredient = make_ingredient()
    row = make_recipe_ingredient(recipe=recipe, ingredient=ingredient)
    row.save()

    recipe.delete()

    assert not RecipeIngredient.objects.filter(pk=row.pk).exists()
    assert Ingredient.objects.filter(pk=ingredient.pk).exists()


def test_deleting_an_ingredient_used_by_a_recipe_is_protected() -> None:
    recipe = make_recipe()
    ingredient = make_ingredient()
    row = make_recipe_ingredient(recipe=recipe, ingredient=ingredient)
    row.save()

    with pytest.raises(IntegrityError):
        ingredient.delete()

    assert Recipe.objects.filter(pk=recipe.pk).exists()
    assert RecipeIngredient.objects.filter(pk=row.pk).exists()


def test_recipe_models_are_registered_in_admin_with_readable_recipe_ingredient() -> None:
    assert Recipe in admin.site._registry
    assert RecipeIngredient in admin.site._registry
    row = make_recipe_ingredient(recipe=make_recipe(name="Bread"), ingredient=make_ingredient(name="Flour"))

    assert str(row) == "Bread: Flour"
