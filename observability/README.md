# Observability stack

A self-contained OpenTelemetry + Grafana stack that receives telemetry from the
application and stores it for querying. It runs as its own Compose project
(`observability`), separate from the application's `web`/`db` stack, so it can
be started, stopped, and updated independently.

## Services

| Service | Purpose | Port |
| --- | --- | --- |
| OpenTelemetry Collector | Receives OTLP (gRPC and HTTP) and routes traces to Tempo, metrics to Prometheus, and logs to Loki | `4317` gRPC, `4318` HTTP |
| Prometheus | Stores metrics scraped from the collector and receives pushed metrics via remote write | `9090` |
| Loki | Stores logs | `3100` |
| Tempo | Stores traces | `3200` |
| Grafana | Dashboards, exploration and alerting; pre-provisioned with Prometheus, Loki, and Tempo data sources and with the business-metrics dashboard and creation-failure alert rule provisioned from files | `3000` |

## Deploy with the pipeline

The **Deploy observability** workflow
([.github/workflows/deploy-observability.yml](../.github/workflows/deploy-observability.yml))
deploys or updates the stack. Run it from **Actions -> Deploy observability ->
Run workflow**; it also runs on every push to `main` that changes a file under
`observability/`. It runs on the self-hosted runner of this host and:

1. Checks the deploy folder and the Grafana env file. If the repository
   variable is unset, the folder is inside `actions-runner/_work`, `.env` is
   missing, or `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` is missing,
   empty, `admin` or the example placeholder, it fails before any file or
   container changes. It never falls back to `admin` / `admin`.
2. Copies the files of `observability/` from the commit it runs on to the
   deploy folder. Only files whose content differs are written, and files
   removed from `grafana/` are removed there too. `.env` is never overwritten.
3. Runs `docker compose --project-name observability up -d` from the deploy
   folder. The project name stays `observability`, so the existing
   `observability_*_data` volumes (metrics, logs, traces, dashboards) are
   reused. Compose only recreates a container whose configuration changed; a
   service whose bind-mounted config file changed but whose container was kept
   is restarted so it reads the new file. A second run with no changes
   recreates and restarts nothing.
4. Waits up to five minutes for every service: Prometheus `/-/ready`, Loki
   `/ready`, Tempo `/ready`, Grafana `/api/health` and the collector's metrics
   on `:8888`. The run is red and names each service that is not ready, with its
   recent logs.
5. Applies the password from `.env` to the Grafana admin user and checks that
   Grafana accepts it. The password goes to the Grafana CLI's stdin as exact
   UTF-8 bytes (never on a command line, never printed). If the login check
   fails, the error says whether Grafana has no such user, rejected the
   password, or temporarily blocked logins after repeated failures (wait 5
   minutes, then run the workflow again).

| Setting | Where | Value |
| --- | --- | --- |
| `OBSERVABILITY_PATH` | Repository variable (**Settings -> Secrets and variables -> Actions -> Variables**) | A fixed folder outside the runner's work directory, for example `C:\Users\<you>\observability`. Containers bind-mount their config from here, never from `actions-runner/_work`, which the runner cleans. |
| `.env` | In `OBSERVABILITY_PATH`, untracked | Grafana admin credentials, from [`env.example`](env.example). |

The workflow touches only the `observability` Compose project. It never
restarts, recreates or stops the dev or prod application containers.

## Grafana credentials

Grafana's admin user and password come from `.env` in the deploy folder, not
from `compose.yaml`. Create it once from the committed example, then replace
the placeholder in it (never commit, print or share `.env`):

```powershell
Copy-Item observability\env.example C:\Users\<you>\observability\.env
```

| Variable | Meaning |
| --- | --- |
| `GRAFANA_ADMIN_USER` | Admin login name. It only takes effect when Grafana creates a new volume; on an existing volume keep the current login name (`admin`). |
| `GRAFANA_ADMIN_PASSWORD` | Admin password. Required; must not be `admin`. |

Compose reads `.env` its own way: in an unquoted or double-quoted value `$name`
is a variable reference (so `pa$word` would become `pa`), and in an unquoted
value ` #` starts a comment. Write each `$` as `$$`, or wrap the whole value in
single quotes (`GRAFANA_ADMIN_PASSWORD='pa$s #word'`). The workflow refuses a
value that Compose would change, before any container changes.

`compose.yaml` requires both (`${GRAFANA_ADMIN_PASSWORD:?...}`), so Compose
refuses to start Grafana without them. Anonymous access
(`GF_AUTH_ANONYMOUS_ENABLED`) and sign-up (`GF_USERS_ALLOW_SIGN_UP`) are
disabled.

