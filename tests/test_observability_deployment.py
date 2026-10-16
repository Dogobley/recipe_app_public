"""Text checks for the Deploy observability workflow and the stack's separation.

The live criteria of Issue 27 (an idempotent re-run, kept volumes, unchanged
application containers, the application surviving a stopped stack, and both
environments in Prometheus) need the self-hosted runner and Docker; they are
operator checks recorded in the issue.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_release_workflows import native_pipes_into_select_first_then_check_exit_code

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy-observability.yml"
APP_COMPOSE = PROJECT_ROOT / "compose.yaml"
STACK_DIR = PROJECT_ROOT / "observability"
STACK_COMPOSE = STACK_DIR / "compose.yaml"
ENV_EXAMPLE = STACK_DIR / "env.example"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def top_level_keys(compose: str, section: str) -> set[str]:
    """Names declared directly under a top-level Compose section."""
    keys: set[str] = set()
    inside = False
    for line in compose.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            inside = line.rstrip() == f"{section}:"
            continue
        match = re.match(r"^  ([\w.-]+):", line)
        if inside and match:
            keys.add(match.group(1))
    return keys


def service_block(compose: str, service: str) -> str:
    """The service's lines, up to the next blank line."""
    return compose.split(f"\n  {service}:\n")[1].split("\n\n")[0]


# Workflow triggers and style


def test_workflow_is_named_and_runs_by_hand_or_on_observability_changes() -> None:
    workflow = read(WORKFLOW)

    assert workflow.startswith("name: Deploy observability\n")
    assert "workflow_dispatch:" in workflow
    push = workflow.split("push:")[1].split("permissions:")[0]
    assert "branches: [main]" in push
    assert "'observability/**'" in push


def test_workflow_follows_the_self_hosted_powershell_style() -> None:
    workflow = read(WORKFLOW)

    assert "runs-on: self-hosted" in workflow
    run_steps = workflow.count("run: |")
    assert run_steps >= 4
    assert workflow.count("shell: powershell") == run_steps
    assert workflow.count("$ErrorActionPreference = 'Stop'") == run_steps


def test_guard_scans_the_observability_workflow_and_it_passes() -> None:
    workflows = sorted(WORKFLOW.parent.glob("*.yml"))

    assert WORKFLOW in workflows
    assert not native_pipes_into_select_first_then_check_exit_code(read(WORKFLOW))


# Deploy folder and Compose project


def test_workflow_copies_the_stack_to_the_folder_named_by_the_repository_variable() -> None:
    workflow = read(WORKFLOW)

    assert "OBSERVABILITY_PATH: ${{ vars.OBSERVABILITY_PATH }}" in workflow
    assert "Resolve-Path 'observability'" in workflow
    assert "Copy-Item -LiteralPath $sourceFile -Destination $target" in workflow
    # The deploy folder must not be inside the runner's work directory.
    assert "actions-runner\\_work" in workflow
    assert workflow.index("Copy-Item") < workflow.index("up -d")
    assert workflow.index("Set-Location $env:DEPLOY_PATH") < workflow.index("up -d")


def test_stack_bind_mounts_only_files_next_to_its_compose_file() -> None:
    compose = read(STACK_COMPOSE)
    bind_sources = re.findall(r"^\s*- (\S+?):/", compose, re.MULTILINE)
    named_volumes = top_level_keys(compose, "volumes")

    for source in bind_sources:
        assert source.startswith("./") or source in named_volumes, source
    assert "_work" not in compose


def test_stack_keeps_the_observability_project_name_and_its_volumes() -> None:
    compose = read(STACK_COMPOSE)
    workflow = read(WORKFLOW)

    assert compose.startswith("name: observability\n")
    assert top_level_keys(compose, "volumes") == {
        "prometheus_data",
        "loki_data",
        "tempo_data",
        "grafana_data",
    }
    compose_calls = re.findall(r"docker compose [^\r\n]*", workflow)
    deploy_folder_calls = [call for call in compose_calls if "-f observability/compose.yaml" not in call]
    assert deploy_folder_calls
    for call in deploy_folder_calls:
        assert "--project-name observability" in call, call


