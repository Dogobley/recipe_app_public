# Issue 28: Alert on repeated recipe and ingredient creation failures

Status: closed (2026-10-15)

## Goal

When saving recipes or ingredients keeps failing on the server in one deployment, a Grafana alert fires. Its labels and annotations give the on-call engineer the service, environment, deployed version, owner, and a dashboard link that opens on the failing deployment.

### What "component creation" means here

The request asked for an alert on "canvas component-creation failures". This application has no canvas. Its user-created components are:

- **recipes**, saved together with their ingredient rows by `recipe_create` in `calculator/views.py`
- **ingredients**, saved by `ingredient_create`

This issue alerts on those two flows.

A **failure** is a create request (POST) that the server could not complete: an unhandled exception or a 5xx response. A form the user filled in wrongly is redisplayed with validation errors, and that is not a failure.

## Acceptance criteria

The failure signal:

- [ ] A counter `component_creation_failures_total` is exported, with a `component` label set to `recipe` or `ingredient`. It also carries the usual resource labels: `service_name`, `deployment_environment`, `service_version`.
- [ ] The counter goes up by one for each create POST that ends in an unhandled exception or a 5xx response, including a database error inside the save transaction. For a recipe, no partial recipe is left behind, as today.
- [ ] The counter does not move for:
  - a POST with validation errors (for example a negative weight, a missing name, or the same ingredient twice)
  - GET requests to the create pages
  - successful creates
  - edits and deletes
- [ ] The user still sees the normal error page. Counting a failure never changes the response.

The alert:

- [ ] The alert rule is provisioned from files under `observability/grafana/provisioning/`, so it exists after `docker compose -f observability/compose.yaml down -v` and `up`. It sits in the "Recipe Calculator" folder.
- [ ] **Threshold:** it fires when one deployment (one environment and version pair) has **3 or more failures within the last 10 minutes**, counting recipes and ingredients together. The rule is evaluated every minute with a 1-minute pending period, to cover the application's one-minute metric export.
  - Why this threshold: this is a single-user app, so one failure can be a one-off and the user simply retries. Three failures in 10 minutes means the user tried again and is still blocked from saving their work.
- [ ] One or two failures within 10 minutes do not fire.
- [ ] Failures in dev and prod, or in two versions, are counted separately. Two failures in dev and two in prod do not fire.
- [ ] It resolves on its own once the deployment has had fewer than 3 failures in the last 10 minutes.
- [ ] Missing data (no failure has ever happened, or Prometheus has no series) leaves the rule Normal. It never fires a NoData or Error alert. A worker or container restart that resets the counter does not fire it.
- [ ] Each firing alert carries:
  - labels `service`, `environment`, `version` (taken from the series) and `owner` (a fixed value set in the rule file, for example `recipe-calculator-oncall`)
  - an annotation `summary` naming the environment, version and failure count
  - an annotation `description` saying what users can't do
  - an annotation `dashboard_url` pointing to `http://localhost:3000/d/recipe-business-metrics` with `var-environment` and `var-version` already set to the failing deployment
  - an annotation `runbook` with a short first step to take
- [ ] The business dashboard has a new panel, "Component creation failures", broken down by component. The `dashboard_url` opens on a view where it is visible. The dashboard's variable filters apply to it.

Live check (dev only):

- [x] On dev, stop only the dev database container (`deploy-db-1`) and try to save three recipes within a few minutes. The alert reaches Firing within about 3 minutes. Its labels show `environment=dev` and the dev release tag, and its link opens the dashboard filtered to that deployment. Start the database again, and the alert resolves within about 12 minutes. Prod is never touched.
- [ ] `observability/README.md` documents the metric, the rule, the threshold and why it was chosen, and the live check above.
- [ ] `python -m pytest` passes.

## Out of scope

- Sending notifications (email, chat). In [Issue 29](issue29.md) the alert is read by polling Grafana's alert API, so no contact point is needed.
- Acting on the alert. That is [Issue 29](issue29.md).
- Alerts for other flows (edits, deletes, views) or for latency.
- Deploying the stack through the pipeline. That is [Issue 27](issue27.md).

