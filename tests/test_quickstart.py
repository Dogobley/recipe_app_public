"""Checks for the one-command quick start that a fresh clone runs without a `.env`.

The running stack is covered by `tests/compose/test_quickstart_stack.py`; these
tests need neither Docker nor a database.
"""

import importlib
import re
import subprocess
from pathlib import Path

import pytest

import config.settings as project_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUICKSTART_ENV = PROJECT_ROOT / "quickstart.env"
QUICKSTART_COMMAND = "docker compose --env-file quickstart.env up --build --detach"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True)


def is_ignored(path: str) -> bool:
    """Ask git whether its ignore rules match `path`, whether or not it is tracked."""
    result = git("check-ignore", "--no-index", "--quiet", path)
    assert result.returncode in (0, 1), result.stderr
    return result.returncode == 0


def read_env_file(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            name, separator, value = line.partition("=")
            assert separator, f"Not a NAME=value line: {line!r}"
            values[name.strip()] = value
    return values


def required_compose_variables() -> set[str]:
    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")
    return set(re.findall(r"\$\{(\w+):\?", compose))


def markdown_section(document: str, heading: str) -> str:
    """Return the body of a `## heading` section up to the next `## ` heading."""
    start = document.index(f"\n## {heading}\n")
    end = document.find("\n## ", start + 1)
    return document[start : end if end != -1 else None]


# Git tracking rules


@pytest.mark.parametrize("path", [".env.example", "quickstart.env"])
def test_tracked_environment_file_is_not_ignored_so_a_fresh_clone_has_it(path) -> None:
    assert (PROJECT_ROOT / path).is_file()
    assert not is_ignored(path)


@pytest.mark.parametrize("path", [".env", ".env.prod"])
def test_deployment_environment_file_stays_ignored(path) -> None:
    assert is_ignored(path)


def test_env_example_still_holds_placeholders_only() -> None:
    example = read_env_file(PROJECT_ROOT / ".env.example")

    for name in ("DJANGO_SECRET_KEY", "POSTGRES_PASSWORD", "DJANGO_DB_PASSWORD"):
        assert example[name] in project_settings.PLACEHOLDER_VALUES


@pytest.mark.parametrize("path", ["quickstart.env", ".env.example"])
def test_environment_file_is_checked_out_with_lf_endings_on_every_os(path) -> None:
    result = git("check-attr", "eol", "--", path)

    assert result.stdout.strip() == f"{path}: eol: lf"
    assert b"\r" not in (PROJECT_ROOT / path).read_bytes()


# quickstart.env contents


def test_quickstart_env_defines_every_variable_compose_requires() -> None:
    values = read_env_file(QUICKSTART_ENV)
    required = required_compose_variables()

    assert required, "compose.yaml should still declare ${NAME:?...} checks"
    assert sorted(required - values.keys()) == []
    assert all(values[name] for name in required)


def test_quickstart_env_uses_no_placeholder_value() -> None:
    values = read_env_file(QUICKSTART_ENV)

    for name, value in values.items():
        assert value not in project_settings.PLACEHOLDER_VALUES, name
        assert "replace-with-" not in value, name


def test_quickstart_env_has_the_local_evaluation_settings() -> None:
    values = read_env_file(QUICKSTART_ENV)

    assert values["DJANGO_DEBUG"] == "false"
    assert values["COMPOSE_PROJECT_NAME"] == "recipe-cost-calculator-quickstart"
    assert values["WEB_PORT"] == "8080"
    assert values["DJANGO_ALLOWED_HOSTS"] == "localhost,127.0.0.1"
    assert values["DJANGO_CSRF_TRUSTED_ORIGINS"] == "http://localhost:8080,http://127.0.0.1:8080"
    assert values["DEPLOYMENT_ENVIRONMENT"] == "local"


def test_quickstart_env_opens_with_a_local_evaluation_only_warning() -> None:
    lines = QUICKSTART_ENV.read_text(encoding="utf-8").splitlines()
    header = []
    for line in lines:
        if not line.startswith("#"):
            break
        header.append(line.lstrip("# "))
    comment = " ".join(header)

    assert lines[0].startswith("#")
    assert "for local evaluation only" in comment
    assert "public" in comment
    assert "`.env`" in comment
    assert "`.env.prod`" in comment


def test_quickstart_values_pass_the_production_settings_checks(monkeypatch) -> None:
    values = read_env_file(QUICKSTART_ENV)
    # compose.yaml sets these for the web container from quickstart.env.
    monkeypatch.setenv("DJANGO_ENV", "production")
    for name in ("DJANGO_SECRET_KEY", "DJANGO_DEBUG", "DJANGO_ALLOWED_HOSTS", "DJANGO_CSRF_TRUSTED_ORIGINS"):
        monkeypatch.setenv(name, values[name])
    monkeypatch.setenv("DJANGO_DB_ENGINE", "django.db.backends.postgresql")
    monkeypatch.setenv("DJANGO_DB_NAME", values["POSTGRES_DB"])
    monkeypatch.setenv("DJANGO_DB_USER", values["POSTGRES_USER"])
    monkeypatch.setenv("DJANGO_DB_PASSWORD", values["POSTGRES_PASSWORD"])
    monkeypatch.setenv("DJANGO_DB_HOST", "db")
    monkeypatch.setenv("DJANGO_DB_PORT", "5432")

    try:
        reloaded = importlib.reload(project_settings)
        assert reloaded.DEBUG is False
        assert reloaded.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]
        assert reloaded.CSRF_TRUSTED_ORIGINS == ["http://localhost:8080", "http://127.0.0.1:8080"]
    finally:
        monkeypatch.delenv("DJANGO_ENV", raising=False)
        importlib.reload(project_settings)


