"""Text checks for the release workflows, the prod template and the release docs."""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = PROJECT_ROOT / ".github" / "workflows"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_no_workflow_checks_out_the_prod_branch() -> None:
    for workflow in WORKFLOWS.glob("*.yml"):
        text = read(workflow)
        assert not re.search(r"ref:\s*.*'prod'", text), workflow.name


def test_deploy_derives_the_checkout_commit_from_the_release_tag() -> None:
    deploy = read(WORKFLOWS / "deploy.yml")

    assert "fetch-depth: 0" in deploy
    assert r"^\d{8}-\d{6}-([0-9a-f]{7,40})$" in deploy
    assert "git rev-parse --verify" in deploy
    assert "git checkout --detach" in deploy
    assert "Commit checked out" in deploy
    assert "Release tag:" in deploy


def test_deploy_rejects_tags_without_a_commit_before_touching_containers() -> None:
    deploy = read(WORKFLOWS / "deploy.yml")

    assert "A release tag" in deploy and "is required" in deploy
    assert "required: true" in deploy.split("image_tag:")[1]
    assert "defaults to the environment name" not in deploy
    assert deploy.index("is required") < deploy.index("docker compose --env-file")


def test_deploy_uses_one_compose_file_for_both_environments() -> None:
    deploy = read(WORKFLOWS / "deploy.yml")

    assert "Copy-Item -Path compose.yaml" in deploy
    assert ".env.prod" in deploy


def test_promote_has_a_required_confirm_input_checked_first() -> None:
    promote = read(WORKFLOWS / "promote-to-production.yml")

    confirm = promote.split("confirm:")[1].split("image_tag:")[0]
    assert "required: true" in confirm
    assert "type: boolean" in confirm
    assert promote.index("Require confirmation") < promote.index("docker login")
    assert "inputs.confirm" in promote


def test_promote_reads_the_release_from_the_running_dev_container() -> None:
    promote = read(WORKFLOWS / "promote-to-production.yml")

    assert "docker compose --env-file .env ps -q web" in promote
    assert "APP_VERSION" in promote
    assert "healthy" in promote
    assert "docker pull" in promote
    assert "docker build" not in promote
    assert "needs.promote.outputs.release_tag" in promote
    assert "image_tag: prod" not in promote
    # The registry check precedes retagging so a missing tag leaves prod alone.
    assert promote.index("docker pull") < promote.index("docker tag")


def test_prod_env_template_is_tracked_with_placeholders_only() -> None:
    template = read(PROJECT_ROOT / ".env.prod.example")

    for line in (
        "COMPOSE_PROJECT_NAME=recipe-cost-calculator-prod",
        "WEB_PORT=8001",
        "DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8001,http://127.0.0.1:8001",
        "DEPLOYMENT_ENVIRONMENT=prod",
        "OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318",
        "OTEL_PYTHON_DJANGO_EXCLUDED_URLS=health/",
        "DJANGO_SECRET_KEY=replace-with-a-long-random-secret",
        "POSTGRES_PASSWORD=replace-with-a-local-database-password",
    ):
        assert line in template


def test_docs_describe_the_release_flow() -> None:
    readme = read(PROJECT_ROOT / "README.md")
    guide = read(PROJECT_ROOT / "docs" / "operator-guide.md")
    architecture = read(PROJECT_ROOT / "_docs" / "architecture.md")

    assert "merged into `prod`" not in readme
    assert "rollback" in readme.lower() or "roll back" in readme.lower()
    assert "confirm" in readme
    assert "Environments: dev and production" in guide
    assert "## Releasing and rolling back" in guide
    assert "docker inspect" in guide
    assert "APP_VERSION" in guide
    assert "8001" in architecture and "env files" in architecture


SELECT_FIRST = re.compile(r"\|\s*Select-Object\s+-First\b", re.IGNORECASE)
ASSIGNMENT_PREFIX = re.compile(r"^\s*(\$[\w:]+\s*=\s*)?[\(@]*\s*")


def native_pipes_into_select_first_then_check_exit_code(text: str) -> list[str]:
    """Lines piping a native command into Select-Object -First before a $LASTEXITCODE check.

    In Windows PowerShell 5.1, Select-Object -First stops the upstream native
    command once it has enough items, which sets $LASTEXITCODE to -1.
    """
    lines = text.splitlines()
    offenders = []
    for number, line in enumerate(lines):
        if not SELECT_FIRST.search(line):
            continue
        source = ASSIGNMENT_PREFIX.sub("", line.split("|")[0], count=1).strip()
        first_token = source.split()[0] if source else ""
        # Variables ($x) and PowerShell cmdlets (Verb-Noun) are not native commands.
        if not first_token or first_token.startswith("$") or "-" in first_token:
            continue
        following = "\n".join(lines[number + 1 : number + 4])
        if "$LASTEXITCODE" in line or "$LASTEXITCODE" in following:
            offenders.append(f"line {number + 1}: {line.strip()}")
    return offenders


def test_pattern_detector_flags_a_native_command_piped_into_select_first() -> None:
    bad = (
        "$container = (docker compose --env-file .env ps -q web | Select-Object -First 1)\n"
        "if ($LASTEXITCODE -ne 0 -or -not $container) { exit 1 }\n"
    )
    good = (
        "$ids = @(docker compose --env-file .env ps -q web)\n"
        "if ($LASTEXITCODE -ne 0) { exit 1 }\n"
        "$container = $ids | Where-Object { \"$_\".Trim() } | Select-Object -First 1\n"
        "if (-not $container) { exit 1 }\n"
    )

    assert native_pipes_into_select_first_then_check_exit_code(bad)
    assert not native_pipes_into_select_first_then_check_exit_code(good)


def test_no_workflow_pipes_a_native_command_into_select_first_before_an_exit_code_check() -> None:
    workflows = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    assert workflows

    for workflow in workflows:
        offenders = native_pipes_into_select_first_then_check_exit_code(read(workflow))
        assert not offenders, f"{workflow.name}: {offenders}"


def test_promote_collects_dev_container_ids_before_selecting_the_first() -> None:
    promote = read(WORKFLOWS / "promote-to-production.yml")

    assert "$ids = @(docker compose --env-file .env ps -q web)" in promote
    lookup = promote.split("$ids = @(docker compose --env-file .env ps -q web)")[1]
    assert lookup.index("$LASTEXITCODE") < lookup.index("Select-Object -First 1")
    assert "The dev web container is not running" in lookup
    assert "The dev web container is not healthy" in lookup