## Constraints

- Put the metric in `calculator/metrics.py`, in the same style as `record_recipe_created()`. Record failures without wrapping the domain services. The views stay thin.
- Use Grafana's built-in alerting, provisioned from files. Don't add an Alertmanager or any other service.
- Change only:
  - `calculator/metrics.py`, `calculator/views.py` (or middleware, if that is cleaner)
  - `observability/grafana/provisioning/`
  - `observability/README.md`
  - tests under `tests/`
- Use read-only or dev-only actions in the live check. Never stop or change prod containers.
- Read `_docs/testing-guidelines.md` before writing tests. Do not add dependencies.

## Engineer comment

Implemented the failure signal, the provisioned alert rule and the dashboard panel.

**Metric (`calculator/metrics.py`, `calculator/views.py`)**

- New counter `component_creation_failures` (exported as `component_creation_failures_total`) with a `component` label, created in the same style as `record_recipe_created()` and carrying the usual resource labels. `record_component_creation_failure(component)` increments it.
- `count_creation_failures(component)` is a view decorator applied to `recipe_create` and `ingredient_create`. It only acts on POST: an unhandled exception is counted and re-raised unchanged; a 5xx response is counted and returned unchanged. Exceptions Django turns into 4xx (`Http404`, `PermissionDenied`, `BadRequest`, `SuspiciousOperation`) are not counted. Recording is wrapped so a metrics problem can never change the response. The domain services and the recipe transaction are untouched, so a failing recipe save still leaves no partial rows.
- `register_instruments()` starts both component series at 0. Without that, Prometheus would first see a series at its first failure, and `increase()` would drop that failure (once per gunicorn worker). With 2 workers, 3 failures could then read as 1.

**Alert (`observability/grafana/provisioning/alerting/component-creation-failures.yaml`)**

- Rule `component-creation-failures`, "Repeated recipe and ingredient creation failures". It is in folder "Recipe Calculator" (named by title; see the fix after QA below), group `component-creation`, evaluated every 1m, `for: 1m`.
- Query: `sum by (service_name, deployment_environment, service_version) (increase(component_creation_failures_total[10m]))`, and a threshold expression `gte 3`. `noDataState: OK` and `execErrState: OK`.
- Labels `service`, `environment` and `version` come from the series, plus `owner: recipe-calculator-oncall`. Annotations: `summary`, `description`, `dashboard_url` (with `var-environment`/`var-version` from the labels and `from=now-1h`) and `runbook`.
- Finding: Grafana's file provisioning expands `$labels` in label values as an environment variable, which turns it into `{{ .deployment_environment }}` and leaves the label unrendered. The label templates are therefore written as `{{ $$labels.x }}`. Grafana stores and renders them as `{{ $labels.x }}`. This is documented in the README and asserted in tests.

**Dashboard**: a new top row "Creation failures" holds the "Component creation failures" timeseries, `sum by (component) (increase(...{deployment_environment=~"$environment", service_version=~"$version"}[$__rate_interval]))`, stacked bars. The existing panels moved down. The variable queries also list `component_creation_failures_total`, so a deployment that only reports failures can still be selected.

**README**: new "Creation failure alert" section (metric, rule, threshold and why, labels and annotations, API reads, live check steps), plus the metric table row and panel table row.

**Tests**

- `tests/test_component_creation_failures.py` checks:
  - recipe and ingredient DB errors count, return a 500 with the normal error page, re-raise the same exception, and leave no partial recipe
  - a 5xx response counts and is returned unchanged
  - none of these count: validation errors (negative weight, missing name, negative quantity, duplicate ingredient, ingredient errors), GETs, successful creates, edits/deletes, a failing edit, and 4xx-mapped exceptions
- `tests/test_grafana_alerting.py` holds static checks of the rule file, the panel and the README.
- The `metric_reader` fixture moved to `tests/conftest.py` so both metric modules share it.
- `.venv/Scripts/python -m pytest` -> 350 passed, 23 deselected (351 after the QA fix below).

**Local validation against the running observability stack** (only the `grafana` service restarted; nothing else touched):

