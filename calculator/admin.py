"""Django admin registrations for the calculator application."""

from django.contrib import admin

from calculator.models import Ingredient, Recipe, RecipeIngredient


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    """Expose ingredient package and pricing data in the administration site."""

    list_display = (
        "name",
        "brand",
        "place_of_purchase",
        "package_weight",
        "package_weight_unit",
        "package_price",
    )
    search_fields = ("name", "brand", "place_of_purchase")


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Expose recipes in the administration site."""

    list_display = ("name", "weight_per_unit")
    search_fields = ("name",)


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    """Expose recipe ingredients in the administration site."""

    list_display = ("recipe", "ingredient", "quantity", "quantity_unit")
    search_fields = ("recipe__name", "ingredient__name")
