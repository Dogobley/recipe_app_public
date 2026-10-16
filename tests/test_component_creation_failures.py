"""The component creation failure counter behind the creation-failure alert.

A failure is a recipe or ingredient create POST that the server could not
complete: an unhandled exception or a 5xx response. Everything else, including
forms redisplayed with validation errors, must leave the counter alone, and
counting must never change what the user receives.
"""

from decimal import Decimal

import pytest
from django.db import DatabaseError
from django.http import Http404, HttpResponse
from django.test import Client, RequestFactory
from django.urls import reverse

from calculator import metrics as app_metrics
from calculator import views
from calculator.models import Ingredient, Recipe, RecipeIngredient


pytestmark = pytest.mark.django_db

METRIC_NAME = "component_creation_failures"


def failure_counts(reader) -> dict[str, int]:
    """Collect once and return the failure count per component label."""
    reader.collect()
    counts: dict[str, int] = {}
    for resource_metric in reader.get_metrics_data().resource_metrics:
        for scope_metric in resource_metric.scope_metrics:
            for metric in scope_metric.metrics:
                if metric.name == METRIC_NAME:
                    for point in metric.data.data_points:
                        counts[dict(point.attributes)["component"]] = point.value
    return counts


def no_failures() -> dict[str, int]:
    return {"recipe": 0, "ingredient": 0}


def make_ingredient(name: str = "Flour") -> Ingredient:
    return Ingredient.objects.create(
        name=name,
        brand="Mill House",
        place_of_purchase="Market",
        package_weight=Decimal("1.000"),
        package_weight_unit="kg",
        package_price=Decimal("4.75"),
    )


def recipe_data(*rows: tuple[Ingredient, str], **overrides: str) -> dict[str, str]:
    values = {
        "name": "Bread",
        "weight_per_unit": "750",
        "ingredients-TOTAL_FORMS": str(len(rows)),
        "ingredients-INITIAL_FORMS": "0",
        "ingredients-MIN_NUM_FORMS": "0",
        "ingredients-MAX_NUM_FORMS": "1000",
    }
    for index, (ingredient, quantity) in enumerate(rows):
        values[f"ingredients-{index}-ingredient"] = str(ingredient.pk)
        values[f"ingredients-{index}-quantity"] = quantity
        values[f"ingredients-{index}-quantity_unit"] = "g"
    values.update(overrides)
    return values


def ingredient_data(**overrides: str) -> dict[str, str]:
    values = {
        "name": "Sugar",
        "brand": "Sweet Co",
        "place_of_purchase": "Market",
        "package_weight": "500",
        "package_weight_unit": "g",
        "package_price": "3.20",
    }
    values.update(overrides)
    return values


def break_formset_save(monkeypatch) -> DatabaseError:
    """Make the recipe's ingredient rows fail to save inside the transaction."""
    error = DatabaseError("connection to the database was lost")

    def failing_save(self, commit=True):
        raise error

    monkeypatch.setattr(views.RecipeIngredientFormSet, "save", failing_save)
    return error


def break_ingredient_save(monkeypatch) -> DatabaseError:
    error = DatabaseError("connection to the database was lost")

    def failing_save(self, commit=True):
        raise error

    monkeypatch.setattr(views.IngredientForm, "save", failing_save)
    return error


# --- The metric ----------------------------------------------------------------


def test_failure_counter_is_exported_at_zero_for_both_components(metric_reader) -> None:
    """Both series exist before any failure, so the first failure is counted too."""
    reader = metric_reader
    reader.collect()
    data = reader.get_metrics_data()
    metric = next(
        metric
        for resource_metric in data.resource_metrics
        for scope_metric in resource_metric.scope_metrics
        for metric in scope_metric.metrics
        if metric.name == METRIC_NAME
    )

    assert metric.data.is_monotonic is True
    assert failure_counts(reader) == no_failures()


def test_failure_counter_carries_the_deployment_resource_labels(metric_reader) -> None:
    app_metrics.record_component_creation_failure("recipe")

    data = metric_reader.get_metrics_data()
    attributes = data.resource_metrics[0].resource.attributes

    assert attributes["service.name"] == "recipe-app-tests"
    assert attributes["deployment.environment"] == "staging"
    assert attributes["service.version"] == "20261013-120000-abc1234"


# --- Failures that count -------------------------------------------------------


def test_recipe_save_database_error_counts_and_leaves_no_partial_recipe(
    metric_reader, monkeypatch
) -> None:
    flour = make_ingredient()
    break_formset_save(monkeypatch)
    client = Client(raise_request_exception=False)

    response = client.post(reverse("recipe-create"), recipe_data((flour, "250")))

    assert response.status_code == 500
    assert b"Server Error" in response.content
    assert not Recipe.objects.exists()
    assert not RecipeIngredient.objects.exists()
    assert failure_counts(metric_reader) == {"recipe": 1, "ingredient": 0}


def test_recipe_failure_reraises_the_original_exception(metric_reader, client, monkeypatch) -> None:
    """Counting never swallows or replaces the error Django reports."""
    flour = make_ingredient()
    error = break_formset_save(monkeypatch)

    with pytest.raises(DatabaseError) as raised:
        client.post(reverse("recipe-create"), recipe_data((flour, "250")))

    assert raised.value is error
    assert failure_counts(metric_reader) == {"recipe": 1, "ingredient": 0}


