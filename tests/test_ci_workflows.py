"""Structure checks for the CI workflow and the deployments it gates.

The virtual environment has no YAML library and none may be added, so the
workflow files are read with a small loader for the block-style YAML subset
they use (mappings, sequences, `[a, b]` lists, quoted and plain scalars, `|`
and `>` block scalars, comments). Every scalar is kept as a string.
"""

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = PROJECT_ROOT / ".github" / "workflows"
CI_WORKFLOW = "./.github/workflows/ci.yml"
RUNNER_CONDITION = "vars.SELF_HOSTED_RUNNER == 'true'"

KEY = re.compile(r"""^(?P<key>'[^']*'|"[^"]*"|[^\s'"#][^:#]*?)\s*:(?:\s+(?P<rest>.*))?$""")


def strip_comment(text: str) -> str:
    """Remove a trailing ` # comment` that is outside quotes."""
    quote = ""
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ""
        elif char in "'\"" and (index == 0 or text[index - 1] in " [,:"):
            quote = char
        elif char == "#" and (index == 0 or text[index - 1] in " \t"):
            return text[:index].rstrip()
    return text.rstrip()


def scalar(text: str) -> str | list | dict:
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        return [scalar(item) for item in text[1:-1].split(",") if item.strip()]
    if text.startswith("{") and text.endswith("}"):
        pairs = (item.split(":", 1) for item in text[1:-1].split(",") if item.strip())
        return {scalar(key): scalar(value) for key, value in pairs}
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1].replace("''", "'") if text[0] == "'" else text[1:-1]
    return text


class WorkflowLoader:
    def __init__(self, text: str) -> None:
        self.lines = text.splitlines()
        self.index = 0

    def peek(self) -> tuple[int, str] | None:
        """Return the next significant line as (indent, text) without consuming it."""
        while self.index < len(self.lines):
            raw = self.lines[self.index]
            if raw.strip() and not raw.strip().startswith("#"):
                return len(raw) - len(raw.lstrip(" ")), strip_comment(raw.strip())
            self.index += 1
        return None

    def load(self) -> dict:
        document = self.block(0)
        assert self.peek() is None, f"unparsed line {self.index + 1}: {self.lines[self.index]!r}"
        return document

    def block(self, indent: int):
        line = self.peek()
        if line is None or line[0] < indent:
            return None
        if line[1] == "-" or line[1].startswith("- "):
            return self.sequence(line[0])
        return self.mapping(line[0])

    def mapping(self, indent: int, first: str | None = None) -> dict:
        result = {}
        while True:
            if first is not None:
                text, first = first, None
            else:
                line = self.peek()
                if line is None or line[0] < indent or line[1].startswith("- ") or line[1] == "-":
                    return result
                assert line[0] == indent, f"unexpected indent at line {self.index + 1}"
                text = line[1]
                self.index += 1
            match = KEY.match(text)
            assert match, f"expected a mapping key at line {self.index}: {text!r}"
            key = scalar(match["key"])
            assert key not in result, f"duplicate key {key!r} at line {self.index}"
            result[key] = self.value(match["rest"] or "", indent)

    def sequence(self, indent: int) -> list:
        items = []
        while True:
            line = self.peek()
            if line is None or line[0] != indent or not (line[1] == "-" or line[1].startswith("- ")):
                return items
            self.index += 1
            rest = line[1][1:].lstrip()
            column = indent + len(line[1]) - len(rest)
            if not rest:
                items.append(self.block(indent + 1))
            elif rest[0] not in "'\"[{" and KEY.match(rest):
                items.append(self.mapping(column, first=rest))
            else:
                items.append(self.value(rest, indent))

    def value(self, rest: str, indent: int):
        if not rest:
            line = self.peek()
            if line is None:
                return None
            if line[0] > indent:
                return self.block(line[0])
            if line[0] == indent and (line[1] == "-" or line[1].startswith("- ")):
                return self.sequence(indent)
            return None
        if rest[0] in "|>":
            return self.block_scalar(rest, indent)
        return scalar(rest)

    def block_scalar(self, header: str, indent: int) -> str:
        content = []
        while self.index < len(self.lines):
            raw = self.lines[self.index]
            if raw.strip() and len(raw) - len(raw.lstrip(" ")) <= indent:
                break
            content.append(raw)
            self.index += 1
        while content and not content[-1].strip():
            content.pop()
        margin = min((len(raw) - len(raw.lstrip(" ")) for raw in content if raw.strip()), default=0)
        lines = [raw[margin:] for raw in content]
        if header.startswith(">"):
            return " ".join(line.strip() for line in lines if line.strip())
        return "\n".join(lines) + ("" if header.endswith("-") else "\n")


