"""OpenTelemetry setup for the Django backend.

The running application identifies itself in every emitted span and metric
through the standard OpenTelemetry resource attributes ``service.name``,
``deployment.environment``, and ``service.version``. These are read from the
environment so a single image can report different values per deployment.
"""

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

DEFAULT_SERVICE_NAME = "recipe-cost-calculator"

logger = logging.getLogger(__name__)

_configured = False
_metrics_configured = False
_warned = False


def _flag(name: str) -> bool:
    """Read a conventional true/false environment variable."""
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


def warn_if_console_only() -> None:
    """Warn once per process when production telemetry has no OTLP endpoint.

    Spans and metrics then go only to the console, which is easy to miss until
    a Grafana dashboard turns out to be empty. This only logs; a missing
    endpoint never stops startup.
    """
    global _warned

    if _warned:
        return
    if (
        os.environ.get("DJANGO_ENV") != "production"
        or _flag("OTEL_SDK_DISABLED")
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    ):
        return

    _warned = True
    logger.warning(
        "Telemetry is going to the console only: DJANGO_ENV=production but "
        "OTEL_EXPORTER_OTLP_ENDPOINT is not set. Set OTEL_EXPORTER_OTLP_ENDPOINT "
        "to export spans and metrics to an OpenTelemetry collector."
    )


def build_resource() -> Resource:
    """Build the resource attributes that identify this deployment."""
    service_name = os.environ.get("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)
    environment = os.environ.get(
        "DEPLOYMENT_ENVIRONMENT", os.environ.get("DJANGO_ENV", "development")
    )
    version = os.environ.get(
        "OTEL_SERVICE_VERSION", os.environ.get("APP_VERSION", "unknown")
    )
    return Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": environment,
            "service.version": version,
        }
    )


def setup_telemetry(exporter=None) -> None:
    """Configure the global tracer provider once at process startup.

    ``exporter`` is a testing seam: tests pass an in-memory exporter so they can
    inspect spans without a network destination. At runtime the exporter is
    chosen from the environment: an OTLP endpoint when one is configured,
    otherwise a console exporter so spans are visible in the container logs.
    Set ``OTEL_SDK_DISABLED`` to a true value to skip telemetry entirely.
    """
    global _configured

    if _flag("OTEL_SDK_DISABLED") or _configured:
        return

    if exporter is None:
        warn_if_console_only()

    trace.set_tracer_provider(build_provider(exporter))
    _configured = True


def build_provider(exporter=None) -> TracerProvider:
    """Build a tracer provider carrying this deployment's resource attributes."""
    if exporter is None:
        exporter = _resolve_exporter()

    provider = TracerProvider(resource=build_resource())
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def _resolve_exporter():
    """Choose a runtime exporter from the environment."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        # OTEL_EXPORTER_OTLP_ENDPOINT is a base URL by convention; the OTLP
        # HTTP exporter requires the full signal path.
        base = endpoint.rstrip("/")
        if not base.endswith("/v1/traces"):
            base = f"{base}/v1/traces"
        return OTLPSpanExporter(endpoint=base)
    return ConsoleSpanExporter()


def setup_metrics(reader=None) -> None:
    """Configure the global meter provider once at process startup.

    ``reader`` is a testing seam: tests pass an in-memory reader so they can
    inspect metric data without a network destination. At runtime a periodic
    reader exports metrics to an OTLP endpoint when one is configured, otherwise
    to the console. ``OTEL_SDK_DISABLED`` skips metrics the same way it skips
    traces.
    """
    global _metrics_configured

    if _flag("OTEL_SDK_DISABLED") or _metrics_configured:
        return

    if reader is None:
        reader = PeriodicExportingMetricReader(_resolve_metric_exporter())

    metrics.set_meter_provider(
        MeterProvider(resource=build_resource(), metric_readers=[reader])
    )
    _metrics_configured = True
    _configure_instruments()


def build_meter_provider(exporter=None) -> MeterProvider:
    """Build a meter provider carrying this deployment's resource attributes."""
    if exporter is None:
        exporter = _resolve_metric_exporter()

    return MeterProvider(
        resource=build_resource(),
        metric_readers=[PeriodicExportingMetricReader(exporter)],
    )


def _resolve_metric_exporter():
    """Choose a runtime metrics exporter from the environment."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        # OTEL_EXPORTER_OTLP_ENDPOINT is a base URL by convention; the OTLP
        # HTTP exporter requires the full signal path.
        base = endpoint.rstrip("/")
        if not base.endswith("/v1/metrics"):
            base = f"{base}/v1/metrics"
        return OTLPMetricExporter(endpoint=base)
    return ConsoleMetricExporter()


def _configure_instruments() -> None:
    """Create the application instruments once the provider is configured."""
    from calculator import metrics as app_metrics

    app_metrics.register_instruments()