def test_production_settings_still_reject_debug_true(monkeypatch) -> None:
    monkeypatch.setenv("DJANGO_ENV", "production")
    monkeypatch.setenv("DJANGO_SECRET_KEY", "a-real-test-secret")
    monkeypatch.setenv("DJANGO_DEBUG", "true")

    with pytest.raises(Exception, match="DJANGO_DEBUG must be false"):
        importlib.reload(project_settings)

    monkeypatch.delenv("DJANGO_ENV", raising=False)
    importlib.reload(project_settings)


# Documentation


def test_readme_opens_with_a_quick_start_section() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    first_section = re.search(r"^## (.+)$", readme, flags=re.MULTILINE)
    section = markdown_section(readme, "Quick start")

    assert first_section and first_section.group(1) == "Quick start"
    assert "Docker with Compose v2" in section
    assert QUICKSTART_COMMAND in section
    assert "http://localhost:8080/" in section
    assert "docker compose --env-file quickstart.env down`" in section
    assert "docker compose --env-file quickstart.env down -v`" in section
    assert "not for deployments" in section


def test_operator_guide_keeps_quickstart_env_out_of_deployments() -> None:
    guide = (PROJECT_ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")
    # Compare words, not line wrapping.
    section = " ".join(markdown_section(guide, "Quick start for local evaluation").split())

    assert QUICKSTART_COMMAND in section
    assert "`quickstart.env` is for local evaluation only" in section
    assert "dev and production deployments keep using `.env` and `.env.prod`" in section


@pytest.mark.parametrize("document", ["README.md", "docs/operator-guide.md"])
def test_every_documented_example_copy_has_a_source_in_a_fresh_clone(document) -> None:
    text = (PROJECT_ROOT / document).read_text(encoding="utf-8")
    sources = re.findall(r"Copy-Item\s+(\S+)", text)

    assert ".env.example" in sources
    for source in sources:
        path = source.replace("\\", "/")
        assert (PROJECT_ROOT / path).is_file(), source
        assert not is_ignored(path), source
