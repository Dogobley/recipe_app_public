"""Server-rendered views for the recipe cost calculator."""

from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from calculator import metrics
from calculator.forms import (
    IngredientForm,
    RecipeCalculatorForm,
    RecipeForm,
    RecipeIngredientFormSet,
)
from calculator.models import Ingredient, Recipe, RecipeIngredient
from calculator.services.recipes import calculate_recipe


def ingredient_list(request):
    """Display all saved ingredients in their model-defined order."""
    ingredients = Ingredient.objects.all()
    return render(request, "calculator/ingredient_list.html", {"ingredients": ingredients})


def ingredient_detail(request, pk: int):
    """Display the complete pricing and package information for one ingredient."""
    ingredient = get_object_or_404(Ingredient, pk=pk)
    return render(request, "calculator/ingredient_detail.html", {"ingredient": ingredient})


@require_http_methods(["GET", "POST"])
@metrics.count_creation_failures("ingredient")
def ingredient_create(request):
    """Create one ingredient after server-side validation."""
    form = IngredientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ingredient = form.save()
        messages.success(request, "Ingredient added successfully.")
        return redirect("ingredient-detail", pk=ingredient.pk)
    return render(
        request,
        "calculator/ingredient_form.html",
        {"form": form, "page_title": "Add ingredient", "submit_label": "Add ingredient"},
    )


@require_http_methods(["GET", "POST"])
def ingredient_edit(request, pk: int):
    """Update an existing ingredient after server-side validation."""
    ingredient = get_object_or_404(Ingredient, pk=pk)
    form = IngredientForm(request.POST or None, instance=ingredient)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ingredient updated successfully.")
        return redirect("ingredient-detail", pk=ingredient.pk)
    return render(
        request,
        "calculator/ingredient_form.html",
        {
            "form": form,
            "ingredient": ingredient,
            "page_title": "Edit ingredient",
            "submit_label": "Save ingredient",
        },
    )


@require_http_methods(["GET", "POST"])
def ingredient_delete(request, pk: int):
    """Confirm and safely delete an ingredient when no recipe uses it."""
    ingredient = get_object_or_404(Ingredient, pk=pk)
    if request.method == "POST":
        try:
            ingredient.delete()
        except ProtectedError:
            messages.error(
                request,
                f"Ingredient {ingredient.name} cannot be deleted because it is used by a recipe.",
            )
            return redirect("ingredient-detail", pk=ingredient.pk)
        messages.success(request, f"Ingredient {ingredient.name} deleted successfully.")
        return redirect("ingredient-list")
    return render(request, "calculator/ingredient_confirm_delete.html", {"ingredient": ingredient})


def recipe_list(request):
    """Display every saved recipe in its model-defined order."""
    recipes = Recipe.objects.all()
    return render(request, "calculator/recipe_list.html", {"recipes": recipes})


def recipe_detail(request, pk: int):
    """Display one recipe and its ingredient quantities without N+1 queries."""
    recipe = get_object_or_404(
        Recipe.objects.prefetch_related(
            Prefetch(
                "ingredients",
                queryset=RecipeIngredient.objects.select_related("ingredient"),
            )
        ),
        pk=pk,
    )
    metrics.record_recipe_view(recipe.name)
    return render(request, "calculator/recipe_detail.html", {"recipe": recipe})


@require_http_methods(["GET", "POST"])
@metrics.count_creation_failures("recipe")
def recipe_create(request):
    """Create a recipe and its ingredient rows as one atomic submission."""
    recipe = Recipe()
    form = RecipeForm(request.POST or None, instance=recipe)
    formset = RecipeIngredientFormSet(request.POST or None, instance=recipe)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            recipe = form.save()
            formset.instance = recipe
            formset.save()
        metrics.record_recipe_created()
        messages.success(request, "Recipe added successfully.")
        return redirect("recipe-detail", pk=recipe.pk)
    return render(
        request,
        "calculator/recipe_form.html",
        {
            "form": form,
            "formset": formset,
            "page_title": "Add recipe",
            "submit_label": "Add recipe",
        },
    )


@require_http_methods(["GET", "POST"])
def recipe_edit(request, pk: int):
    """Update a recipe and its ingredient rows as one atomic submission."""
    recipe = get_object_or_404(Recipe, pk=pk)
    form = RecipeForm(request.POST or None, instance=recipe)
    formset = RecipeIngredientFormSet(request.POST or None, instance=recipe)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            formset.save()
        messages.success(request, "Recipe updated successfully.")
        return redirect("recipe-detail", pk=recipe.pk)
    return render(
        request,
        "calculator/recipe_form.html",
        {
            "form": form,
            "formset": formset,
            "recipe": recipe,
            "page_title": "Edit recipe",
            "submit_label": "Save recipe",
        },
    )


@require_http_methods(["GET", "POST"])
def recipe_delete(request, pk: int):
    """Confirm and delete a recipe without deleting its ingredients."""
    recipe = get_object_or_404(Recipe, pk=pk)
    if request.method == "POST":
        recipe_name = recipe.name
        recipe.delete()
        messages.success(request, f"Recipe {recipe_name} deleted successfully.")
        return redirect("recipe-list")
    return render(request, "calculator/recipe_confirm_delete.html", {"recipe": recipe})


@require_http_methods(["GET", "POST"])
def recipe_calculator(request):
    """Render a read-only, server-side recipe cost calculation."""
    form = RecipeCalculatorForm(request.POST or None)
    calculation = None
    if request.method == "GET" and request.GET.get("recipe"):
        form = RecipeCalculatorForm(initial={"recipe": request.GET["recipe"]})
    elif request.method == "POST" and form.is_valid():
        calculation = calculate_recipe(form.cleaned_data["recipe"], form.cleaned_data["units"])

    return render(
        request,
        "calculator/recipe_calculator.html",
        {
            "form": form,
            "calculation": calculation,
            "recipes_available": form.fields["recipe"].queryset.exists(),
        },
    )
