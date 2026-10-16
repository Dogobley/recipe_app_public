"""Static checks for the provisioned component creation failure alert.

The rule is delivered as a Grafana provisioning file, so its folder, query,
threshold, timing, no-data handling, labels and annotations can be asserted
from the repository without Docker. PyYAML is not a dependency, so the checks
read the file as text, as the dashboard checks do. Firing against live data is
the issue's live check, described in ``observability/README.md``.
"""

import json
import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROVISIONING_DIRECTORY = REPOSITORY_ROOT / "observability" / "grafana" / "provisioning"
RULE_FILE = PROVISIONING_DIRECTORY / "alerting" / "component-creation-failures.yaml"
DASHBOARD_FILE = PROVISIONING_DIRECTORY / "dashboards" / "recipe-business-metrics.json"
DASHBOARD_PROVIDER_FILE = PROVISIONING_DIRECTORY / "dashboards" / "dashboards.yaml"
COMPOSE_FILE = REPOSITORY_ROOT / "observability" / "compose.yaml"
README_FILE = REPOSITORY_ROOT / "observability" / "README.md"

PANEL_TITLE = "Component creation failures"
DEPLOYMENT_GROUPING = "sum by (service_name, deployment_environment, service_version)"


def rule_text() -> str:
    return RULE_FILE.read_text(encoding="utf-8")


def flat_rule_text() -> str:
    """The rule file with YAML line folding collapsed to single spaces."""
    return " ".join(rule_text().split())


def yaml_value(key: str) -> str:
    match = re.search(rf"^\s*(?:- )?{key}:\s*(.+)$", rule_text(), re.MULTILINE)
    assert match, f"the rule file does not set {key}"
    return match.group(1).strip()


def annotation(name: str) -> str:
    """Return a folded (>-) annotation value as one line."""
    match = re.search(
        rf"^(\s*){name}: >-\n((?:\1\s+.+\n)+)", rule_text(), re.MULTILINE
    )
    assert match, f"the rule file does not set the {name} annotation"
    return " ".join(match.group(2).split())


def dashboard() -> dict:
    return json.loads(DASHBOARD_FILE.read_text(encoding="utf-8"))


def failures_panel() -> dict:
    for panel in dashboard()["panels"]:
        if panel["title"] == PANEL_TITLE:
            return panel
    raise AssertionError(f"the dashboard has no {PANEL_TITLE!r} panel")


def test_rule_is_provisioned_from_repository_files_into_the_recipe_calculator_folder():
    """The rule must survive `down -v` and live next to the dashboard."""
    assert RULE_FILE.is_file()
    assert "./grafana/provisioning:/etc/grafana/provisioning:ro" in COMPOSE_FILE.read_text(
        encoding="utf-8"
    )
    text = rule_text()
    assert text.startswith("apiVersion: 1")
    assert yaml_value("folder") == "Recipe Calculator"
    assert yaml_value("uid") == "component-creation-failures"
    assert yaml_value("datasourceUid").startswith("prometheus")


def test_rule_and_dashboard_share_one_folder_matched_by_title():
    """A fresh Grafana volume must end up with one "Recipe Calculator" folder.

    Grafana 13 alert rule files can only name their folder by title, and
    alerting is provisioned before dashboards. A folderUid on the dashboard
    provider would therefore create a second folder with the same title, which
    would split the rule from the dashboard. Both files must name the folder by
    the same title and neither may pin a uid.
    """
    provider = DASHBOARD_PROVIDER_FILE.read_text(encoding="utf-8")
    provider_folder = re.search(r"^\s*folder:\s*(.+)$", provider, re.MULTILINE)

    assert provider_folder, "the dashboard provider does not name a folder"
    assert provider_folder.group(1).strip() == yaml_value("folder") == "Recipe Calculator"
    assert not re.search(r"^\s*folderUid:", provider, re.MULTILINE)
    assert not re.search(r"^\s*folderUid:", rule_text(), re.MULTILINE)


