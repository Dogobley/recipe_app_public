"""Tests for the OpenTelemetry instrumentation of the backend."""

import logging
from pathlib import Path

from django.test import Client
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

from config import telemetry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_build_resource_uses_defaults(monkeypatch) -> None:
    """Without configuration the resource identifies a development build."""
    for name in (
        "OTEL_SERVICE_NAME",
        "DEPLOYMENT_ENVIRONMENT",
        "DJANGO_ENV",
        "APP_VERSION",
        "OTEL_SERVICE_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)

    resource = telemetry.build_resource()

    assert resource.attributes["service.name"] == "recipe-cost-calculator"
    assert resource.attributes["deployment.environment"] == "development"
    assert resource.attributes["service.version"] == "unknown"


def test_build_resource_reads_environment(monkeypatch) -> None:
    """Service name, environment, and version come from the environment."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "recipe-app")
    monkeypatch.setenv("DJANGO_ENV", "production")
    monkeypatch.setenv("APP_VERSION", "20261013-120000-abc1234")

    resource = telemetry.build_resource()

    assert resource.attributes["service.name"] == "recipe-app"
    assert resource.attributes["deployment.environment"] == "production"
    assert resource.attributes["service.version"] == "20261013-120000-abc1234"


def test_build_resource_prefers_dedicated_environment_variables(monkeypatch) -> None:
    """Dedicated variables override the Django and image-tag fallbacks."""
    monkeypatch.setenv("DJANGO_ENV", "development")
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "staging")
    monkeypatch.setenv("APP_VERSION", "fallback-version")
    monkeypatch.setenv("OTEL_SERVICE_VERSION", "explicit-version")

    resource = telemetry.build_resource()

    assert resource.attributes["deployment.environment"] == "staging"
    assert resource.attributes["service.version"] == "explicit-version"


def test_provider_records_spans_with_resource_attributes(monkeypatch) -> None:
    """A span emitted through the configured provider carries the identifiers."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "recipe-app")
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "staging")
    monkeypatch.setenv("APP_VERSION", "v1.2.3")

    exporter = InMemorySpanExporter()
    provider = telemetry.build_provider(exporter=exporter)
    tracer = provider.get_tracer("tests")

    with tracer.start_as_current_span("cost-calculation"):
        pass

    provider.force_flush()
    spans = exporter.get_finished_spans()

    assert len(spans) == 1
    assert spans[0].name == "cost-calculation"
    assert spans[0].resource.attributes["service.name"] == "recipe-app"
    assert spans[0].resource.attributes["deployment.environment"] == "staging"
    assert spans[0].resource.attributes["service.version"] == "v1.2.3"


def test_setup_telemetry_respects_disable_flag(monkeypatch) -> None:
    """OTEL_SDK_DISABLED leaves the existing tracer provider untouched."""
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    provider_before = trace.get_tracer_provider()

    telemetry.setup_telemetry(exporter=InMemorySpanExporter())

    assert trace.get_tracer_provider() is provider_before