def test_workflow_never_forces_recreation_or_removes_containers() -> None:
    workflow = read(WORKFLOW)

    for forbidden in (
        "--force-recreate",
        "--renew-anon-volumes",
        "--always-recreate-deps",
        "--build",
        "--remove-orphans",
        " down",
        " rm ",
        "docker volume",
    ):
        assert forbidden not in workflow, forbidden
    # Unchanged files are left alone, so bind-mounted config is not rewritten.
    assert "Get-FileHash" in workflow
    # A changed config is loaded with a restart only when `up` kept the container.
    assert "$after -eq $before[$service]" in workflow
    assert "restart $service" in workflow


def test_images_stay_pinned() -> None:
    images = re.findall(r"image:\s*(\S+)", read(STACK_COMPOSE))

    assert len(images) == 5
    for image in images:
        tag = image.rsplit(":", 1)[-1]
        assert ":" in image and tag != "latest" and re.search(r"\d", tag), image


# Readiness


def test_run_is_green_only_when_every_service_is_ready() -> None:
    workflow = read(WORKFLOW)

    for name, url in (
        ("Prometheus", "http://localhost:9090/-/ready"),
        ("Loki", "http://localhost:3100/ready"),
        ("Tempo", "http://localhost:3200/ready"),
        ("Grafana", "http://localhost:3000/api/health"),
        ("OpenTelemetry Collector", "http://localhost:8888/metrics"),
    ):
        assert f"Name = '{name}'" in workflow
        assert f"Url = '{url}'" in workflow
    assert "is not ready" in workflow
    assert "$($check.Name) is not ready" in workflow
    readiness = workflow.split("Wait for every service to be ready")[1]
    assert "exit 1" in readiness


# Credentials


def test_grafana_credentials_come_from_the_env_file_and_are_required() -> None:
    grafana = service_block(read(STACK_COMPOSE), "grafana")

    assert "GF_SECURITY_ADMIN_USER: ${GRAFANA_ADMIN_USER:?" in grafana
    assert "GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:?" in grafana
    assert not re.search(r"GF_SECURITY_ADMIN_(USER|PASSWORD):\s*admin\b", grafana)
    assert 'GF_AUTH_ANONYMOUS_ENABLED: "false"' in grafana
    assert 'GF_USERS_ALLOW_SIGN_UP: "false"' in grafana


def test_env_example_is_committed_with_placeholders_only() -> None:
    example = read(ENV_EXAMPLE)
    gitignore = read(PROJECT_ROOT / ".gitignore").splitlines()
    values = dict(
        line.split("=", 1)
        for line in example.splitlines()
        if line.strip() and not line.startswith("#")
    )

    assert set(values) == {"GRAFANA_ADMIN_USER", "GRAFANA_ADMIN_PASSWORD"}
    assert values["GRAFANA_ADMIN_PASSWORD"].startswith("replace-with-")
    # The real file is `.env` (ignored); the example's name is not ignored.
    assert ".env" in gitignore
    assert not any(pattern.strip() in {"env.example", "*.example"} for pattern in gitignore)


def test_workflow_fails_on_a_missing_env_file_or_password_before_changing_anything() -> None:
    workflow = read(WORKFLOW)
    first_change = min(workflow.index("Copy-Item"), workflow.index("up -d"))

    for text in (
        "Test-Path -LiteralPath $envFile",
        "is missing",
        "GRAFANA_ADMIN_PASSWORD is missing or empty",
        "$password -eq 'admin'",
        "No container was changed",
    ):
        assert text in workflow, text
        assert workflow.index(text) < first_change, text


def test_workflow_applies_the_password_without_printing_it() -> None:
    workflow = read(WORKFLOW)

    assert "::add-mask::$password" in workflow
    assert "reset-admin-password --password-from-stdin" in workflow
    assert "Write-Host $password" not in workflow
    assert "Get-Content" not in workflow
    assert "http://localhost:3000/api/user" in workflow


# Fix after the first live run: under `chcp 65001` (which the runner runs),
# `$password | docker ...` in Windows PowerShell sent a UTF-8 BOM before the
# password, so Grafana stored BOM + password and rejected the real one.


def workflow_step(name: str) -> str:
    return read(WORKFLOW).split(f"- name: {name}")[1].split("\n      - name:")[0]


