## QA: PASS

Docker Desktop was running, so the live checks were done. One criterion part (live multi-pair cost series) could only be checked at the query level; see the notes.

- [x] The dashboard is provisioned from repository files and comes back after `docker compose -f observability/compose.yaml down -v` and `up` - PASS
      `dashboards.yaml` is a file provider on `/etc/grafana/provisioning/dashboards`, and `compose.yaml` bind-mounts `./grafana/provisioning` there. I ran `down -v` (the grafana_data and prometheus_data volumes were removed), then `up -d`. `GET /api/dashboards/uid/recipe-business-metrics` returned the dashboard with `provisioned: true`, folder "Recipe Calculator" and 11 panels (3 of them rows).
- [x] Environment and version filters, both multi-select with "All"; versions limited to the selected environment - PASS
      JSON: `environment` and `version` both have `multi: true`, `includeAll: true`, and default to All. The version query is `label_values({__name__=~"recipes_created_total|recipe_views_total|recipes_average_cost", deployment_environment=~"$environment"}, service_version)`, so it is scoped by `$environment`. Live, the Prometheus labels returned `production` and the versions `latest` and `20261014-042438-6c30e73`. I could not check live that a version reported by only one of several environments is hidden, because only one environment exists. The scoping is in the query.
- [x] Every panel query applies both filters - PASS
      All 8 non-row panels have a single target each, and each metric selector contains `deployment_environment=~"$environment", service_version=~"$version"`.
- [x] Recipes created, recipe views per recipe, and average recipe cost each have panels - PASS
      Recipes created: 3 panels (cumulative, range, over time). Views: per-recipe time series, most viewed, and top-10 table. Cost: stat and time series.
- [x] With several environments or versions selected, the cost panels show one value per environment/version pair and never mix them - PASS (query level)
      Both cost panels use `max by (deployment_environment, service_version) (recipes_average_cost{...})` with legend `{{deployment_environment}} / {{service_version}}`. The stat panel uses `textMode: value_and_name`. Counter panels keep `sum(...)`. I ran the filtered expression against Prometheus before the reset: the `production` / `latest` pair gave one series at 12750, from two worker series with identical values. Only one pair had data, so I could not see two pairs side by side live. After `down -v` the data is gone, so I did not re-test.
- [x] The observability README documents the dashboard, its filters, its panels and how to reload it - PASS
      `observability/README.md` has "Business metrics dashboard" with the source files, Variables, a Panels table, the per-pair cost rationale, and "Reloading the dashboard" (`docker compose ... restart grafana`, plus the 30 s rescan).
- [x] `python -m pytest` passes - PASS

Tests: `.venv/Scripts/python -m pytest`, 298 passed, 0 failed, 23 deselected (compose/e2e markers).

Observation (not a criterion failure):
- The "All" option uses `allValue: ".*"`. A regex `.*` also matches series that have no `deployment_environment` or `service_version` label. Before the reset, Prometheus held an old unlabeled `recipes_average_cost` series (value 137500). With All selected, the expression `max by (deployment_environment, service_version) (last_over_time(recipes_average_cost{deployment_environment=~".*", service_version=~".*"}[7d]))` returned two series: the `production`/`latest` pair (12750) and an extra one with empty labels (137500). On a fresh volume, where every series carries both labels, this does not occur. If a legacy unlabeled series appears again, the cost panels would show a blank-label entry. A stricter `allValue` such as `.+` would avoid it. Consider a follow-up issue.