def load(name: str) -> dict:
    return WorkflowLoader((WORKFLOWS / name).read_text(encoding="utf-8")).load()


def triggers(workflow: dict) -> dict:
    on = workflow["on"]
    return {name: None for name in on} if isinstance(on, list) else on


def needs(job: dict) -> list[str]:
    value = job.get("needs", [])
    return [value] if isinstance(value, str) else value


def runs(job: dict) -> list[str]:
    return [step["run"].strip() for step in job.get("steps", []) if "run" in step]


def condition(job: dict) -> str:
    return re.sub(r"^\$\{\{\s*(.*?)\s*\}\}$", r"\1", job.get("if", "").strip())


def all_workflows() -> dict[str, dict]:
    return {path.name: load(path.name) for path in sorted(WORKFLOWS.glob("*.y*ml"))}


# --- The loader itself -------------------------------------------------------


def test_loader_reads_the_yaml_constructs_the_workflows_use() -> None:
    text = (
        "name: Example  # trailing comment\n"
        "on:\n"
        "  push:\n"
        "    branches: [main, 'release']\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  one:\n"
        "    if: vars.FLAG == 'true'\n"
        "    steps:\n"
        "      - name: First\n"
        "        run: |\n"
        "          echo one  # kept\n"
        "\n"
        "          echo two\n"
        "      - uses: actions/checkout@v4\n"
        "        with:\n"
        "          python-version: \"3.13\"\n"
        "    options: >-\n"
        "      --a 1\n"
        "      --b 2\n"
        "    ports:\n"
        "      - 5432:5432\n"
    )

    assert WorkflowLoader(text).load() == {
        "name": "Example",
        "on": {"push": {"branches": ["main", "release"]}, "workflow_dispatch": None},
        "jobs": {
            "one": {
                "if": "vars.FLAG == 'true'",
                "steps": [
                    {"name": "First", "run": "echo one  # kept\n\necho two\n"},
                    {"uses": "actions/checkout@v4", "with": {"python-version": "3.13"}},
                ],
                "options": "--a 1 --b 2",
                "ports": ["5432:5432"],
            }
        },
    }


def test_every_workflow_file_parses_with_a_name_triggers_and_jobs() -> None:
    workflows = all_workflows()

    assert {"ci.yml", "build.yml", "deploy.yml", "promote-to-production.yml", "deploy-observability.yml"} <= set(workflows)
    for name, workflow in workflows.items():
        assert workflow["name"], name
        assert triggers(workflow), name
        assert workflow["jobs"], name


# --- The CI workflow ---------------------------------------------------------


def test_ci_is_named_ci_and_runs_on_pull_requests_calls_and_by_hand_but_not_on_push() -> None:
    ci = load("ci.yml")

    assert ci["name"] == "CI"
    assert set(triggers(ci)) == {"pull_request", "workflow_call", "workflow_dispatch"}
    # A pull_request filter would skip some pull requests.
    assert not triggers(ci)["pull_request"]


def test_ci_needs_no_secrets_and_grants_only_contents_read() -> None:
    ci = load("ci.yml")
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")

    assert ci["permissions"] == {"contents": "read"}
    assert all("permissions" not in job for job in ci["jobs"].values())
    assert "secrets." not in text
    assert "vars." not in text