**Change the Grafana password.** Edit `GRAFANA_ADMIN_PASSWORD` in `.env` in the
deploy folder, then run **Deploy observability** again. Grafana only reads
`GF_SECURITY_ADMIN_PASSWORD` when it creates its database, so the workflow
applies the new password to the existing volume with
`grafana cli admin reset-admin-password --password-from-stdin`, without
recreating the container. To do it by hand from the deploy folder instead, run

```powershell
docker compose exec grafana grafana cli admin reset-admin-password --password-from-stdin
```

type the new password, press Enter, and update `.env` to match.

## Start and stop by hand

Run these from the deploy folder (`OBSERVABILITY_PATH`), where `compose.yaml`
and `.env` live. `compose.yaml` names the project `observability`, so these act
on the same containers and volumes as the workflow:

```powershell
Set-Location C:\Users\<you>\observability
docker compose up -d
docker compose ps
```

Stop it without deleting the stored data:

```powershell
docker compose down
```

Add `-v` to `down` only to discard stored metrics, logs, traces and Grafana
data; the provisioned dashboards and alert rules come back on the next `up`.

Stopping the stack never affects the application. The dev (`:8000`) and prod
(`:8001`) containers keep serving requests; their logs may show telemetry export
errors while the collector is down, and telemetry resumes within about two
minutes of `docker compose up -d`, with no application restart.

To try a change from a repository checkout instead, copy `env.example` to
`observability/.env` (ignored by Git) and use
`docker compose -f observability/compose.yaml up -d`. It is the same
`observability` project, so run **Deploy observability** again afterwards to
return to the deploy folder's files.

Grafana is at <http://localhost:3000>; sign in with the credentials from `.env`.

## Send the application's telemetry to it

The application exports OTLP over HTTP. Point it at the collector's published
port. Because the application runs in a different Compose project, use the
Docker Desktop host alias rather than `localhost`:

```powershell
# In the application's .env (dev) and .env.prod (prod)
OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318
```

This is the only link between the application and the stack: the two Compose
files share no services, volumes or networks. Redeploy the application, then
make a request and explore it in Grafana: **Explore -> Tempo**. Each trace's
resource attributes include `service.name`, `deployment.environment` (`dev` or
`prod`), and `service.version`. Check that both environments report with
<http://localhost:9090/api/v1/label/deployment_environment/values>.

## Application metrics

The backend emits OpenTelemetry metrics alongside its traces. Every metric
carries the same `service.name`, `deployment.environment`, and `service.version`
resource attributes as the traces. After the collector exports them to
Prometheus, they appear under the following names:

