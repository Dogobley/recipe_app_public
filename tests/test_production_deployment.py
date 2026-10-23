"""Executable checks for the production container contract."""

import importlib
from pathlib import Path

import pytest
from django.test import Client

import config.settings as project_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def configure_production_environment(monkeypatch) -> None:
    """Supply valid production values while testing one rejected value at a time."""
    monkeypatch.setenv("DJANGO_ENV", "production")
    monkeypatch.setenv("DJANGO_SECRET_KEY", "a-real-test-secret")
    monkeypatch.setenv("DJANGO_DEBUG", "false")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "example.test")
    monkeypatch.setenv("DJANGO_CSRF_TRUSTED_ORIGINS", "https://example.test")
    monkeypatch.setenv("DJANGO_DB_ENGINE", "django.db.backends.postgresql")
    monkeypatch.setenv("DJANGO_DB_NAME", "calculator")
    monkeypatch.setenv("DJANGO_DB_USER", "calculator")
    monkeypatch.setenv("DJANGO_DB_PASSWORD", "a-real-test-password")
    monkeypatch.setenv("DJANGO_DB_HOST", "db")
    monkeypatch.setenv("DJANGO_DB_PORT", "5432")


@pytest.mark.django_db
def test_health_endpoint_confirms_django_and_database_readiness() -> None:
    response = Client().get("/health/")

    assert response.status_code == 200
    assert response.content == b"OK"


@pytest.mark.django_db
def test_collected_static_asset_is_served_by_the_application(tmp_path, settings) -> None:
    source_asset = PROJECT_ROOT / "calculator" / "static" / "calculator" / "site.css"
    settings.STATIC_ROOT = tmp_path / "staticfiles"
    settings.STATIC_URL = "static/"
    settings.DEBUG = False
    settings.STATIC_ROOT.mkdir()
    destination = settings.STATIC_ROOT / "calculator"
    destination.mkdir()
    (destination / "site.css").write_bytes(source_asset.read_bytes())

    response = Client().get("/static/calculator/site.css")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/css")


@pytest.mark.django_db
def test_static_files_come_from_the_current_static_root_after_the_url_conf_is_loaded(tmp_path, settings) -> None:
    # Load the URL configuration first, as an earlier test or a running server
    # would; STATIC_ROOT must still be read when each file is requested.
    assert Client().get("/health/").status_code == 200
    settings.DEBUG = False
    settings.STATIC_ROOT = tmp_path / "collected"
    (settings.STATIC_ROOT / "calculator").mkdir(parents=True)
    (settings.STATIC_ROOT / "calculator" / "probe.css").write_bytes(b"body { color: black; }")

    served = Client().get("/static/calculator/probe.css")
    # A source file that collectstatic has not copied into STATIC_ROOT is not served.
    not_collected = Client().get("/static/calculator/site.css")

    assert served.status_code == 200
    assert b"".join(served.streaming_content) == b"body { color: black; }"
    assert not_collected.status_code == 404


def test_production_settings_reject_a_missing_secret(monkeypatch) -> None:
    configure_production_environment(monkeypatch)
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)

    with pytest.raises(Exception, match="DJANGO_SECRET_KEY must be set"):
        importlib.reload(project_settings)

    monkeypatch.delenv("DJANGO_ENV", raising=False)
    importlib.reload(project_settings)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DJANGO_SECRET_KEY", "replace-with-a-long-random-secret"),
        ("DJANGO_DB_PASSWORD", "replace-with-a-local-database-password"),
    ],
)
def test_production_settings_reject_example_credentials(monkeypatch, name, value) -> None:
    configure_production_environment(monkeypatch)
    monkeypatch.setenv(name, value)

    with pytest.raises(Exception, match=f"{name} must not use an example placeholder"):
        importlib.reload(project_settings)

    monkeypatch.delenv("DJANGO_ENV", raising=False)
    importlib.reload(project_settings)


def test_production_image_uses_entrypoint_and_non_root_user() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (PROJECT_ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert "USER app" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert "runserver" not in dockerfile
    assert "python manage.py migrate --noinput" in entrypoint
    assert "python manage.py collectstatic --noinput" in entrypoint
    assert "exec gunicorn config.wsgi:application" in entrypoint


def test_container_shutdown_allows_gunicorn_to_finish_gracefully() -> None:
    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")
    entrypoint = (PROJECT_ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert "stop_grace_period: 35s" in compose
    assert '--graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-30}"' in entrypoint
    assert "trap stop_startup TERM INT" in entrypoint
    assert 'kill -TERM "$child_pid"' in entrypoint


def test_compose_labels_environment_without_changing_django_env() -> None:
    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "DJANGO_ENV: production" in compose
    assert "DEPLOYMENT_ENVIRONMENT: ${DEPLOYMENT_ENVIRONMENT:-production}" in compose


def test_compose_publishes_a_configurable_host_port() -> None:
    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert '"${WEB_PORT:-8000}:8000"' in compose


def test_app_version_is_baked_into_the_image_not_set_at_runtime() -> None:
    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG APP_VERSION=unknown" in dockerfile
    assert "ENV APP_VERSION=$APP_VERSION" in dockerfile
    assert 'APP_VERSION: "${IMAGE_TAG:-latest}"' in compose
    # Only the build arg mentions it; a runtime variable would override the baked value.
    assert compose.count("APP_VERSION") == 1


def test_build_workflow_passes_the_build_tag_as_app_version() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")

    assert '--build-arg "APP_VERSION=${tag}"' in workflow


def test_env_example_and_operator_guide_document_telemetry_settings() -> None:
    example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")

    for text in (example, guide):
        assert "http://host.docker.internal:4318" in text
        assert "http://collector:4318" not in text
        assert "DEPLOYMENT_ENVIRONMENT" in text
        assert "WEB_PORT" in text
    assert "baked into the image at build time" in guide