- `GET /api/v1/provisioning/alert-rules` shows the rule with `provenance: file` in folder uid `recipe-calculator`. Its health is `ok`, its state is Normal, and there is no failure data yet.
- Both PromQL expressions parse on Prometheus (`localhost:9090`).
- A temporary API-created copy of the rule fed synthetic values (deleted afterwards) confirmed:
  - `gte 3` fires at 3 and stays Normal at 2
  - the labels render (`environment=dev`, `version=...`, `service=recipe-cost-calculator`, `owner=recipe-calculator-oncall`)
  - the summary reads "3 recipe/ingredient creation failures ... on dev version ..."
  - `dashboard_url` resolves to `...?var-environment=dev&var-version=<version>&from=now-1h&to=now`
- The provisioned dashboard loads with "Component creation failures" at the top.

**Fix after QA FAIL (duplicate "Recipe Calculator" folder on a fresh volume)**

- Cause: QA's diagnosis was right. Grafana 13.2.4 provisions alerting before dashboards. The rule file can only name its folder by title, so on a fresh volume it creates a "Recipe Calculator" folder with a generated uid. The dashboard provider then pinned `folderUid: recipe-calculator` and created a second folder with the same title.
- What 13.2.4 supports: I tested on throwaway containers. Adding `folderUid: recipe-calculator` to the alert rule group is silently ignored: the rule still landed in a random-uid folder next to `recipe-calculator`. A folder uid can't be set from the alerting side.
- Fix: removed `folderUid` from `observability/grafana/provisioning/dashboards/dashboards.yaml`, with a comment explaining why. Both providers now match the folder by the title "Recipe Calculator" and converge on one folder. On a fresh volume the folder gets a generated uid. The existing volume keeps its `recipe-calculator` uid. Nothing in the repo refers to the folder uid.
- Verification, with the same method as QA:
  - A throwaway `grafana/grafana:13.2.4` container (no volume, repo provisioning mounted read-only, port 3998) had exactly one "Recipe Calculator" folder, holding both the rule and the dashboard.
  - After `docker restart`, still one folder with both in it.
  - The container was then removed.
  - The running `observability` stack (only `grafana` restarted, no `down -v`) has one folder, `recipe-calculator`, with both the rule and the dashboard in it.
- Guard test: `test_rule_and_dashboard_share_one_folder_matched_by_title` in `tests/test_grafana_alerting.py` checks:
  - both files name the same folder title
  - neither pins a `folderUid`
  It fails if a `folderUid` is added back (checked by temporarily re-adding one).
- README: the "Creation failure alert" section now explains the shared folder: it is matched by title, and its uid differs between fresh and old volumes. The "survives `down -v`" claim now holds fully.
- `.venv/Scripts/python -m pytest` -> 351 passed, 23 deselected.

**Pending**: the "Live check (dev only)" criterion (stop `deploy-db-1`, save three recipes, see Firing, restart, see resolve). It needs this app change deployed to dev first, because the running dev image does not emit the new metric yet. It was not performed here.

## QA: FAIL

The failure signal:

- [x] `component_creation_failures_total` is exported with `component=recipe|ingredient` and the `service_name`, `deployment_environment`, `service_version` resource labels - PASS
      Both component series are started at 0 by `register_instruments()`; a scratch test read the in-memory reader and saw the counter with resource attributes `service.name`, `deployment.environment`, `service.version` (exported to Prometheus through `resource_to_telemetry_conversion`, same as the existing metrics, which carry them as labels).
- [x] The counter goes up by one per failed create POST, including a DB error inside the save transaction; no partial recipe - PASS
      Scratch test (outside the repo, transactional DB) used `connection.execute_wrapper` to make the real `INSERT` into the recipe-ingredient table fail inside `transaction.atomic()`: three POSTs gave three 500s, `recipe` = 3, `ingredient` = 0, and 0 `Recipe` / 0 `RecipeIngredient` rows remained. A failing ingredient `INSERT` gave a 500 and `ingredient` = 1.