| Metric | Type | Meaning |
| --- | --- | --- |
| `recipes_created_total` | Counter | Number of recipes created through the web flow. |
| `recipe_views_total` | Counter, `recipe` label | Views of each recipe's detail page, labelled by recipe name. |
| `recipes_average_cost` | Gauge | Average cost per unit across all stored recipes, in COP. |
| `component_creation_failures_total` | Counter, `component` label (`recipe` or `ingredient`) | Create POSTs the server could not complete. See [Creation failure alert](#creation-failure-alert). |

Gunicorn runs two workers by default, so each worker exports its own series for
the same metric (distinguished by the `instance` label). Sum the counters to
get whole-application totals, for example `sum(recipes_created_total)`,
`sum by (recipe) (recipe_views_total)`, and the most viewed recipe with
`topk(1, sum by (recipe) (recipe_views_total))`. The gauge reports the same
value from every worker, so `max by (deployment_environment, service_version) (recipes_average_cost)`
deduplicates it within each deployment.

Explore them in Grafana under **Explore → Prometheus**.

## Business metrics dashboard

Grafana provisions a business-metrics dashboard from files in this repository,
so every freshly created Grafana volume comes up with it already installed:

| Item | Value |
| --- | --- |
| Dashboard | Recipe Calculator - Business Metrics |
| UID | `recipe-business-metrics` |
| Folder | Recipe Calculator |
| Open it | <http://localhost:3000/d/recipe-business-metrics> |

The source files are:

- `grafana/provisioning/dashboards/dashboards.yaml` - the file provider that
  tells Grafana to read dashboard JSON from
  `/etc/grafana/provisioning/dashboards`.
- `grafana/provisioning/dashboards/recipe-business-metrics.json` - the dashboard
  itself.

Because both live in the repository and are bind-mounted into the container, the
dashboard survives `docker compose -f observability/compose.yaml down -v` and
reappears on the next `up`. No extra service, image, or dependency is involved.

### Variables

The dashboard exposes two template variables, both multi-select and both with an
`All` option:

- `environment` - the values of the `deployment_environment` resource label
  (`dev` or `prod`, set per deployment with `DEPLOYMENT_ENVIRONMENT`; a
  deployment that does not set it reports `production`).
- `version` - the values of the `service_version` resource label (for example
  `latest` or a release tag such as `20261014-042438-6c30e73`).

Both variables use `allValue: ".+"` rather than `".*"`, so "All" matches only
series that carry a non-empty label and never shows a blank environment or
version from an older series.

The `version` options are queried with the selected environment as a filter, so
the dropdown only offers versions that environment actually reported and an
impossible environment/version pair cannot be selected. Both variables list the
label values of all three business metrics, so a deployment still shows up when
it has only reported one of them.

Every panel query applies both variables
(`deployment_environment=~"$environment", service_version=~"$version"`), so the
panels describe the selected deployment instead of blending several together.

### Panels

| Panel | Query shape | Notes |
| --- | --- | --- |
| Recipes created (cumulative) | `sum(recipes_created_total{...})` | Sums the per-worker `instance` series into the whole-application total. |
| Recipes created (selected time range) | `sum(increase(recipes_created_total{...}[$__range]))` | Movement during the dashboard's time range. |
| Recipes created over time | `sum(increase(recipes_created_total{...}[$__rate_interval]))` | Recipes per interval; a version that stopped receiving traffic reads as flat. |
| Recipe views per recipe over time | `sum by (recipe) (increase(recipe_views_total{...}[$__rate_interval]))` | One series per recipe name. |
| Most viewed recipe (cumulative) | `topk(1, sum by (recipe) (recipe_views_total{...}))` | Names the single most viewed recipe. |
| Recipe views per recipe (top 10 in range) | `topk(10, sum by (recipe) (increase(recipe_views_total{...}[$__range])))` | Views in range, highest first. |
| Average recipe cost (COP) | `max by (deployment_environment, service_version) (recipes_average_cost{...})` | One labelled value per environment/version pair; `max` only deduplicates the identical per-worker values within each pair. |
| Component creation failures | `sum by (component) (increase(component_creation_failures_total{...}[$__rate_interval]))` | First panel on the dashboard, one stacked series per component (`recipe`, `ingredient`). |
| Average recipe cost over time (COP) | `max by (deployment_environment, service_version) (recipes_average_cost{...})` | Same series as a trend, one line per environment/version pair. |

Counter panels pair `increase()` with a cumulative total, so filtering to one
version still shows how that version moves rather than only a number that grew
since the process started. The application exports metrics once a minute, so the
per-interval counter panels declare a `5m` minimum interval; a shorter window
would regularly hold fewer than two samples and render no data. Cost panels use
the custom `suffix:COP` unit with zero decimals, because Grafana has no Colombian
peso currency unit. A version that has not yet served traffic has no counter
series at all, so its panels read "No data" until its first recipe is created or
viewed.

### Why cost is per pair and counts are added together

Counts are additive: recipes created or views across the selected environments
and versions add up to a meaningful total, so the counter panels use `sum`. The
average cost is not. Each environment/version pair is a different deployment with
its own recipe database, so a mean or sum of costs across deployments would
describe no real data set. The cost panels therefore show one series per
`deployment_environment` / `service_version` pair (legend `environment / version`)
and never combine them; `max` only collapses the identical per-worker values
within a single pair.

The dashboard refreshes every minute, matching the application's one-minute
metric export.

### Reloading the dashboard

The provisioning directory is bind-mounted read-only, so a changed file needs a
container restart before it is read again:

```powershell
docker compose -f observability/compose.yaml restart grafana
```

The file provider also rescans its directory every 30 seconds, so an edited
dashboard JSON is picked up without a restart.

## Creation failure alert

Grafana's built-in alerting raises an alert when saving recipes or ingredients
keeps failing on the server in one deployment. There is no Alertmanager and no
contact point; the alert is read from Grafana's alert API.

### The metric

`component_creation_failures_total` counts recipe and ingredient create
requests (POST to the recipe or ingredient "add" page) that the server could
not complete: an unhandled exception, including a database error inside the
recipe's save transaction, or a 5xx response. Its `component` label is
`recipe` or `ingredient`, and it carries the usual `service_name`,
`deployment_environment` and `service_version` resource labels. It is recorded
by the `count_creation_failures()` view decorator in `calculator/metrics.py`,
which re-raises the exception unchanged, so the user still gets the normal
error page and a recipe still leaves no partial rows behind.

It does not move for a form redisplayed with validation errors (for example a
negative weight, a missing name, or the same ingredient twice), for GET
requests, for successful creates, or for edits and deletes. Each worker starts
both component series at `0`, so Prometheus already has the series when the
first failure happens and `increase()` counts that failure as well.

### The rule

| Item | Value |
| --- | --- |
| Rule | Repeated recipe and ingredient creation failures |
| UID | `component-creation-failures` |
| Folder / group | Recipe Calculator / `component-creation` |
| Source | `grafana/provisioning/alerting/component-creation-failures.yaml` |
| Query | `sum by (service_name, deployment_environment, service_version) (increase(component_creation_failures_total[10m]))` |
| Condition | 3 or more (`gte 3`) |
| Evaluation | every 1 minute, pending period 1 minute |
| No data / error | `OK` (the rule stays Normal) |

Like the dashboard, the rule is bind-mounted from the repository, so it
survives `docker compose -f observability/compose.yaml down -v` and comes back
on the next `up`. A changed rule file needs
`docker compose -f observability/compose.yaml restart grafana`.

The dashboard and the rule share one "Recipe Calculator" folder, and both
provisioning files name it **by title only**. Grafana 13 alert rule files cannot
name a folder uid (a `folderUid` on a rule group is silently ignored), and
Grafana provisions alerting before dashboards. If the dashboard provider pinned
a `folderUid`, a fresh volume would get two folders called "Recipe
Calculator", with the rule in one and the dashboard in the other. Because both
match by title, they converge on one folder: on a fresh volume it gets a
generated uid; on an older volume it keeps its existing `recipe-calculator`
uid. Refer to the folder by its title, not by its uid. Keep the two titles
identical.

**Threshold:** the alert fires when one deployment (one environment and version
pair) has 3 or more failures within the last 10 minutes, recipes and
ingredients counted together. This is a single-user application, so one
failure can be a one-off the user simply retries; three failures in 10 minutes
means the user tried again and is still blocked from saving their work. One or
two failures do not fire. Because the query groups by environment and version,
two failures in dev and two in prod (or in two versions) stay separate and do
not fire. The rule resolves on its own once the deployment's last 10 minutes
hold fewer than 3 failures.

The one-minute pending period covers the application's one-minute metric
export. `increase()` treats a counter that drops as a reset, so a worker or
container restart never looks like a burst of failures. With no failure series
at all (or Prometheus unreachable) the rule stays Normal instead of raising a
NoData or Error alert.

Each firing alert carries:

- labels `service`, `environment` and `version` (from the series'
  `service_name`, `deployment_environment` and `service_version`) and the fixed
  `owner=recipe-calculator-oncall`;
- annotation `summary` naming the environment, version and failure count;
- annotation `description` saying users cannot save new recipes or
  ingredients;
- annotation `dashboard_url`,
  `http://localhost:3000/d/recipe-business-metrics?var-environment=<env>&var-version=<version>&from=now-1h&to=now`,
  which opens the business dashboard filtered to the failing deployment with
  the **Component creation failures** panel at the top;
- annotation `runbook` with the first step to take.

Grafana expands `$NAME` in provisioning files as an environment variable, so
the rule file writes the label templates as `{{ $$labels.deployment_environment }}`;
Grafana stores and renders them as `{{ $labels.deployment_environment }}`.

Read the alert state from the API with the admin credentials from `.env`:

```powershell
curl.exe -s -u admin:<password> http://localhost:3000/api/prometheus/grafana/api/v1/alerts
curl.exe -s -u admin:<password> http://localhost:3000/api/v1/provisioning/alert-rules/component-creation-failures
```

### Live check (dev only)

Only the dev deployment is touched; never stop or change the production
containers (`recipe-cost-calculator-prod-*`).

1. With dev exporting to this stack, stop only the dev database container:
   `docker stop deploy-db-1`.
2. Within a few minutes, try to save three recipes on dev
   (<http://localhost:8000/recipes/add/>). Each shows the error page.
3. Within about 3 minutes the rule is Firing in
   `/api/prometheus/grafana/api/v1/alerts`, with `environment=dev` and the dev
   release tag as `version`. Its `dashboard_url` opens the dashboard filtered
   to that deployment, with the failures on the **Component creation
   failures** panel.
4. Start the database again: `docker start deploy-db-1`. The alert resolves
   within about 12 minutes, once the 10-minute window no longer holds 3
   failures.

## Notes

- The metrics and traces pipelines are active; the logs pipeline is wired and
  ready for future instrumentation.
- The dashboard queries `recipes_average_cost`, the name the current code emits.
  A deployment that set a `COP` unit on the gauge instead exported
  `recipes_average_cost_COP`; the dashboard deliberately ignores that series.
- Tempo flushes fresh traces into searchable blocks every 5 minutes and picks
  them up within 10 seconds, so a brand-new trace may not appear in a search
  immediately. Force a flush with `curl -X POST http://localhost:3200/flush`.
  Fetching a trace by its ID always works right away.
- The collector's own health metrics are published at `:8888` and scraped by
  Prometheus.
- Config files are bind-mounted read-only from the deploy folder, so edits
  need a container restart: `docker compose restart <service>` from the
  deploy folder (the workflow does this for the files it changes), or
  `docker compose -f observability/compose.yaml restart <service>` from a
  checkout.