def test_rule_counts_failures_per_deployment_over_ten_minutes_with_increase():
    """Recipes and ingredients are added together, deployments kept apart.

    increase() handles counter resets, so a restart does not look like
    failures; grouping by environment and version keeps dev and prod (and two
    versions) separate.
    """
    expression = (
        f"{DEPLOYMENT_GROUPING} (increase(component_creation_failures_total[10m]))"
    )
    assert expression in flat_rule_text()
    assert "component=" not in flat_rule_text()
    assert "from: 600" in rule_text()


def test_rule_fires_at_three_or_more_failures():
    text = rule_text()
    assert yaml_value("condition") == "C"
    assert "type: threshold" in text
    assert "expression: A" in text
    assert re.search(r"type: gte\n\s+params:\n\s+- 3\n", text)


def test_rule_is_evaluated_every_minute_with_a_one_minute_pending_period():
    assert yaml_value("interval") == "1m"
    assert yaml_value("for") == "1m"


def test_missing_data_and_query_errors_keep_the_rule_normal():
    assert yaml_value("noDataState") == "OK"
    assert yaml_value("execErrState") == "OK"


def test_rule_labels_identify_the_deployment_and_owner():
    """Labels come from the series; `$$` survives Grafana's env expansion as `$`."""
    assert yaml_value("service") == "'{{ $$labels.service_name }}'"
    assert yaml_value("environment") == "'{{ $$labels.deployment_environment }}'"
    assert yaml_value("version") == "'{{ $$labels.service_version }}'"
    assert yaml_value("owner") == "recipe-calculator-oncall"


def test_rule_annotations_describe_the_failure_and_link_the_filtered_dashboard():
    summary = annotation("summary")
    assert "$values.A.Value" in summary
    assert "{{ $labels.deployment_environment }}" in summary
    assert "{{ $labels.service_version }}" in summary

    description = annotation("description")
    assert "cannot save new recipes or ingredients" in description

    dashboard_url = annotation("dashboard_url")
    assert dashboard_url.startswith("http://localhost:3000/d/recipe-business-metrics?")
    assert "var-environment={{ $labels.deployment_environment }}" in dashboard_url
    assert "var-version={{ $labels.service_version }}" in dashboard_url

    assert annotation("runbook")


def test_failures_panel_breaks_down_by_component_and_applies_the_variables():
    panel = failures_panel()
    (target,) = panel["targets"]
    expression = target["expr"]

    assert expression.startswith("sum by (component) (increase(component_creation_failures_total{")
    assert 'deployment_environment=~"$environment"' in expression
    assert 'service_version=~"$version"' in expression
    assert target["legendFormat"] == "{{component}}"
    assert target["datasource"]["uid"] == "prometheus"


def test_failures_panel_is_on_the_view_the_alert_link_opens():
    """The link opens the top of the dashboard, so the panel sits first."""
    panel = failures_panel()
    other_panels = [
        p for p in dashboard()["panels"] if p["id"] != panel["id"] and p["type"] != "row"
    ]

    assert panel["gridPos"]["y"] <= 1
    assert all(p["gridPos"]["y"] > panel["gridPos"]["y"] for p in other_panels)


def test_dashboard_variables_list_deployments_that_only_report_failures():
    for item in dashboard()["templating"]["list"]:
        assert "component_creation_failures_total" in item["query"]["query"]


def test_observability_readme_documents_the_metric_rule_threshold_and_live_check():
    readme = README_FILE.read_text(encoding="utf-8")

    for required_text in (
        "component_creation_failures_total",
        "component-creation-failures.yaml",
        "Repeated recipe and ingredient creation failures",
        "3 or more",
        "10 minutes",
        "recipe-calculator-oncall",
        "Component creation failures",
        "deploy-db-1",
        "/api/prometheus/grafana/api/v1/alerts",
    ):
        assert required_text in readme
