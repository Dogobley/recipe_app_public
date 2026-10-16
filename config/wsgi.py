"""WSGI configuration for the project."""

import os

from django.core.wsgi import get_wsgi_application
from opentelemetry.instrumentation.django import DjangoInstrumentor

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config import telemetry

telemetry.setup_telemetry()
telemetry.setup_metrics()
if not DjangoInstrumentor().is_instrumented_by_opentelemetry:
    DjangoInstrumentor().instrument()

application = get_wsgi_application()