- [x] The counter does not move for validation errors, GETs, successful creates, edits and deletes - PASS
      Scratch test: negative quantity, missing name, same ingredient twice, negative weight per unit, negative package weight, missing ingredient name (all 200 re-rendered), GETs to both create pages, a PUT (405), a successful recipe and ingredient create (302), a recipe edit, an ingredient edit whose `UPDATE` failed with a DB error (500), a recipe delete and an ingredient delete: counter stayed `recipe` = 0, `ingredient` = 0.
- [x] The user still sees the normal error page; counting never changes the response - PASS
      With `raise_request_exception=False` the 500 body equals Django's default `server_error` page byte for byte; with the default client the original `DatabaseError("QA forced failure")` propagates unchanged.

The alert:

- [ ] Provisioned from files under `observability/grafana/provisioning/`, exists after `down -v`/`up`, sits in the "Recipe Calculator" folder - FAIL
      On the running stack the rule is `provenance: file` in folder uid `recipe-calculator`, but only because that folder already existed in the old Grafana volume. To check a fresh volume without running `down -v`, I started a throwaway `grafana/grafana:13.2.4` container (`qa28-fresh-grafana`, port 3999, no volume, the repo's `grafana/provisioning` mounted read-only, removed afterwards). Grafana provisions alerting before dashboards, so the rule file (`folder: Recipe Calculator`, a title only) created its own folder with a random uid (`eg192aocvbuv4f`), and then the dashboard provider created the `recipe-calculator` folder. Result: two folders both named "Recipe Calculator", the rule in one and the dashboard in the other. A restart kept that split. After a real `down -v`/`up` the rule exists, but in a duplicate folder, not the project's "Recipe Calculator" folder (`recipe-calculator`) that holds the dashboard.
- [x] Threshold: 3 or more failures in 10 minutes per environment/version, recipes and ingredients together, evaluated every 1m with a 1m pending period - PASS
      Provisioned rule: `sum by (service_name, deployment_environment, service_version) (increase(component_creation_failures_total[10m]))`, `gte 3`, group interval 1m, `for: 1m`. The sum has no `component` grouping, so recipes and ingredients add together. A temporary copy of the rule with a fixed `vector(3)` series went Pending, then Firing one evaluation later.
- [x] One or two failures within 10 minutes do not fire - PASS
      Temporary copies with fixed values 1 and 2 stayed Normal across several evaluations.
- [x] Dev and prod, or two versions, are counted separately; 2 in dev + 2 in prod do not fire - PASS
      Temporary copies fed two series through the same `sum by`: dev=2 + prod=2, and dev v1=2 + dev v2=2. Each gave two separate Normal instances with value 2, and none fired.
- [x] It resolves on its own below 3 - PASS
      A temporary copy whose value was `3 - (time() > bool T)` fired, then went back to Normal after `T` passed, with no rule edit. `keep_firing_for` is 0s.
- [x] Missing data stays Normal, never NoData/Error alerts; a counter reset does not fire - PASS
      `noDataState: OK` and `execErrState: OK`. A temporary copy that queried a metric that does not exist showed "Normal (NoData)". A copy with a PromQL syntax error showed "Normal (Error)". The real rule currently shows Normal (NoData). On resets: each gunicorn worker exports its own series (distinct `service_instance_id`), and a restart starts new series at 0. `increase()` treats any drop inside one series as a reset, not as an increase, so a restart cannot add failures. `increase()` extrapolation can briefly overshoot on a young series. For example, a series with samples 0 and then 2, read 30-60s after the second sample, can give 3-4. On the next evaluation, 60s later, the value is below 3. The 1-minute pending period therefore stops 2 failures from firing (worked through for 60s export samples). No fault.
- [x] Each firing alert carries the required labels and annotations - PASS
      Firing instance labels: `service=qa-svc`, `environment=dev`, `version=qa-v1`, `owner=recipe-calculator-oncall`. Summary: "3 recipe/ingredient creation failures in the last 10 minutes on dev version qa-v1". The description says users cannot save new recipes or ingredients. `dashboard_url=http://localhost:3000/d/recipe-business-metrics?var-environment=dev&var-version=qa-v1&from=now-1h&to=now`. `runbook` gives a first step. The stored provisioned rule holds `{{ $labels.* }}` in labels and annotations, so the `$$` escape works.
- [x] Business dashboard has a "Component creation failures" panel by component, visible from `dashboard_url`, filtered by the variables - PASS
      The live provisioned dashboard (uid `recipe-business-metrics`) has the panel at the top (gridPos y=1). The query is `sum by (component) (increase(component_creation_failures_total{deployment_environment=~"$environment", service_version=~"$version"}[$__rate_interval]))`, and both variable queries include the new metric.

Live check (dev only):

- [ ] Stop `deploy-db-1`, save three recipes, alert fires and resolves - NOT VERIFIED (pending deploy)
      Not performed on purpose: the change is not deployed to dev yet, so the running dev image does not emit the metric. This item is not counted in the verdict.
- [x] `observability/README.md` documents the metric, rule, threshold and its reason, and the live check - PASS
      The "Creation failure alert" section covers all four. Its claim that the rule "survives `down -v`" holds only in part: the rule comes back, but in a duplicate folder (see the FAIL above).
- [x] `python -m pytest` passes - PASS

Tests:
- `.venv/Scripts/python -m pytest`: 350 passed, 23 deselected, 0 failed
- Scratch QA suite (not in the repo) run with `-c pytest.ini`: 4 passed

Other notes, not counted in the verdict:
- The repo tests for the alert (`tests/test_grafana_alerting.py`) are static checks of the files. No test covers how a fresh Grafana resolves the folder.
- In the real rule's Normal (NoData) instance, the labels read `{{ .deployment_environment }}`. It is not firing and it is harmless.

Cleanup:
- All 7 temporary rules (`qa28-*`, group `qa-temp-28`) were deleted.
- The throwaway Grafana container was removed.
- Only the provisioned rule and the single `recipe-calculator` folder remain.
- No code, test, prod container or `deploy/` file was touched.

## QA (re-check): PASS

Re-checked after commit 66d0c23, which removed `folderUid` from `observability/grafana/provisioning/dashboards/dashboards.yaml`. That commit leaves `calculator/`, the alert rule file and the dashboard JSON exactly as they were in fe8d3c3 (`git diff fe8d3c3 66d0c23` shows no changes there). So the earlier evidence for those files still applies, and I ran the scratch checks again.

The failure signal:

- [x] `component_creation_failures_total` exported with `component` and the `service_name`, `deployment_environment`, `service_version` labels - PASS
      Code unchanged; the scratch QA suite passes again.
- [x] Counts each failed create POST, including a DB error in the save transaction; no partial recipe - PASS
      Scratch suite: a real failing `INSERT` gave three 500s, `recipe` = 3, and no recipe or recipe-ingredient rows left. A failing ingredient insert gave `ingredient` = 1.
- [x] Does not move for validation errors, GETs, successful creates, edits and deletes - PASS
      Scratch suite: all of these left both counts at 0, including a failing ingredient edit.
- [x] The user still sees the normal error page - PASS
      The 500 body is byte-identical to Django's default `server_error`, and the original exception propagates unchanged.

The alert:

- [x] Provisioned from files, exists after `down -v`/`up`, sits in the "Recipe Calculator" folder - PASS
      I did not run `down -v` on the stack. Instead I started a throwaway `grafana/grafana:13.2.4` container (`qa28-fresh-grafana2`, port 3999, no volume, the repo's `grafana/provisioning` mounted read-only).
      - Fresh start: exactly one folder, "Recipe Calculator" (uid `eg19363ttkg74f`, `managedBy: classic-file-provisioning`). The rule `component-creation-failures` (`provenance: file`) and the dashboard `recipe-business-metrics` are both in it.
      - After `docker restart`: still the same single folder, with both in it, and no folder or provisioning errors in the log.
      - The container was removed afterwards.
      - Running stack: still a single folder (uid `recipe-calculator`) holding the rule and the dashboard. The rule's health is ok and its state Normal.
- [x] Threshold: 3+ in 10 minutes per environment/version, every 1m, `for: 1m` - PASS
      The rule file is unchanged, and the stored rule matches it. Earlier, a temporary copy fed a fixed value of 3 went Pending, then Firing.
- [x] One or two failures do not fire - PASS
      Earlier temporary rules with values 1 and 2 stayed Normal. The rule is unchanged since.
- [x] Dev and prod, or two versions, counted separately - PASS
      Earlier: 2 dev + 2 prod, and 2 + 2 across two versions, gave separate Normal instances. The rule is unchanged since.
- [x] Resolves on its own - PASS
      Earlier: a time-based value that fell from 3 to 2 went back to Normal with no rule edit. The rule is unchanged since.
- [x] Missing data or errors stay Normal; a counter reset does not fire - PASS
      `noDataState`/`execErrState` are `OK`. Earlier, a missing metric showed Normal (NoData) and a broken query showed Normal (Error). My reasoning that `increase()` handles resets is unchanged.
- [x] Labels and annotations - PASS
      The stored rule on the running stack still has `{{ $labels.* }}` labels, `owner=recipe-calculator-oncall`, and `dashboard_url` `http://localhost:3000/d/recipe-business-metrics?var-environment=...&var-version=...&from=now-1h&to=now`. Rendering was confirmed earlier with a firing temporary copy.
- [x] Dashboard panel "Component creation failures", reached from `dashboard_url`, filtered by the variables - PASS
      The dashboard uid is still `recipe-business-metrics` (URL `/d/recipe-business-metrics/recipe-calculator-business-metrics`), with "Component creation failures" at the top. A filtered `dashboard_url` answers HTTP 200 on both the running stack and the fresh container. The `dashboard_url` does not depend on the folder uid, and nothing in the repo refers to the folder uid.

Live check (dev only):

- [ ] Stop `deploy-db-1`, save three recipes, alert fires and resolves - NOT VERIFIED (pending deploy)
      Not performed on purpose: the change is not deployed to dev yet. This item is not counted in the verdict.
- [x] `observability/README.md` documents the metric, rule, threshold and its reason, and the live check - PASS
      It now also explains that both providers name the folder by title only, and why.
- [x] `python -m pytest` passes - PASS

Tests:
- `.venv/Scripts/python -m pytest`: 351 passed, 23 deselected, 0 failed (includes the new folder guard test)
- Scratch QA suite (not in the repo): 4 passed

Cleanup:
- The throwaway container was removed.
- The running stack was not restarted or changed.
- No code, test, prod container or `deploy/` file was touched.

## Live check (dev only), 2026-10-15: PASS

Run by the orchestrator after `fe8d3c3` and `66d0c23` were pushed and Build redeployed dev.

- Dev web container `deploy-web-1`: `APP_VERSION=20261015-011621-66d0c23`, healthy, `http://localhost:8000/health/` 200. `component_creation_failures_total{deployment_environment="dev"}` present at 0 for `recipe` and `ingredient` before the test.
- 01:18:10Z: `docker stop deploy-db-1` (dev only). Three POSTs to `/recipes/add/` between 01:18:10Z and 01:18:53Z each returned 500.
- 01:20:40Z: alert "Repeated recipe and ingredient creation failures" Firing (about 2.5 minutes after the first failure), read from `GET /api/alertmanager/grafana/api/v2/alerts?active=true`. Labels: `environment=dev`, `version=20261015-011621-66d0c23`, `service=recipe-cost-calculator`, `owner=recipe-calculator-oncall`. `dashboard_url` = `http://localhost:3000/d/recipe-business-metrics?var-environment=dev&var-version=20261015-011621-66d0c23&from=now-1h&to=now`, which returned 200.
- 01:20:53Z: `docker start deploy-db-1`; dev health 200 again. None of the three test recipes exist in `/recipes/` (no partial recipe).
- 01:28:50Z: alert no longer active (resolved about 10.7 minutes after the first failure, 8 minutes after the database came back).
- Prod containers were not touched.

Observation (not a criterion failure): the `summary` read "4 recipe/ingredient creation failures" for 3 real failures, because `increase()` extrapolates over the window (query value 4.296). Consider rounding the value or wording it as "about N" in a follow-up.

## Closed by orchestrator

QA (re-check) PASS on all code criteria and the live check above passed.

