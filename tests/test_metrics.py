"""Tests for the OpenTelemetry metrics emitted by the calculator app."""

from decimal import Decimal
from pathlib import Path

import pytest
from django.urls import reverse
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, InMemoryMetricReader

from calculator import metrics as app_metrics
from calculator.models import Ingredient, Recipe, RecipeIngredient
from config import telemetry


pytestmark = pytest.mark.django_db

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _collected_metrics(reader) -> dict[str, object]:
    """Collect once and return the exported metrics keyed by name."""
    reader.collect()
    data = reader.get_metrics_data()
    result: dict[str, object] = {}
    for resource_metric in data.resource_metrics:
        for scope_metric in resource_metric.scope_metrics:
            for metric in scope_metric.metrics:
                result[metric.name] = metric
    return result


def make_ingredient(name: str, price: str) -> Ingredient:
    return Ingredient.objects.create(
        name=name,
        brand="Mill House",
        place_of_purchase="Market",
        package_weight=Decimal("1000.000"),
        package_weight_unit="g",
        package_price=Decimal(price),
    )


def test_resource_attributes_are_attached_to_metrics(metric_reader) -> None:
    """Metrics carry the deployment environment and deployed version."""
    app_metrics.record_recipe_created()

    data = metric_reader.get_metrics_data()
    attributes = data.resource_metrics[0].resource.attributes

    assert attributes["service.name"] == "recipe-app-tests"
    assert attributes["deployment.environment"] == "staging"
    assert attributes["service.version"] == "20261013-120000-abc1234"


def test_recipes_created_counter_increments(metric_reader) -> None:
    """Each successful recipe creation adds one to a monotonic counter."""
    app_metrics.record_recipe_created()
    app_metrics.record_recipe_created()

    metric = _collected_metrics(metric_reader)["recipes_created"]

    assert metric.data.is_monotonic is True
    points = list(metric.data.data_points)
    assert len(points) == 1
    assert points[0].value == 2


def test_recipe_views_counter_labels_each_recipe(metric_reader) -> None:
    """Recipe views are counted per recipe name."""
    app_metrics.record_recipe_view("Brownie")
    app_metrics.record_recipe_view("Brownie")
    app_metrics.record_recipe_view("Galletas")

    metric = _collected_metrics(metric_reader)["recipe_views"]

    views = {
        dict(point.attributes)["recipe"]: point.value
        for point in metric.data.data_points
    }
    assert views == {"Brownie": 2, "Galletas": 1}


def test_average_cost_gauge_reports_mean(metric_reader) -> None:
    """The average cost gauge reports the mean cost per unit across recipes."""
    flour = make_ingredient("Flour", "1000.00")  # cost per gram: 1.0
    sugar = make_ingredient("Sugar", "2000.00")  # cost per gram: 2.0

    bread = Recipe.objects.create(name="Bread", weight_per_unit=Decimal("100.000"))
    RecipeIngredient.objects.create(
        recipe=bread, ingredient=flour, quantity=Decimal("100.000"), quantity_unit="g"
    )
    cake = Recipe.objects.create(name="Cake", weight_per_unit=Decimal("100.000"))
    RecipeIngredient.objects.create(
        recipe=cake, ingredient=sugar, quantity=Decimal("100.000"), quantity_unit="g"
    )

    metric = _collected_metrics(metric_reader)["recipes_average_cost"]

    points = list(metric.data.data_points)
    assert len(points) == 1
    # Bread costs 100.00 and cake costs 200.00, so the mean is 150.00.
    assert points[0].value == pytest.approx(150.0)


def test_recipe_creation_view_increments_created_counter(metric_reader, client) -> None:
    """Creating a recipe through the web flow records one creation."""
    flour = make_ingredient("Flour", "1000.00")

    response = client.post(
        reverse("recipe-create"),
        {
            "name": "Bread",
            "weight_per_unit": "750",
            "ingredients-TOTAL_FORMS": "1",
            "ingredients-INITIAL_FORMS": "0",
            "ingredients-MIN_NUM_FORMS": "0",
            "ingredients-MAX_NUM_FORMS": "1000",
            "ingredients-0-ingredient": str(flour.pk),
            "ingredients-0-quantity": "250",
            "ingredients-0-quantity_unit": "g",
        },
    )

    assert response.status_code == 302
    metric = _collected_metrics(metric_reader)["recipes_created"]
    points = list(metric.data.data_points)
    assert len(points) == 1
    assert points[0].value == 1


def test_recipe_detail_view_increments_view_counter(metric_reader, client) -> None:
    """Viewing a recipe's detail page records one view for that recipe."""
    flour = make_ingredient("Flour", "1000.00")
    brownie = Recipe.objects.create(name="Brownie", weight_per_unit=Decimal("80.000"))
    RecipeIngredient.objects.create(
        recipe=brownie, ingredient=flour, quantity=Decimal("30.000"), quantity_unit="g"
    )

    response = client.get(reverse("recipe-detail", args=[brownie.pk]))

    assert response.status_code == 200
    metric = _collected_metrics(metric_reader)["recipe_views"]
    views = {
        dict(point.attributes)["recipe"]: point.value
        for point in metric.data.data_points
    }
    assert views == {"Brownie": 1}


def test_setup_metrics_respects_disable_flag(monkeypatch) -> None:
    """OTEL_SDK_DISABLED leaves the existing meter provider untouched."""
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    provider_before = metrics.get_meter_provider()

    telemetry.setup_metrics(reader=InMemoryMetricReader())

    assert metrics.get_meter_provider() is provider_before


def test_resolve_metric_exporter_defaults_to_console(monkeypatch) -> None:
    """Without an endpoint, metrics are written to the console."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    assert isinstance(telemetry._resolve_metric_exporter(), ConsoleMetricExporter)


def test_resolve_metric_exporter_appends_the_metrics_signal_path(monkeypatch) -> None:
    """OTEL_EXPORTER_OTLP_ENDPOINT is a base URL; the signal path is added."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    exporter = telemetry._resolve_metric_exporter()

    assert isinstance(exporter, OTLPMetricExporter)
    assert exporter._endpoint == "http://collector:4318/v1/metrics"


def test_wsgi_and_asgi_enable_metrics_at_startup() -> None:
    """The server entrypoints configure metrics before serving requests."""
    wsgi_source = (PROJECT_ROOT / "config" / "wsgi.py").read_text(encoding="utf-8")
    asgi_source = (PROJECT_ROOT / "config" / "asgi.py").read_text(encoding="utf-8")

    for source in (wsgi_source, asgi_source):
        assert "telemetry.setup_metrics()" in source
