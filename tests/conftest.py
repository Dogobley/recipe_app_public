"""Fixtures shared by the application metrics test modules."""

import pytest
from opentelemetry import metrics
from opentelemetry.metrics import _internal as metrics_internal
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.util._once import Once

from calculator import metrics as app_metrics
from config import telemetry


@pytest.fixture
def metric_reader(monkeypatch):
    """Install a fresh meter provider whose data an in-memory reader can inspect.

    The OpenTelemetry API allows only one global meter provider per process, so
    reset the internal singleton before installing each test's provider.
    """
    monkeypatch.setattr(metrics_internal, "_METER_PROVIDER", None, raising=False)
    monkeypatch.setattr(metrics_internal, "_METER_PROVIDER_SET_ONCE", Once(), raising=False)
    monkeypatch.setenv("OTEL_SERVICE_NAME", "recipe-app-tests")
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "staging")
    monkeypatch.setenv("APP_VERSION", "20261013-120000-abc1234")

    reader = InMemoryMetricReader()
    provider = MeterProvider(
        resource=telemetry.build_resource(),
        metric_readers=[reader],
    )
    metrics.set_meter_provider(provider)
    app_metrics.register_instruments()
    return reader
