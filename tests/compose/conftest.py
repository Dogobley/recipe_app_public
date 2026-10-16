"""Fixtures that build and drive an isolated copy of the Compose deployment."""

import json
import os
import secrets
import subprocess
from dataclasses import dataclass
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OVERRIDE_FILE = Path(__file__).resolve().parent / "compose.override.yaml"
# A dedicated project name keeps containers and the database volume separate
# from a real deployment started from this checkout.
PROJECT_NAME = "recipe-cost-calculator-itest"
COMPOSE_VARIABLES = (
    "DJANGO_SECRET_KEY",
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DJANGO_TIME_ZONE",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "WEB_PORT",
    "DEPLOYMENT_ENVIRONMENT",
)


def valid_environment() -> dict[str, str]:
    """Return a complete, non-placeholder deployment environment."""
    return {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
        "DJANGO_DEBUG": "false",
        "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "http://localhost,http://127.0.0.1",
        "DJANGO_TIME_ZONE": "UTC",
        "POSTGRES_DB": "itest",
        "POSTGRES_USER": "itest",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
    }


def write_env_file(path: Path, values: dict[str, str]) -> Path:
    path.write_text("".join(f"{name}={value}\n" for name, value in values.items()), encoding="utf-8")
    return path


def run_compose(env_file: Path, *args: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run Docker Compose against compose.yaml using only the given env file."""
    # Shell variables outrank --env-file, so drop any the developer exported.
    environment = {name: value for name, value in os.environ.items() if name not in COMPOSE_VARIABLES}
    return subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            PROJECT_NAME,
            "--project-directory",
            str(PROJECT_ROOT),
            "--file",
            str(PROJECT_ROOT / "compose.yaml"),
            "--file",
            str(OVERRIDE_FILE),
            "--env-file",
            str(env_file),
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=timeout,
    )


@dataclass
class Response:
    status: int
    url: str
    headers: dict[str, str]
    text: str


class Browser:
    """A cookie-keeping HTTP client that follows redirects like a browser."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def request(self, path: str, data: dict | None = None, headers: dict | None = None) -> Response:
        body = urlencode(data).encode() if data is not None else None
        request = Request(self.base_url + path, data=body, headers=headers or {})
        try:
            raw = self.opener.open(request, timeout=30)
        except HTTPError as error:
            raw = error
        with raw:
            return Response(raw.status, raw.url, dict(raw.headers.items()), raw.read().decode("utf-8"))

    def get(self, path: str, **kwargs) -> Response:
        return self.request(path, **kwargs)

    def submit(self, path: str, data: dict) -> Response:
        """Load a form page for its CSRF token, then post the form."""
        page = self.get(path)
        assert page.status == 200, f"GET {path} returned {page.status}"
        token = next(cookie.value for cookie in self.cookies if cookie.name == "csrftoken")
        return self.request(path, {**data, "csrfmiddlewaretoken": token})


class Stack:
    """The running Compose deployment under test."""

    def __init__(self, env_file: Path) -> None:
        self.env_file = env_file
        self.base_url = ""

    def compose(self, *args: str, check: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
        result = run_compose(self.env_file, *args, timeout=timeout)
        if check and result.returncode != 0:
            raise AssertionError(
                f"docker compose {' '.join(args)} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}"
            )
        return result

    def up(self) -> None:
        """Start every service and wait until both health checks pass."""
        result = self.compose("up", "--build", "--detach", "--wait", "--wait-timeout", "240", check=False)
        if result.returncode != 0:
            logs = self.compose("logs", "--no-color", "--tail", "80", check=False).stdout
            raise AssertionError(f"The stack did not become healthy:\n{result.stderr}\n{logs}")
        # The host port is ephemeral and changes whenever the container is recreated.
        published = self.compose("port", "web", "8000").stdout.strip()
        self.base_url = f"http://127.0.0.1:{published.rsplit(':', 1)[1]}"

    def services(self) -> dict[str, dict]:
        """Return `docker compose ps` state keyed by service name."""
        output = self.compose("ps", "--all", "--format", "json").stdout.strip()
        # Compose emits either one JSON array or one object per line.
        rows = json.loads(output) if output.startswith("[") else [json.loads(line) for line in output.splitlines()]
        return {row["Service"]: row for row in rows}

    def browser(self) -> Browser:
        return Browser(self.base_url)


@pytest.fixture(scope="session")
def stack(tmp_path_factory) -> Stack:
    env_file = write_env_file(tmp_path_factory.mktemp("compose") / "itest.env", valid_environment())
    deployment = Stack(env_file)
    # Remove leftovers from an interrupted run so every session starts empty.
    deployment.compose("down", "--volumes", "--remove-orphans")
    try:
        deployment.up()
        yield deployment
    finally:
        deployment.compose("down", "--volumes", "--remove-orphans", check=False)


@pytest.fixture
def browser(stack: Stack) -> Browser:
    return stack.browser()
