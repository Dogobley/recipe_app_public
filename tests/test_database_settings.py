"""Tests for database settings supplied by the runtime environment."""

import importlib

import pytest

import config.settings as project_settings


@pytest.fixture
def database_environment(monkeypatch):
    """Restore the settings module after changing process environment values."""
    yield monkeypatch
    monkeypatch.undo()
    importlib.reload(project_settings)


def test_postgresql_connection_uses_environment_values(database_environment) -> None:
    """PostgreSQL connection settings are supplied without embedded credentials."""
    database_environment.setenv("DJANGO_DB_ENGINE", "django.db.backends.postgresql")
    database_environment.setenv("DJANGO_DB_NAME", "calculator_test")
    database_environment.setenv("DJANGO_DB_USER", "calculator_user")
    database_environment.setenv("DJANGO_DB_PASSWORD", "test-password")
    database_environment.setenv("DJANGO_DB_HOST", "database")
    database_environment.setenv("DJANGO_DB_PORT", "5544")

    configured_settings = importlib.reload(project_settings)

    assert configured_settings.DATABASES["default"] == {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "calculator_test",
        "USER": "calculator_user",
        "PASSWORD": "test-password",
        "HOST": "database",
        "PORT": "5544",
    }
