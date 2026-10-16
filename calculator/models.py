"""Database models for the calculator application."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Ingredient(models.Model):
    """A purchasable ingredient and the package information used to price it."""

    class WeightUnit(models.TextChoices):
        GRAMS = "g", "Grams"
        KILOGRAMS = "kg", "Kilograms"

    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=255)
    place_of_purchase = models.CharField(max_length=255)
    package_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    package_weight_unit = models.CharField(
        max_length=2,
        choices=WeightUnit.choices,
    )
    package_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(package_weight__gt=0),
                name="ingredient_package_weight_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(package_price__gt=0),
                name="ingredient_package_price_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Recipe(models.Model):
    """A recipe with the finished weight produced by one unit."""

    name = models.CharField(max_length=255)
    weight_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weight_per_unit__gt=0),
                name="recipe_weight_per_unit_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class RecipeIngredient(models.Model):
    """The amount of one ingredient required by a recipe."""

    class QuantityUnit(models.TextChoices):
        GRAMS = "g", "Grams"
        KILOGRAMS = "kg", "Kilograms"

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="ingredients")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="recipe_ingredients")
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    quantity_unit = models.CharField(max_length=2, choices=QuantityUnit.choices)

    class Meta:
        ordering = ["ingredient__name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "ingredient"],
                name="recipe_ingredient_unique_pair",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="recipe_ingredient_quantity_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.recipe}: {self.ingredient}"