def _startup(monkeypatch, caplog, **env) -> list[str]:
    """Run server startup telemetry setup and return the warning messages."""
    for name in ("DJANGO_ENV", "OTEL_SDK_DISABLED", "OTEL_EXPORTER_OTLP_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(telemetry, "_configured", False)
    monkeypatch.setattr(telemetry, "_warned", False)
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", lambda provider: None)

    with caplog.at_level(logging.WARNING, logger=telemetry.logger.name):
        telemetry.setup_telemetry()
    return [r.getMessage() for r in caplog.records if r.name == telemetry.logger.name]


def test_production_without_endpoint_warns_once_naming_the_variable(
    monkeypatch, caplog
) -> None:
    """Console-only production telemetry is announced at startup."""
    messages = _startup(monkeypatch, caplog, DJANGO_ENV="production")

    assert len(messages) == 1
    assert "console" in messages[0]
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in messages[0]


def test_blank_endpoint_in_production_still_warns(monkeypatch, caplog) -> None:
    """An empty endpoint, as compose passes it, counts as unset."""
    messages = _startup(
        monkeypatch, caplog, DJANGO_ENV="production", OTEL_EXPORTER_OTLP_ENDPOINT=""
    )

    assert len(messages) == 1


def test_warning_is_not_repeated_by_later_setup_or_requests(
    monkeypatch, caplog
) -> None:
    """The warning is a startup message only: later calls and requests are silent."""
    messages = _startup(monkeypatch, caplog, DJANGO_ENV="production")
    assert len(messages) == 1

    caplog.clear()
    monkeypatch.setattr(telemetry, "_configured", False)
    with caplog.at_level(logging.WARNING, logger=telemetry.logger.name):
        telemetry.setup_telemetry()
        Client().get("/")
        Client().get("/")

    assert [r for r in caplog.records if r.name == telemetry.logger.name] == []


def test_no_warning_when_endpoint_is_set(monkeypatch, caplog) -> None:
    messages = _startup(
        monkeypatch,
        caplog,
        DJANGO_ENV="production",
        OTEL_EXPORTER_OTLP_ENDPOINT="http://collector:4318",
    )

    assert messages == []


def test_no_warning_when_sdk_is_disabled(monkeypatch, caplog) -> None:
    messages = _startup(
        monkeypatch, caplog, DJANGO_ENV="production", OTEL_SDK_DISABLED="true"
    )

    assert messages == []


def test_no_warning_outside_production(monkeypatch, caplog) -> None:
    assert _startup(monkeypatch, caplog, DJANGO_ENV="development") == []
    assert _startup(monkeypatch, caplog) == []


def test_missing_endpoint_in_production_does_not_stop_startup(
    monkeypatch, caplog
) -> None:
    """Startup completes and the app serves requests without an endpoint."""
    _startup(monkeypatch, caplog, DJANGO_ENV="production")

    assert telemetry._configured is True
    assert Client().get("/").status_code == 200


def test_resolve_exporter_defaults_to_console(monkeypatch) -> None:
    """Without an endpoint, spans are written to the console."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    assert isinstance(telemetry._resolve_exporter(), ConsoleSpanExporter)


def test_resolve_exporter_appends_the_traces_signal_path(monkeypatch) -> None:
    """OTEL_EXPORTER_OTLP_ENDPOINT is a base URL; the signal path is added."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    exporter = telemetry._resolve_exporter()

    assert isinstance(exporter, OTLPSpanExporter)
    assert exporter._endpoint == "http://collector:4318/v1/traces"


def test_resolve_exporter_does_not_duplicate_the_signal_path(monkeypatch) -> None:
    """A full endpoint is left unchanged."""
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318/v1/traces"
    )

    exporter = telemetry._resolve_exporter()

    assert exporter._endpoint == "http://collector:4318/v1/traces"


def test_django_request_produces_server_span_with_resource(monkeypatch) -> None:
    """A real request through Django produces a server span with identifiers."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "recipe-app-tests")
    monkeypatch.setenv("DJANGO_ENV", "production")
    monkeypatch.setenv("APP_VERSION", "20261013-120000-abc1234")

    exporter = InMemorySpanExporter()
    telemetry.setup_telemetry(exporter=exporter)

    DjangoInstrumentor().instrument()
    try:
        response = Client().get("/")
    finally:
        DjangoInstrumentor().uninstrument()

    assert response.status_code == 200

    trace.get_tracer_provider().force_flush()
    spans = exporter.get_finished_spans()
    server_spans = [span for span in spans if span.kind == SpanKind.SERVER]
    assert server_spans, "expected a server span for the request"

    span = server_spans[0]
    assert span.resource.attributes["service.name"] == "recipe-app-tests"
    assert span.resource.attributes["deployment.environment"] == "production"
    assert span.resource.attributes["service.version"] == "20261013-120000-abc1234"


def test_wsgi_and_asgi_enable_telemetry_at_startup() -> None:
    """The server entrypoints configure telemetry before serving requests."""
    wsgi_source = (PROJECT_ROOT / "config" / "wsgi.py").read_text(encoding="utf-8")
    asgi_source = (PROJECT_ROOT / "config" / "asgi.py").read_text(encoding="utf-8")

    for source in (wsgi_source, asgi_source):
        assert "telemetry.setup_telemetry()" in source
        assert "DjangoInstrumentor().instrument()" in source
