"""OpenTelemetry metrics for the calculator application.

Business metrics are emitted through a meter that carries the deployment's
resource attributes (``service.name``, ``deployment.environment``, and
``service.version``) set by :func:`config.telemetry.build_resource`.
"""

import functools
import logging
from decimal import Decimal

from django.core.exceptions import BadRequest, PermissionDenied, SuspiciousOperation
from django.http import Http404
from opentelemetry import metrics

METER_NAME = "recipe-cost-calculator"

# Metric names follow OpenTelemetry conventions. The observability collector's
# Prometheus remote-write exporter appends the standard ``_total`` suffix to
# monotonic counters.
RECIPES_CREATED = "recipes_created"
RECIPE_VIEWS = "recipe_views"
RECIPES_AVERAGE_COST = "recipes_average_cost"
COMPONENT_CREATION_FAILURES = "component_creation_failures"

# The user-created components whose create flow is counted when it fails.
CREATION_COMPONENTS = ("recipe", "ingredient")

# Exceptions Django turns into 4xx responses. They are a rejected request, not
# a server that could not complete the create, so they are not failures.
_CLIENT_ERROR_EXCEPTIONS = (Http404, PermissionDenied, BadRequest, SuspiciousOperation)

logger = logging.getLogger(__name__)

_registered_provider = None


def _meter():
    return metrics.get_meter(METER_NAME)


def _recipes_created_counter():
    return _meter().create_counter(
        RECIPES_CREATED,
        unit="{recipe}",
        description="Number of recipes created.",
    )


def _recipe_views_counter():
    return _meter().create_counter(
        RECIPE_VIEWS,
        unit="{view}",
        description="Number of times each recipe has been viewed.",
    )


def _component_creation_failures_counter():
    return _meter().create_counter(
        COMPONENT_CREATION_FAILURES,
        unit="{failure}",
        description=(
            "Number of recipe or ingredient create requests the server could "
            "not complete (unhandled exception or 5xx response)."
        ),
    )


def record_recipe_created() -> None:
    """Increment the count of created recipes."""
    _recipes_created_counter().add(1)


def record_recipe_view(recipe_name: str) -> None:
    """Increment the view count for one recipe, labelled by its name."""
    _recipe_views_counter().add(1, {"recipe": recipe_name})


def record_component_creation_failure(component: str) -> None:
    """Increment the count of failed creates for one component type."""
    _component_creation_failures_counter().add(1, {"component": component})


def _record_failure_safely(component: str) -> None:
    """Record a failure without ever letting the metric change the response."""
    try:
        record_component_creation_failure(component)
    except Exception:  # pragma: no cover - defensive: metrics must never break a request
        logger.exception("Could not record a %s creation failure.", component)


def count_creation_failures(component: str):
    """Decorate a create view so failed create POSTs are counted.

    A failure is a POST that raises an unhandled exception or returns a 5xx
    response. The exception is re-raised unchanged and the response is
    returned unchanged, so Django still renders its normal error page.
    Validation errors (re-rendered forms), GETs and successful creates do not
    count.
    """

    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method != "POST":
                return view(request, *args, **kwargs)
            try:
                response = view(request, *args, **kwargs)
            except _CLIENT_ERROR_EXCEPTIONS:
                raise
            except Exception:
                _record_failure_safely(component)
                raise
            if response.status_code >= 500:
                _record_failure_safely(component)
            return response

        return wrapper

    return decorator


def _average_recipe_cost(options):
    """Observe the mean cost per unit across all stored recipes."""
    from calculator.models import Recipe
    from calculator.services.recipes import calculate_recipe

    costs = [calculate_recipe(recipe, 1).cost_per_unit for recipe in Recipe.objects.all()]
    if not costs:
        return []
    average = sum(costs, Decimal("0")) / Decimal(len(costs))
    return [metrics.Observation(float(average))]


def register_instruments() -> None:
    """Create the counters and observable gauges once per meter provider."""
    global _registered_provider

    provider = metrics.get_meter_provider()
    if provider is _registered_provider:
        return

    meter = _meter()
    _recipes_created_counter()
    _recipe_views_counter()
    # Start each component's failure series at zero, so Prometheus sees the
    # counter before the first failure and increase() counts that failure too.
    failures = _component_creation_failures_counter()
    for component in CREATION_COMPONENTS:
        failures.add(0, {"component": component})
    meter.create_observable_gauge(
        RECIPES_AVERAGE_COST,
        description="Average cost per unit across all recipes, in COP.",
        callbacks=[_average_recipe_cost],
    )
    _registered_provider = provider