def test_every_ci_job_runs_on_github_hosted_ubuntu_with_python_313_and_requirements_only() -> None:
    jobs = load("ci.yml")["jobs"]

    assert set(jobs) == {"tests", "integration"}
    for name, job in jobs.items():
        assert job["runs-on"] == "ubuntu-latest", name
        uses = [step["uses"] for step in job["steps"] if "uses" in step]
        assert all(action.startswith("actions/") for action in uses), name
        setup = [step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python@")]
        assert len(setup) == 1 and setup[0]["with"]["python-version"] == "3.13", name
        installs = [command for command in runs(job) if "pip install" in command]
        assert installs == ["python -m pip install -r requirements.txt"], name


def test_tests_job_runs_pytest_against_a_postgresql_17_service_and_proves_it() -> None:
    tests = load("ci.yml")["jobs"]["tests"]
    services = tests["services"]

    assert len(services) == 1
    postgres = next(iter(services.values()))
    assert re.fullmatch(r"postgres:17(\.\d+)*(-[a-z0-9.]+)?", postgres["image"])
    assert "--health-cmd" in postgres["options"] and "pg_isready" in postgres["options"]
    host_port = postgres["ports"][0].split(":")[0]

    env = tests["env"]
    assert env["DJANGO_DB_ENGINE"] == "django.db.backends.postgresql"
    assert env["DJANGO_DB_HOST"] in {"localhost", "127.0.0.1"}
    assert env["DJANGO_DB_PORT"] == host_port
    assert env["DJANGO_DB_NAME"] == postgres["env"]["POSTGRES_DB"]
    assert env["DJANGO_DB_USER"] == postgres["env"]["POSTGRES_USER"]
    assert env["DJANGO_DB_PASSWORD"] == postgres["env"]["POSTGRES_PASSWORD"]
    assert "DJANGO_ENV" not in env
    # tests/test_ci_database.py fails the run unless the suite used this vendor.
    assert env["CI_EXPECTED_DATABASE_VENDOR"] == "postgresql"
    assert (PROJECT_ROOT / "tests" / "test_ci_database.py").is_file()

    commands = runs(tests)
    assert commands[-1] == "python -m pytest"
    assert commands.index("python -m pip install -r requirements.txt") < commands.index("python -m pytest")


def test_integration_job_installs_chromium_then_runs_compose_then_e2e_without_secrets_or_variables() -> None:
    integration = load("ci.yml")["jobs"]["integration"]

    assert runs(integration) == [
        "python -m pip install -r requirements.txt",
        "python -m playwright install --with-deps chromium",
        "python -m pytest -m compose",
        "python -m pytest e2e",
    ]
    assert "env" not in integration
    assert "secrets." not in repr(integration) and "vars." not in repr(integration)


def test_no_ci_job_or_step_hides_a_failure() -> None:
    for name, job in load("ci.yml")["jobs"].items():
        assert "continue-on-error" not in job, name
        assert "if" not in job, name
        for step in job["steps"]:
            assert "continue-on-error" not in step, (name, step)
            assert "if" not in step, (name, step)
            assert "shell" not in step, (name, step)
            command = step.get("run", "")
            assert "|| true" not in command and "|| exit 0" not in command, (name, step)


# --- Gating the build and dev deploy on the tests ----------------------------


def test_push_to_main_runs_ci_once_through_build_before_building_and_deploying_dev() -> None:
    build = load("build.yml")
    jobs = build["jobs"]

    assert triggers(build)["push"] == {"branches": ["main"]}
    assert jobs["ci"]["uses"] == CI_WORKFLOW
    assert needs(jobs["build"]) == ["ci"]
    assert needs(jobs["deploy-dev"]) == ["build"]
    # No status function, so a failed or cancelled test run skips both jobs.
    for name in ("build", "deploy-dev"):
        assert not re.search(r"always\(\)|failure\(\)|cancelled\(\)", condition(jobs[name])), name

    # build.yml is the only caller of ci.yml, and ci.yml itself has no push
    # trigger, so a push to main starts the tests exactly once.
    callers = [
        (workflow_name, job_name)
        for workflow_name, workflow in all_workflows().items()
        for job_name, job in workflow["jobs"].items()
        if job.get("uses") == CI_WORKFLOW
    ]
    assert callers == [("build.yml", "ci")]
    assert "push" not in triggers(load("ci.yml"))


def test_build_still_tags_pushes_and_deploys_dev_when_the_runner_is_enabled() -> None:
    jobs = load("build.yml")["jobs"]
    build, deploy = jobs["build"], jobs["deploy-dev"]

    assert build["runs-on"] == "self-hosted"
    assert build["outputs"] == {"image_tag": "${{ steps.image.outputs.tag }}"}
    script = "\n".join(runs(build))
    assert 'ToString("yyyyMMdd-HHmmss")' in script
    assert 'docker build --build-arg "APP_VERSION=${tag}" -t "${image}:${tag}" -t "${image}:dev" .' in script
    assert 'docker push "${image}:${tag}"' in script
    assert 'docker push "${image}:dev"' in script
    assert deploy["uses"] == "./.github/workflows/deploy.yml"
    assert deploy["with"] == {"environment": "dev", "image_tag": "${{ needs.build.outputs.image_tag }}"}
    assert deploy["secrets"] == "inherit"


# --- Self-hosted jobs on repositories without a runner -----------------------


@pytest.mark.parametrize(
    ("workflow", "job"),
    [("build.yml", "build"), ("build.yml", "deploy-dev"), ("deploy-observability.yml", "deploy")],
)
def test_automatic_self_hosted_job_runs_only_when_the_runner_variable_is_true(workflow, job) -> None:
    assert condition(load(workflow)["jobs"][job]) == RUNNER_CONDITION


def test_every_self_hosted_job_an_automatic_trigger_starts_is_gated_on_the_runner_variable() -> None:
    automatic = {"push", "pull_request", "pull_request_target", "schedule", "workflow_run"}
    for name, workflow in all_workflows().items():
        if not automatic & set(triggers(workflow)):
            continue
        for job_name, job in workflow["jobs"].items():
            if job.get("runs-on") == "self-hosted" or job.get("uses") == "./.github/workflows/deploy.yml":
                assert condition(job) == RUNNER_CONDITION, (name, job_name)


def test_tests_never_depend_on_the_runner_variable() -> None:
    assert "SELF_HOSTED_RUNNER" not in (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "if" not in load("build.yml")["jobs"]["ci"]


@pytest.mark.parametrize("workflow", ["deploy.yml", "promote-to-production.yml"])
def test_manual_deploy_and_promote_workflows_are_not_gated(workflow) -> None:
    loaded = load(workflow)

    assert "SELF_HOSTED_RUNNER" not in (WORKFLOWS / workflow).read_text(encoding="utf-8")
    assert set(triggers(loaded)) <= {"workflow_dispatch", "workflow_call"}
    for job in loaded["jobs"].values():
        assert "if" not in job


# --- Node.js 24 action versions ----------------------------------------------

# The first majors of these actions that run on Node.js 24 instead of the
# deprecated Node.js 20.
NODE24_ACTIONS = ("actions/checkout", "actions/setup-python")
NODE24_MINIMUM_MAJOR = 7
NODE24_ACTION_MENTION = re.compile(r"actions/(?:checkout|setup-python)\b[^\s'\"#]*")


def step_actions(workflow: dict) -> list[str]:
    return [
        step["uses"]
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if "uses" in step
    ]


def targets_node20(reference: str) -> bool:
    """True when a checkout or setup-python reference is not a v7-or-later tag.

    A ref without a `vN` major, such as a branch or commit SHA, also counts:
    nothing proves it runs on Node.js 24.
    """
    action, _, ref = reference.partition("@")
    assert action in NODE24_ACTIONS, reference
    major = re.fullmatch(r"v(\d+)(\.\d+){0,2}", ref)
    return major is None or int(major[1]) < NODE24_MINIMUM_MAJOR


@pytest.mark.parametrize(
    ("reference", "outdated"),
    [
        ("actions/checkout@v4", True),
        ("actions/checkout@v6", True),
        ("actions/setup-python@v5", True),
        ("actions/setup-python@v6.1.0", True),
        ("actions/checkout@main", True),
        ("actions/checkout", True),
        ("actions/checkout@v7", False),
        ("actions/checkout@v7.0.0", False),
        ("actions/setup-python@v7", False),
        ("actions/setup-python@v8", False),
    ],
)
def test_version_check_flags_checkout_and_setup_python_below_major_7(reference, outdated) -> None:
    assert targets_node20(reference) is outdated


def test_no_workflow_uses_checkout_or_setup_python_below_major_7() -> None:
    for name in all_workflows():
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        mentions = NODE24_ACTION_MENTION.findall(text)
        outdated = [reference for reference in mentions if targets_node20(reference)]
        assert outdated == [], name


def test_workflow_action_references_are_exactly_the_node24_checkout_and_setup_python() -> None:
    checkout, setup_python = "actions/checkout@v7", "actions/setup-python@v7"

    assert {name: step_actions(workflow) for name, workflow in all_workflows().items()} == {
        "build.yml": [checkout],
        "ci.yml": [checkout, setup_python, checkout, setup_python],
        "deploy-observability.yml": [checkout],
        "deploy.yml": [checkout],
        "promote-to-production.yml": [],
    }
    # Every reference the text mentions is one of those parsed steps.
    for name, workflow in all_workflows().items():
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert NODE24_ACTION_MENTION.findall(text) == step_actions(workflow), name


def test_setup_python_keeps_its_python_pip_cache_and_requirements_inputs() -> None:
    for name, job in load("ci.yml")["jobs"].items():
        setup = [step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python@")]
        assert [step["with"] for step in setup] == [
            {"python-version": "3.13", "cache": "pip", "cache-dependency-path": "requirements.txt"}
        ], name
        checkout = [step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")]
        assert len(checkout) == 1 and "with" not in checkout[0], name


def test_readme_requires_a_self_hosted_runner_that_can_run_node24_actions() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    ci_section = " ".join(readme.split("## CI/CD", 1)[1].split("\n## ", 1)[0].split())

    assert "runner must be version 2.327.1 or later" in ci_section
    assert "Node.js 24" in ci_section


# --- Documentation -----------------------------------------------------------


def test_readme_documents_ci_the_gate_the_runner_variable_and_local_commands() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    ci_section = readme.split("## CI/CD", 1)[1].split("\n## ", 1)[0]
    table = ci_section.split("### Required repository configuration", 1)[1]

    assert ".github/workflows/ci.yml" in ci_section
    assert "**tests**" in ci_section and "**integration**" in ci_section
    assert "pull request" in ci_section
    assert re.search(r"^\| `SELF_HOSTED_RUNNER` \| Variable \|", table, re.MULTILINE)
    for command in (
        "python -m pytest",
        "python -m pytest -m compose",
        "python -m playwright install --with-deps chromium",
        "python -m pytest e2e",
    ):
        assert command in readme
    for variable in ("DJANGO_DB_ENGINE", "DJANGO_DB_NAME", "DJANGO_DB_USER", "DJANGO_DB_PASSWORD", "DJANGO_DB_HOST", "DJANGO_DB_PORT"):
        assert variable in readme


def test_operator_guide_and_architecture_describe_the_gated_pipeline() -> None:
    guide = (PROJECT_ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")
    architecture = (PROJECT_ROOT / "_docs" / "architecture.md").read_text(encoding="utf-8")

    for document in (guide, architecture):
        assert "ci.yml" in document
        assert "SELF_HOSTED_RUNNER" in document
