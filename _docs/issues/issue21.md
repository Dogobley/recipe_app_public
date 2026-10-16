# Issue 21: Provision the business-metrics Grafana dashboard

Status: closed

## Goal

Give the operator a Grafana dashboard, provisioned from repository files, that shows the recipe business metrics and can be filtered by deployment environment and version.

## Acceptance criteria

- [x] The dashboard is provisioned from repository files and comes back after `docker compose -f observability/compose.yaml down -v` and `up`.
- [x] It has environment and version filters. Both are multi-select with "All", and the version list only shows versions the selected environment reported.
- [x] Every panel query applies both filters.
- [x] Recipes created, recipe views per recipe, and average recipe cost each have panels.
- [x] With several environments or versions selected, the cost panels show one value per environment/version pair and never mix them into one number.
- [x] The observability README documents the dashboard, its filters, its panels and how to reload it.
- [x] `python -m pytest` passes.

## Out of scope

- Changing the metrics the application emits.
- Alerting rules.

## Constraints

- Keep the dashboard in `observability/grafana/provisioning/dashboards/` and the checks in `tests/test_grafana_dashboard.py`.
- Counter panels keep `sum(...)`: adding counts across the selected deployments is a meaningful total.
- Cost panels use `max by (deployment_environment, service_version) (...)`: `max` collapses the identical values the gunicorn workers report, separately for each pair.
- Do not add dependencies.