def step_script(name: str) -> str:
    script = []
    for line in workflow_step(name).split("run: |\n", 1)[1].splitlines():
        if line.strip() and not line.startswith(" " * 10):
            break  # comments that introduce the next step
        script.append(line[10:])
    return "\n".join(script)


def test_password_is_written_as_exact_bytes_not_piped() -> None:
    step = workflow_step("Apply the Grafana admin password")

    assert "$password |" not in step
    assert (
        "Invoke-Native 'docker' 'compose --project-name observability exec -T grafana "
        "grafana cli admin reset-admin-password --password-from-stdin' $passwordBytes"
    ) in step
    assert '(New-Object System.Text.UTF8Encoding $false).GetBytes($password + "`n")' in step
    assert "[Console]::InputEncoding = $utf8" in step
    # The password never appears in a process's arguments.
    assert not re.search(r"Invoke-Native\s+'docker'\s+[^\n]*\$password\b", step)


def test_compose_config_dollar_escaping_is_undone_in_both_steps() -> None:
    assert read(WORKFLOW).count(".Replace('$$', '$')") == 2


def test_login_failure_names_the_real_cause() -> None:
    step = workflow_step("Apply the Grafana admin password")

    for marker, message in (
        ("too many consecutive incorrect login attempts", "temporarily blocked logins"),
        (r"identity\.not-found", "has no user named"),
        (r"password-auth\.invalid", "rejected the password just applied"),
    ):
        assert marker in step, marker
        assert message in step, message
    # Only the log line of this check counts, not older failures.
    assert "--since $checkedAt" in step
    assert "path=/api/user" in step


def test_env_file_pre_check_rejects_compose_dollar_and_comment_traps() -> None:
    step = workflow_step("Check the deploy folder and the Grafana credentials")

    assert "Write each $ as $$, or wrap the whole value in single quotes" in step
    assert "Compose treats as the start of a comment" in step
    assert step.index("[System.IO.File]::ReadAllLines($envFile)") < step.index("docker compose")


def test_env_example_explains_quoting() -> None:
    example = read(ENV_EXAMPLE)

    assert "$$" in example
    assert "single quotes" in example


windows_powershell = pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("powershell") is None,
    reason="needs Windows PowerShell, like the self-hosted runner",
)


@windows_powershell
def test_invoke_native_sends_exact_utf8_bytes_under_code_page_65001(tmp_path: Path) -> None:
    script = step_script("Apply the Grafana admin password")
    function = re.search(r"^function Invoke-Native.*?^}$", script, re.MULTILINE | re.DOTALL).group(0)
    password = "Pa$s #%&'\"\u00f1\u00e9-1"
    (tmp_path / "password.txt").write_text(password, encoding="utf-8")
    (tmp_path / "echo_stdin.py").write_text(
        "import sys\nsys.stdout.write(sys.stdin.buffer.read().hex())\n", encoding="utf-8"
    )
    output = tmp_path / "stdin.hex"
    probe = "\n".join(
        (
            "$ErrorActionPreference = 'Stop'",
            function,
            f"$password = [IO.File]::ReadAllText('{tmp_path / 'password.txt'}', [Text.Encoding]::UTF8)",
            '$bytes = (New-Object System.Text.UTF8Encoding $false).GetBytes($password + "`n")',
            f"$result = Invoke-Native '{sys.executable}' '-I \"{tmp_path / 'echo_stdin.py'}\"' $bytes",
            f"[IO.File]::WriteAllText('{output}', $result.StdOut)",
        )
    )
    (tmp_path / "probe.ps1").write_text(probe, encoding="utf-8-sig")
    # The runner switches its console to UTF-8 with `chcp 65001` first.
    (tmp_path / "probe.cmd").write_text(
        "@echo off\r\nchcp 65001 >nul\r\n"
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{tmp_path / "probe.ps1"}"\r\n',
        encoding="ascii",
    )

    subprocess.run(["cmd", "/c", str(tmp_path / "probe.cmd")], check=True, timeout=60)

    assert bytes.fromhex(output.read_text()) == (password + "\n").encode("utf-8")


