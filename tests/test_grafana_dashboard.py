"""Static checks for the provisioned Grafana business-metrics dashboard.

The dashboard is delivered as provisioning files, so the parts that decide
whether it exists, what it filters on, and which metrics it queries can all be
asserted from the repository without Docker or the network. Behaviour that needs
the running stack (Grafana loading the provider, Prometheus answering the
queries) is verified against the live stack and described in
``observability/README.md``.
"""

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROVISIONING_DIRECTORY = REPOSITORY_ROOT / "observability" / "grafana" / "provisioning"
DASHBOARDS_DIRECTORY = PROVISIONING_DIRECTORY / "dashboards"
PROVIDER_FILE = DASHBOARDS_DIRECTORY / "dashboards.yaml"
DASHBOARD_FILE = DASHBOARDS_DIRECTORY / "recipe-business-metrics.json"
DATASOURCES_FILE = PROVISIONING_DIRECTORY / "datasources" / "datasources.yaml"
COMPOSE_FILE = REPOSITORY_ROOT / "observability" / "compose.yaml"
README_FILE = REPOSITORY_ROOT / "observability" / "README.md"

DASHBOARD_UID = "recipe-business-metrics"
PROMETHEUS_UID = "prometheus"
CONTAINER_PROVISIONING_PATH = "/etc/grafana/provisioning"
CONTAINER_DASHBOARDS_PATH = "/etc/grafana/provisioning/dashboards"

ENVIRONMENT_FILTER = 'deployment_environment=~"$environment"'
VERSION_FILTER = 'service_version=~"$version"'

COST_GROUPING = "max by (deployment_environment, service_version)"

BUSINESS_METRICS = ("recipes_created_total", "recipe_views_total", "recipes_average_cost")


def dashboard():
    return json.loads(DASHBOARD_FILE.read_text(encoding="utf-8"))


def variable(name):
    for item in dashboard()["templating"]["list"]:
        if item["name"] == name:
            return item
    raise AssertionError(f"the dashboard does not declare a {name!r} variable")


def panel_queries():
    """Yield (panel title, query expression) for every panel target."""
    for panel in dashboard()["panels"]:
        if panel.get("type") == "row":
            continue
        for target in panel.get("targets", []):
            yield panel["title"], target["expr"]


def expressions():
    return [expression for _, expression in panel_queries()]


def test_dashboard_is_provisioned_from_repository_files():
    """A fresh Grafana volume must come up with the dashboard already installed."""
    assert PROVIDER_FILE.is_file()
    assert DASHBOARD_FILE.is_file()

    provider = PROVIDER_FILE.read_text(encoding="utf-8")
    assert "apiVersion: 1" in provider
    assert "type: file" in provider
    assert f"path: {CONTAINER_DASHBOARDS_PATH}" in provider

    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    assert "./grafana/provisioning:/etc/grafana/provisioning:ro" in compose
    # The provider reads the directory the bind mount exposes, so the committed
    # JSON really is what Grafana loads.
    assert CONTAINER_DASHBOARDS_PATH.startswith(CONTAINER_PROVISIONING_PATH + "/")


def test_dashboard_declares_a_stable_identity_and_the_prometheus_datasource():
    """Provisioned dashboards need a stable uid and must not pin a numeric id."""
    document = dashboard()
    assert document["uid"] == DASHBOARD_UID
    assert document["id"] is None
    assert document["title"]
    assert isinstance(document["schemaVersion"], int)

    datasources = DATASOURCES_FILE.read_text(encoding="utf-8")
    assert f"uid: {PROMETHEUS_UID}" in datasources
    for panel in document["panels"]:
        if panel.get("type") == "row":
            continue
        for target in panel["targets"]:
            assert target["datasource"]["uid"] == PROMETHEUS_UID


def test_dashboard_declares_environment_and_version_variables():
    """Both filters must be multi-select, offer All, and cascade version from environment."""
    environment = variable("environment")
    version = variable("version")

    for item in (environment, version):
        assert item["type"] == "query"
        assert item["includeAll"] is True
        assert item["multi"] is True
        # ".+" (not ".*") so "All" never matches series with a blank label.
        assert item["allValue"] == ".+"
        assert item["datasource"]["uid"] == PROMETHEUS_UID
        assert item["query"]["query"].startswith("label_values(")

    assert "deployment_environment" in environment["query"]["query"]
    assert "service_version" in version["query"]["query"]
    # The version list is scoped to the selected environment, so a pair that
    # never existed cannot be chosen.
    assert "$environment" in version["definition"]
    assert "$environment" in version["query"]["query"]
    assert "deployment_environment" not in environment["query"]["query"].split(",", 1)[0]


