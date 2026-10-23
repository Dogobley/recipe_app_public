"""Integration tests for the one-command quick start driven by `quickstart.env`.

Run them with `python -m pytest -m compose`; they need a running Docker daemon.
The stack runs under its own project name and a free loopback port, so it never
collides with the `stack` fixture, a real quick start on port 8080, or a dev or
production deployment, and it is removed with its volume afterwards.
"""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from tests.compose.conftest import COMPOSE_VARIABLES, OVERRIDE_FILE, PROJECT_ROOT, Stack


pytestmark = pytest.mark.compose

QUICKSTART_ENV = PROJECT_ROOT / "quickstart.env"
PROJECT_NAME = "recipe-cost-calculator-quickstart-itest"
# quickstart.env sets these too; a value exported in the shell would outrank it.
QUICKSTART_VARIABLES = (*COMPOSE_VARIABLES, "COMPOSE_PROJECT_NAME", "IMAGE_REPOSITORY", "IMAGE_TAG")


def docker_compose(*args: str, cwd: Path = PROJECT_ROOT, timeout: int = 600) -> subprocess.CompletedProcess:
    environment = {name: value for name, value in os.environ.items() if name not in QUICKSTART_VARIABLES}
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=timeout,
    )


def strings_in(value) -> list[str]:
    if isinstance(value, dict):
        return [text for item in value.values() for text in strings_in(item)]
    if isinstance(value, list):
        return [text for item in value for text in strings_in(item)]
    return [value] if isinstance(value, str) else []


class QuickstartStack(Stack):
    """The quick-start stack on an isolated project name and a free loopback port."""

    def compose(self, *args: str, check: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
        result = docker_compose(
            "--project-name", PROJECT_NAME,
            "--file", str(PROJECT_ROOT / "compose.yaml"),
            "--file", str(OVERRIDE_FILE),
            "--env-file", str(self.env_file),
            *args,
            timeout=timeout,
        )
        if check and result.returncode != 0:
            raise AssertionError(
                f"docker compose {' '.join(args)} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}"
            )
        return result


@pytest.fixture(scope="module")
def quickstart_stack() -> QuickstartStack:
    deployment = QuickstartStack(QUICKSTART_ENV)
    deployment.compose("down", "--volumes", "--remove-orphans")
    try:
        deployment.up()
        yield deployment
    finally:
        deployment.compose("down", "--volumes", "--remove-orphans", check=False)


def quickstart_config() -> dict:
    """The configuration a user gets from `docker compose --env-file quickstart.env config`."""
    result = docker_compose("--env-file", "quickstart.env", "config", "--format", "json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_quickstart_config_has_no_carriage_return_in_any_value() -> None:
    values = strings_in(quickstart_config())

    assert values
    assert [value for value in values if "\r" in value] == []


def test_quickstart_config_uses_its_own_project_port_and_volume() -> None:
    config = quickstart_config()

    assert config["name"] == "recipe-cost-calculator-quickstart"
    assert [port["published"] for port in config["services"]["web"]["ports"]] == ["8080"]
    assert config["volumes"]["postgres_data"]["name"] == "recipe-cost-calculator-quickstart_postgres_data"
    assert config["networks"]["default"]["name"] == "recipe-cost-calculator-quickstart_default"
    assert config["services"]["web"]["environment"]["DEPLOYMENT_ENVIRONMENT"] == "local"


def test_compose_without_an_env_file_still_fails_fast(tmp_path) -> None:
    # An empty project directory guarantees no `.env` is picked up.
    result = docker_compose(
        "--project-directory", str(tmp_path), "--file", str(PROJECT_ROOT / "compose.yaml"), "config", "--quiet",
        cwd=tmp_path,
    )

    missing = re.search(r"required variable (\w+) is missing a value: Set (\w+)", result.stderr)

    assert result.returncode != 0
    assert missing, result.stderr
    assert missing.group(1) == missing.group(2)


def test_quickstart_services_start_and_report_healthy(quickstart_stack) -> None:
    services = quickstart_stack.services()

    assert services["db"]["Health"] == "healthy"
    assert services["web"]["Health"] == "healthy"


@pytest.mark.parametrize("path", ["/health/", "/", "/static/calculator/site.css"])
def test_quickstart_serves_the_smoke_check_urls(quickstart_stack, path) -> None:
    assert quickstart_stack.browser().get(path).status == 200