def run_credentials_check(tmp_path: Path, password_line: str) -> subprocess.CompletedProcess:
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    (deploy / ".env").write_text(f"GRAFANA_ADMIN_USER=admin\n{password_line}\n", encoding="utf-8")
    (tmp_path / "check.ps1").write_text(
        step_script("Check the deploy folder and the Grafana credentials"), encoding="utf-8-sig"
    )
    powershell_dir = str(Path(shutil.which("powershell")).parent)
    environment = {
        "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        "OBSERVABILITY_PATH": str(deploy),
        "GITHUB_WORKSPACE": str(tmp_path / "workspace"),
        "GITHUB_ENV": str(tmp_path / "github_env"),
        # No docker on PATH: the pre-check must fail before Compose runs.
        "PATH": powershell_dir,
    }
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(tmp_path / "check.ps1")],
        capture_output=True,
        text=True,
        env=environment,
        cwd=tmp_path,
        timeout=60,
    )


@windows_powershell
@pytest.mark.parametrize(
    ("password_line", "message"),
    (
        ("GRAFANA_ADMIN_PASSWORD=pa$word-1", "Write each $ as $$"),
        ('GRAFANA_ADMIN_PASSWORD="pa$word-1"', "Write each $ as $$"),
        ("GRAFANA_ADMIN_PASSWORD=with space #1", "start of a comment"),
    ),
)
def test_credentials_check_rejects_values_compose_would_change(
    tmp_path: Path, password_line: str, message: str
) -> None:
    result = run_credentials_check(tmp_path, password_line)

    assert result.returncode == 1
    assert message in result.stdout
    assert "No container was changed" in result.stdout
    assert "pa$word" not in result.stdout and "with space" not in result.stdout


@windows_powershell
@pytest.mark.parametrize(
    "password_line",
    (
        "GRAFANA_ADMIN_PASSWORD=pa$$word-1",
        "GRAFANA_ADMIN_PASSWORD='pa$word #1'",
        'GRAFANA_ADMIN_PASSWORD="with space #1"',
    ),
)
def test_credentials_check_accepts_escaped_or_quoted_values(tmp_path: Path, password_line: str) -> None:
    result = run_credentials_check(tmp_path, password_line)

    # It passes the pre-check and stops only at `docker compose`, which is
    # deliberately missing from PATH here.
    assert result.returncode != 0
    assert "Write each $ as $$" not in result.stdout
    assert "start of a comment" not in result.stdout
    assert "docker" in (result.stdout + result.stderr).lower()


# Separation from the application


def test_application_and_stack_share_no_services_volumes_or_networks() -> None:
    app = read(APP_COMPOSE)
    stack = read(STACK_COMPOSE)

    for section in ("services", "volumes", "networks"):
        assert not top_level_keys(app, section) & top_level_keys(stack, section), section
    for compose in (app, stack):
        assert "networks:" not in compose
        assert "external:" not in compose
        assert "network_mode" not in compose
    assert "observability" not in app
    assert "collector" not in app


def test_application_reaches_the_collector_only_through_the_host_alias() -> None:
    app = read(APP_COMPOSE)

    assert "OTEL_EXPORTER_OTLP_ENDPOINT: ${OTEL_EXPORTER_OTLP_ENDPOINT:-}" in app
    for template in (".env.example", ".env.prod.example"):
        endpoints = re.findall(
            r"OTEL_EXPORTER_OTLP_ENDPOINT=(\S+)", read(PROJECT_ROOT / template)
        )
        assert endpoints == ["http://host.docker.internal:4318"], template
    assert "http://collector:4318" not in read(STACK_DIR / "README.md")


# Docs


def test_docs_describe_the_workflow_env_file_manual_operation_and_isolation() -> None:
    for doc in (STACK_DIR / "README.md", PROJECT_ROOT / "docs" / "operator-guide.md"):
        text = read(doc)
        for required in (
            "Deploy observability",
            "OBSERVABILITY_PATH",
            "env.example",
            "GRAFANA_ADMIN_PASSWORD",
            "reset-admin-password",
            "docker compose up -d",
            "docker compose down",
            "never affects the application",
        ):
            assert required in text, f"{doc.name}: {required}"