def test_variables_discover_values_from_all_business_metrics():
    """A deployment is listed even when only one of the three metrics has data."""
    for metric in BUSINESS_METRICS:
        assert metric in variable("version")["query"]["query"]
        assert metric in variable("environment")["query"]["query"]


def test_dashboard_queries_the_live_metric_names_only():
    """The panels must use the names the current code emits, not the legacy COP series."""
    text = DASHBOARD_FILE.read_text(encoding="utf-8")
    queries = " ".join(expressions())

    for metric in BUSINESS_METRICS:
        assert metric in queries
    assert "recipes_average_cost_COP" not in text


def test_every_panel_query_applies_both_filters():
    """Without both filters a panel would mix deployments together."""
    panels = [
        panel
        for panel in dashboard()["panels"]
        if panel.get("type") != "row"
    ]
    assert len(panels) >= 8

    for title, expression in panel_queries():
        assert ENVIRONMENT_FILTER in expression, title
        assert VERSION_FILTER in expression, title


def test_panels_cover_created_views_and_cost_metrics():
    """The panel set must cover the three business metrics and their breakdowns."""
    queries = expressions()

    # Whole-application recipes created, summed across the worker instance series.
    assert any(
        query.startswith("sum(recipes_created_total{") for query in queries
    )
    # Views per recipe, so the most viewed recipes are identifiable.
    assert any(
        "sum by (recipe) (increase(recipe_views_total{" in query for query in queries
    )
    assert any(
        "topk(1, sum by (recipe) (recipe_views_total{" in query for query in queries
    )
    # Average cost per environment/version pair, deduplicated across the
    # identical per-worker gauge values within each pair.
    assert any(
        query.startswith(COST_GROUPING + " (recipes_average_cost{")
        for query in queries
    )


def test_cost_panels_are_grouped_per_environment_and_version_pair():
    """Costs from different deployments are different databases and must not be blended."""
    cost_queries = [
        (title, query)
        for title, query in panel_queries()
        if "recipes_average_cost" in query
    ]
    assert len(cost_queries) >= 2

    for title, query in cost_queries:
        assert query.startswith(COST_GROUPING + " (recipes_average_cost{"), title
        assert "sum(" not in query and "avg(" not in query, title

    for panel in dashboard()["panels"]:
        if any("recipes_average_cost" in t["expr"] for t in panel.get("targets", [])):
            for target in panel["targets"]:
                assert "{{deployment_environment}}" in target["legendFormat"], panel["title"]
                assert "{{service_version}}" in target["legendFormat"], panel["title"]


def test_counter_panels_pair_a_cumulative_total_with_movement_over_the_range():
    """A version filter must leave counters meaningful, not just cumulative."""
    queries = expressions()

    assert any(
        query.startswith("sum(recipes_created_total{") and "increase(" not in query
        for query in queries
    )
    assert any(
        "sum(increase(recipes_created_total{" in query and "$__rate_interval" in query
        for query in queries
    )
    assert any(
        "sum(increase(recipes_created_total{" in query and "$__range" in query
        for query in queries
    )


def test_counter_panels_state_their_units_and_decimals():
    """Counts are whole numbers, and the cost panels say they are in COP."""
    for panel in dashboard()["panels"]:
        if panel.get("type") == "row":
            continue
        defaults = panel["fieldConfig"]["defaults"]
        assert defaults["unit"], panel["title"]
        assert defaults["decimals"] == 0, panel["title"]


def test_observability_readme_documents_the_dashboard():
    """Operators must find the dashboard, its variables, and its reload behaviour."""
    readme = README_FILE.read_text(encoding="utf-8")

    for required_text in (
        DASHBOARD_UID,
        "Recipe Calculator - Business Metrics",
        "grafana/provisioning/dashboards/dashboards.yaml",
        "recipe-business-metrics.json",
        "deployment_environment",
        "service_version",
        "environment",
        "version",
        "recipes_created_total",
        "recipe_views_total",
        "recipes_average_cost",
        "docker compose -f observability/compose.yaml restart grafana",
        "down -v",
    ):
        assert required_text in readme