def test_ingredient_save_database_error_counts_as_an_ingredient_failure(
    metric_reader, monkeypatch
) -> None:
    break_ingredient_save(monkeypatch)
    client = Client(raise_request_exception=False)

    response = client.post(reverse("ingredient-create"), ingredient_data())

    assert response.status_code == 500
    assert b"Server Error" in response.content
    assert not Ingredient.objects.exists()
    assert failure_counts(metric_reader) == {"recipe": 0, "ingredient": 1}


def test_each_failed_create_adds_one(metric_reader, monkeypatch) -> None:
    flour = make_ingredient()
    break_formset_save(monkeypatch)
    break_ingredient_save(monkeypatch)
    client = Client(raise_request_exception=False)

    for _ in range(3):
        client.post(reverse("recipe-create"), recipe_data((flour, "250")))
    client.post(reverse("ingredient-create"), ingredient_data())

    assert failure_counts(metric_reader) == {"recipe": 3, "ingredient": 1}


def test_a_5xx_response_counts_and_is_returned_unchanged(metric_reader) -> None:
    unavailable = HttpResponse("try later", status=503)
    view = app_metrics.count_creation_failures("recipe")(lambda request: unavailable)

    response = view(RequestFactory().post("/recipes/add/"))

    assert response is unavailable
    assert failure_counts(metric_reader) == {"recipe": 1, "ingredient": 0}


# --- Requests that must not count ----------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"weight_per_unit": "-1"}, id="negative-weight"),
        pytest.param({"name": ""}, id="missing-name"),
        pytest.param({"ingredients-0-quantity": "-5"}, id="negative-quantity"),
    ],
)
def test_recipe_validation_errors_do_not_count(metric_reader, client, overrides) -> None:
    flour = make_ingredient()

    response = client.post(reverse("recipe-create"), recipe_data((flour, "250"), **overrides))

    assert response.status_code == 200
    assert not Recipe.objects.exists()
    assert failure_counts(metric_reader) == no_failures()


def test_recipe_with_the_same_ingredient_twice_does_not_count(metric_reader, client) -> None:
    flour = make_ingredient()

    response = client.post(
        reverse("recipe-create"), recipe_data((flour, "250"), (flour, "100"))
    )

    assert response.status_code == 200
    assert not Recipe.objects.exists()
    assert failure_counts(metric_reader) == no_failures()


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"package_weight": "-500"}, id="negative-weight"),
        pytest.param({"name": ""}, id="missing-name"),
    ],
)
def test_ingredient_validation_errors_do_not_count(metric_reader, client, overrides) -> None:
    response = client.post(reverse("ingredient-create"), ingredient_data(**overrides))

    assert response.status_code == 200
    assert not Ingredient.objects.exists()
    assert failure_counts(metric_reader) == no_failures()


def test_get_requests_to_create_pages_do_not_count(metric_reader, client) -> None:
    assert client.get(reverse("recipe-create")).status_code == 200
    assert client.get(reverse("ingredient-create")).status_code == 200

    assert failure_counts(metric_reader) == no_failures()


def test_successful_creates_do_not_count(metric_reader, client) -> None:
    flour = make_ingredient()

    recipe_response = client.post(reverse("recipe-create"), recipe_data((flour, "250")))
    ingredient_response = client.post(reverse("ingredient-create"), ingredient_data())

    assert recipe_response.status_code == 302
    assert ingredient_response.status_code == 302
    assert failure_counts(metric_reader) == no_failures()


def test_edits_and_deletes_do_not_count(metric_reader, client) -> None:
    flour = make_ingredient()
    sugar = make_ingredient("Sugar")
    recipe = Recipe.objects.create(name="Bread", weight_per_unit=Decimal("750.000"))
    row = RecipeIngredient.objects.create(
        recipe=recipe, ingredient=flour, quantity=Decimal("250.000"), quantity_unit="g"
    )
    edit = recipe_data((flour, "300"), **{"ingredients-INITIAL_FORMS": "1"})
    edit["ingredients-0-id"] = str(row.pk)
    edit["ingredients-0-recipe"] = str(recipe.pk)

    assert client.post(reverse("recipe-edit", args=[recipe.pk]), edit).status_code == 302
    assert (
        client.post(reverse("ingredient-edit", args=[sugar.pk]), ingredient_data()).status_code
        == 302
    )
    assert client.post(reverse("ingredient-delete", args=[sugar.pk])).status_code == 302
    assert client.post(reverse("recipe-delete", args=[recipe.pk])).status_code == 302

    assert failure_counts(metric_reader) == no_failures()


def test_a_failing_edit_does_not_count(metric_reader, monkeypatch) -> None:
    sugar = make_ingredient("Sugar")
    break_ingredient_save(monkeypatch)
    client = Client(raise_request_exception=False)

    response = client.post(reverse("ingredient-edit", args=[sugar.pk]), ingredient_data())

    assert response.status_code == 500
    assert failure_counts(metric_reader) == no_failures()


def test_exceptions_django_turns_into_4xx_do_not_count(metric_reader) -> None:
    def not_found(request):
        raise Http404("missing")

    view = app_metrics.count_creation_failures("ingredient")(not_found)

    with pytest.raises(Http404):
        view(RequestFactory().post("/ingredients/add/"))

    assert failure_counts(metric_reader) == no_failures()
