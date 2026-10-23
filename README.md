# Recipe Cost Calculator

Recipe Cost Calculator is a web application for a small confectionery producer
who prices their own recipes. It answers two questions: what does one unit of a
recipe cost, and what does a batch of N units cost?

You enter each ingredient once, with the price and weight of the package you
buy. You then enter each recipe with the quantity of every ingredient it uses
for one unit. The application converts kilograms to grams and does the
arithmetic, so you do not need a spreadsheet and you avoid unit-conversion
mistakes. It is a Django application backed by PostgreSQL, and prices are in
Colombian pesos (COP).

## Quick start

Prerequisite: Docker with Compose v2 (for example Docker Desktop), running.
Nothing else needs to be installed, created or edited.

From the repository root of a fresh clone, start the Django web service and
PostgreSQL with one command:

```shell
docker compose --env-file quickstart.env up --build --detach
```

Then open <http://localhost:8080/>. `docker compose --env-file quickstart.env ps`
shows `db` and `web` as `healthy` once the application is ready.

- **Stop it** (your data is kept for the next `up`):
  `docker compose --env-file quickstart.env down`
- **Wipe its data** (removes the quick-start database volume):
  `docker compose --env-file quickstart.env down -v`

The quick start runs as its own Compose project,
`recipe-cost-calculator-quickstart`, on port `8080`, so it never touches a dev
or production deployment on the same host. `quickstart.env` is for local
evaluation only: its values, including the secret key and database password,
are public. It is **not for deployments**; dev and production use `.env` and
`.env.prod`, as described in the [operator guide](docs/operator-guide.md).

## Features

The navigation bar on every page links to **Ingredients**, **Recipes** and
**Calculator**. The home page is at `/`. After a successful add, edit or
delete, the application redirects and shows a status message, such as
"Ingredient added successfully."

### Ingredients

An ingredient is something you buy, described by its package.

| Page | URL | What you can do |
| --- | --- | --- |
| List | `/ingredients/` | See every ingredient with its brand, purchase location, package weight and package price. |
| Add | `/ingredients/add/` | Enter the name, brand, purchase location, package weight, package unit (`g` or `kg`) and package price. |
| Detail | `/ingredients/<id>/` | See one ingredient, with buttons to edit or delete it. |
| Edit | `/ingredients/<id>/edit/` | Change any of the fields. Recipes that use the ingredient use the new price in their next calculation. |
| Delete | `/ingredients/<id>/delete/` | Confirm the deletion. It is blocked while any recipe uses the ingredient: you return to the detail page with the message "Ingredient *name* cannot be deleted because it is used by a recipe." |

### Recipes

A recipe is one unit of a product you make, such as one truffle.

| Page | URL | What you can do |
| --- | --- | --- |
| List | `/recipes/` | See every recipe with its weight per unit. |
| Add | `/recipes/add/` | Enter the name, the weight of one finished unit in grams, and one row per ingredient (ingredient, quantity for one unit, unit `g` or `kg`). **Add ingredient row** and **Remove row** let you use any number of rows. |
| Detail | `/recipes/<id>/` | See the weight per unit and each ingredient's quantity, with buttons to edit, delete or calculate the recipe. |
| Edit | `/recipes/<id>/edit/` | Change the name, the weight per unit and the ingredient rows, including adding and removing rows. |
| Delete | `/recipes/<id>/delete/` | Confirm the deletion. The recipe and its ingredient rows are removed; the ingredients themselves stay. |

A recipe and its ingredient rows are saved together, all or nothing. If any
row is invalid, nothing is saved, on add and on edit.

### Recipe cost calculator

At `/calculator/`, pick a recipe, enter a whole number of units and press
**Calculate**. The result appears below the form on the same page. The
**Calculate recipe** button on a recipe's detail page opens the calculator
with that recipe already selected (`/calculator/?recipe=<id>`).

### Health endpoint

`/health/` runs a database query. It returns `OK` (HTTP 200, plain text) when
the query succeeds and `Database unavailable.` (HTTP 500) when it fails. The
`web` container's health check in `compose.yaml` uses it.

## Expected behaviour

### Calculation rules

- **Grams are the internal unit.** A weight entered in kilograms is converted
  to grams (multiplied by 1000) before any cost or total is calculated.
- **Cost per gram** = package price / package weight in grams.
- **Ingredient cost** = quantity used in grams × cost per gram.
- **Scaling is linear.** For N units, every ingredient quantity and every
  ingredient cost is multiplied by N.
- **The result shows:**
  - the cost per unit: the ingredient cost of one unit;
  - the weight per unit: the value saved on the recipe (it is not computed
    from the ingredients);
  - for every ingredient, the adjusted quantity (in the unit the recipe uses
    for it) and its cost;
  - the total cost: the sum of the adjusted ingredient costs;
  - the total weight: the sum of the adjusted ingredient weights, in grams.
- **Exact decimals.** All money and weight arithmetic uses exact decimal
  numbers, never floating point. Rounding happens only when a value is
  displayed: money to 2 decimal places (half up), shown as `COP $1234.56`
  without a thousands separator; weights to 3 decimal places, without trailing
  zeros.
- **Calculating changes no stored data.** It saves no result, history or stock
  movement. Each calculation uses the ingredient prices saved at that moment.

### Worked example

A recipe for **Chocolate truffles** has a weight per unit of `19.5 g` and these
ingredients. The dark chocolate is bought in `kg` and used in `g`:

| Ingredient | Package weight | Package price | Quantity per unit |
| --- | --- | --- | --- |
| Cocoa powder | 250 g | COP $13500.00 | 1.5 g |
| Dark chocolate 53% | 1 kg | COP $46900.00 | 12 g |
| Heavy cream | 900 g | COP $17900.00 | 6 g |

The costs per gram are 13500 / 250 = 54 for cocoa powder, 46900 / 1000 = 46.9
for dark chocolate, and 17900 / 900 = 19.888… for heavy cream.

Calculating **24** units shows this on the calculator page:

| Ingredient | Adjusted quantity | Cost |
| --- | --- | --- |
| Cocoa powder | 36 g | COP $1944.00 |
| Dark chocolate 53% | 288 g | COP $13507.20 |
| Heavy cream | 144 g | COP $2864.00 |

| Result | Value |
| --- | --- |
| Requested units | 24 |
| Cost per unit | COP $763.13 |
| Weight per unit | 19.5 g |
| Total cost | COP $18315.20 |
| Total weight | 468 g |

The exact cost per unit is COP $763.1333…; it is rounded only for display. That
is why the total cost is COP $18315.20 and not 24 × COP $763.13 = COP $18315.12.
The test `tests/test_readme.py` builds this example, runs it through the
calculation service and the page's formatting, and fails if any figure here
differs.

### What the application rejects

- Package weight, package price, recipe weight per unit and ingredient
  quantity must be greater than zero. Weights and quantities take up to 3
  decimal places (smallest `0.001`), prices up to 2 (smallest `0.01`).
- A weight unit is `g` or `kg`; nothing else can be chosen.
- An ingredient needs a name, brand and purchase location. A recipe needs a
  name and at least one ingredient row ("Add at least one ingredient to the
  recipe.").
- An ingredient appears at most once in a recipe ("Each ingredient may only be
  used once in a recipe.").
- The calculator needs a recipe and a unit count that is a whole number greater
  than zero ("Enter a positive whole number."). `0`, `-1` and `1.5` are
  rejected.
- Invalid input shows the same form again with your values and a message next
  to each wrong field (or above the ingredient rows, for the two recipe rules
  above). Nothing is saved.
- Opening the detail, edit or delete page of an ingredient or recipe that does
  not exist returns HTTP 404.

### Out of scope

The application is for one user and one currency (COP). It has:

- no authentication: the ingredient, recipe and calculator pages have no login;
- no inventory or stock tracking;
- no labour, packaging or overhead costs (it reports ingredient costs, not sale
  prices);
- no multiple currencies.

## Operations

For clean checkout setup, production configuration, backups, restores, updates,
and troubleshooting, follow the [operator guide](docs/operator-guide.md).

## Observability

The backend exports OpenTelemetry traces and application metrics. A separate
[observability stack](observability/README.md) (OpenTelemetry Collector,
Prometheus, Loki, Tempo, and Grafana) receives and stores them; see its guide
for how to run it and point the application at it. The **Deploy observability**
workflow ([.github/workflows/deploy-observability.yml](.github/workflows/deploy-observability.yml))
deploys it to the folder named by the `OBSERVABILITY_PATH` repository variable,
with Grafana credentials from an untracked `.env` there (see
[`observability/env.example`](observability/env.example)). Stopping the stack
never affects the application.

## CI/CD

Images are built in GitHub Actions, pushed to a container registry, and pulled
onto a Docker host that serves dev on port `8000` and production on port
`8001`. Every image is tagged with a release tag, `YYYYMMDD-HHMMSS-shortsha`
(UTC), for example `20260818-163457-83242da`; the commit is the part after the
last `-`. There is a single branch, `main`, and every deployment runs a release
with the `compose.yaml` from the commit that built it.

- **CI** ([.github/workflows/ci.yml](.github/workflows/ci.yml)) — runs the
  whole automated test suite on GitHub-hosted `ubuntu-latest` runners with
  Python 3.13 and dependencies from `requirements.txt` only. It needs no
  secret, no repository variable and no machine of ours, and grants only
  `contents: read`. It has two jobs:
  - **tests** runs `python -m pytest` against a PostgreSQL 17 service
    container. The job sets `CI_EXPECTED_DATABASE_VENDOR=postgresql`, so
    [`tests/test_ci_database.py`](tests/test_ci_database.py) fails the run if
    the suite did not really use PostgreSQL.
  - **integration** installs Chromium with
    `python -m playwright install --with-deps chromium`, then runs
    `python -m pytest -m compose` and `python -m pytest e2e` against an
    isolated Compose stack it builds and removes itself.

  It runs on every pull request; the result appears as the **CI / tests** and
  **CI / integration** checks at the bottom of the pull request's
  **Conversation** tab and in its **Checks** tab. It can also be run by hand
  (**Actions → CI → Run workflow**). A failing test, a failed install or a
  PostgreSQL service that never becomes healthy fails the run.
- **Build** ([.github/workflows/build.yml](.github/workflows/build.yml)) — on
  every push to `main`, first runs the CI workflow (its `ci / tests` and
  `ci / integration` jobs; CI has no push trigger of its own, so the tests run
  once per push). Only after they pass does it build the image on the
  self-hosted runner, push it to the local registry with the timestamp tag and
  the `dev` tag, then deploy it to the dev environment. A failing test stops
  the push there: no image is built and dev is not touched. The build and dev
  deploy run only when the `SELF_HOSTED_RUNNER` repository variable is `true`;
  otherwise they show as skipped (see
  [Required repository configuration](#required-repository-configuration)).
- **Deploy** ([.github/workflows/deploy.yml](.github/workflows/deploy.yml)) —
  runs on the self-hosted runner. Given a release tag, it checks out the commit
  named by the tag, pulls that image, and serves it with that commit's
  `compose.yaml`. Run it manually with an older release tag to roll `dev` or
  `prod` back. It rejects anything that is not a release tag (`dev`, `prod`,
  `latest`, a typo) before changing any container.
- **Promote dev to production**
  ([.github/workflows/promote-to-production.yml](.github/workflows/promote-to-production.yml)) —
  manual and confirmed (a required **confirm** checkbox). By default it
  promotes the release the running dev container reports in `APP_VERSION`, not
  the `dev` registry tag; an explicit release tag promotes that one instead. It
  re-tags the image `prod` in the registry (never rebuilds) and deploys it to
  production, and the run summary shows the release and its commit.

### Running a deployment

1. Start the self-hosted runner in a command prompt and leave it running:

   ```cmd
   cd <repository folder>\actions-runner
   run.cmd
   ```

   It prints `Listening for Jobs` when it is online. Verify it under
   **Settings → Actions → Runners** (status `Idle`).

2. **Dev (automatic)** — push to `main`. The **Build and push** workflow runs
   on every push: it runs the CI tests, and once they pass it builds the
   image, tags it with a `YYYYMMDD-HHMMSS-shortsha` tag plus `dev`, pushes
   both to the local registry, then deploys to the dev environment.

3. **Dev or prod (manual, also rollback)** — **Actions → Deploy → Run
   workflow**, choose the **environment** (`dev` or `prod`) and enter a
   release tag as the **image tag**, such as `20261014-191754-9bdd779`. The
   runner checks out commit `9bdd779`, pulls that image, and serves it with
   that commit's `compose.yaml`, polling until the web service is healthy. To
   roll back, enter an older release tag.

4. **Production (promote)** — **Actions → Promote dev to production → Run
   workflow**. Tick **confirm** and leave the tag empty to promote what dev is
   running, or enter a release tag. The image is re-tagged `prod` in the
   registry and deployed to production.

The exact steps, including how to find which release each environment runs,
are in the [operator guide](docs/operator-guide.md#releasing-and-rolling-back).

After a deployment completes, confirm health on the host:

```powershell
docker compose --env-file .env ps   # dev, from DEPLOY_PATH
docker compose --env-file .env.prod ps   # production
curl http://localhost:8000/health/   # dev
curl http://localhost:8001/health/   # production
```

### Required repository configuration

| Name | Kind | Purpose |
| --- | --- | --- |
| `IMAGE_REPOSITORY` | Variable | Full image repository, e.g. `localhost:5000/recipe_app`. |
| `DEPLOY_PATH` | Variable | Directory on this machine holding `compose.yaml` and the `.env`/`.env.prod` files, e.g. `C:/Users/.../ai_dev_project/deploy`. |
| `REGISTRY_USERNAME` | Secret | Registry login user (omit for an unauthenticated registry). |
| `REGISTRY_PASSWORD` | Secret | Registry login password (omit for an unauthenticated registry). |
| `SELF_HOSTED_RUNNER` | Variable | Set to `true` only on a repository that has the self-hosted runner below. It enables the automatically triggered self-hosted jobs: the build and dev deploy in **Build and push**, and **Deploy observability**. Unset or any other value, those jobs show as skipped instead of waiting for a runner; the CI tests still run. |

The CI workflow needs none of these and runs on GitHub-hosted runners. The
Build and push, Deploy, Promote dev to production and Deploy observability
workflows run on a **self-hosted runner** installed on this machine
(Settings → Actions → Runners → New self-hosted runner, Windows): they must run
locally because the registry lives at `localhost:5000`. The runner must be
version 2.327.1 or later: the workflows use `actions/checkout@v7`, a Node.js 24
action, and older runners cannot run Node.js 24 actions. The machine needs
Docker Desktop running, a local registry container, Git Bash, and a `.env`
(dev) plus `.env.prod` (production) file in `DEPLOY_PATH`. On a repository
without that runner, such as a public fork, leave `SELF_HOSTED_RUNNER` unset:
pushes to `main` then run only the tests. The manual Deploy and Promote dev to
production workflows are not gated by the variable and always need the runner.

### Running the CI checks locally

The CI jobs run these commands, from the repository root with the virtual
environment active (see [Direct Python setup](#direct-python-setup)):

```powershell
python -m pip install -r requirements.txt
python -m pytest                                      # tests job
python -m playwright install --with-deps chromium     # integration job
python -m pytest -m compose
python -m pytest e2e
```

Without database variables, `python -m pytest` uses the SQLite fallback. To
run it against PostgreSQL the way the **tests** job does, start a throwaway
PostgreSQL 17 container and point Django at it with the same variables the
job sets (the `DJANGO_DB_*` variables select PostgreSQL in
[`config/settings.py`](config/settings.py); pytest-django creates and drops
its own `test_calculator` database). If port `5432` is taken, publish another
host port and set `DJANGO_DB_PORT` to it:

```powershell
docker run --detach --name recipe-ci-postgres --publish 127.0.0.1:5432:5432 `
  --env POSTGRES_DB=calculator --env POSTGRES_USER=calculator `
  --env POSTGRES_PASSWORD=calculator postgres:17-alpine
$env:DJANGO_DB_ENGINE = "django.db.backends.postgresql"
$env:DJANGO_DB_NAME = "calculator"
$env:DJANGO_DB_USER = "calculator"
$env:DJANGO_DB_PASSWORD = "calculator"
$env:DJANGO_DB_HOST = "127.0.0.1"
$env:DJANGO_DB_PORT = "5432"
$env:CI_EXPECTED_DATABASE_VENDOR = "postgresql"
python -m pytest
docker rm --force --volumes recipe-ci-postgres
```

`--with-deps` also installs the system libraries Chromium needs on Linux (it
uses `sudo` there); on a Windows or macOS workstation
`python -m playwright install chromium` is enough.

## Requirements

- Python 3.13
- Docker Desktop with Docker Compose (for the supported local environment)

## Production Compose deployment

Docker Compose runs the production-oriented Django web service and PostgreSQL.
The application runs as the non-root `app` user under Gunicorn, and only the
web application's port (`8000`) is published to the host. PostgreSQL is
available only to services on the Compose network.

1. Create a deployment environment file from the tracked example:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Replace every placeholder. These variables are required:

   | Variable | Purpose |
   | --- | --- |
   | `DJANGO_SECRET_KEY` | A long, random Django secret key. |
   | `DJANGO_DEBUG` | Must be `false` in this configuration. |
   | `DJANGO_ALLOWED_HOSTS` | Comma-separated public host names. |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated `http://` or `https://` origins. |
   | `DJANGO_TIME_ZONE` | Application time zone. |
   | `POSTGRES_DB` | PostgreSQL database name. |
   | `POSTGRES_USER` | PostgreSQL username. |
   | `POSTGRES_PASSWORD` | PostgreSQL password. |

   `DJANGO_DB_*` values are retained in the example for direct local use, but
   the production web container derives its database credentials from the
   `POSTGRES_*` values. Inside Compose it always connects to `db:5432`.
   `localhost:5430` is not used by a container; it would only be relevant to a
   host-published development database port.

The backend is instrumented with OpenTelemetry. Each request span reports the
service name (`OTEL_SERVICE_NAME`), the deployment environment (from
`DJANGO_ENV`), and the deployed version (`APP_VERSION`, derived from the image
tag). Spans go to the container logs by default; set `OTEL_EXPORTER_OTLP_ENDPOINT`
to send them to a collector, or `OTEL_SDK_DISABLED=true` to disable tracing.

3. Build and start the deployment:

   ```powershell
   docker compose up --build --detach
   ```

Startup runs migrations and collects static files before Gunicorn accepts
traffic. Any migration or collection failure stops the web container visibly;
inspect it with the logs command below. Compose waits for PostgreSQL to be
healthy before starting Django. Inspect both service health with:

```powershell
docker compose ps
```

Check migration status explicitly when needed:

```powershell
docker compose exec web python manage.py showmigrations
```

Follow web and database logs:

```powershell
docker compose logs --follow web db
```

Run the documented deployment smoke check after startup:

```powershell
(Invoke-WebRequest http://localhost:8000/health/).StatusCode
(Invoke-WebRequest http://localhost:8000/).StatusCode
(Invoke-WebRequest http://localhost:8000/static/calculator/site.css).StatusCode
docker compose ps
```

All three HTTP commands must output `200`; `docker compose ps` must show both
`web` and `db` as `healthy`. The health endpoint performs a database query, so
it returns a non-200 response if PostgreSQL cannot be reached.

Stop the deployment gracefully while retaining PostgreSQL data:

```powershell
docker compose down
```

The named `postgres_data` volume retains database data across subsequent
`docker compose up` commands. Do not use `docker compose down -v` in a
deployment unless intentionally discarding its database; backup and restore
procedures are documented separately.

## Direct Python setup

This setup is for development without containers.

Create and activate a virtual environment, then install dependencies:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For direct Python use, provide database environment variables in your shell. The
tracked example is configured for production Compose, so set `DJANGO_ENV` to
`development`, `DJANGO_DB_ENGINE` to `django.db.backends.sqlite3`, and
`DJANGO_DB_NAME` to `db.sqlite3` if you want to use the lightweight local SQLite
fallback. Environment values are read by Django from the process environment;
load `.env` with your preferred shell or development tool.

Run database migrations and start the development server:

```powershell
python manage.py migrate
python manage.py runserver
```

Run the automated tests:

```powershell
python -m pytest
```

To run them against PostgreSQL the way CI does, see
[Running the CI checks locally](#running-the-ci-checks-locally).

Run the integration tests against the Compose deployment. They need Docker
running, build an isolated copy of the stack on a free port, and remove it
afterwards without touching `.env` or an existing deployment's data:

```powershell
python -m pytest -m compose
```

Run the browser end-to-end tests in `e2e/`, which drive Chromium with Playwright
against the same isolated Compose stack. Install the browser once, then run:

```powershell
python -m playwright install chromium
python -m pytest e2e
```

Set `$env:E2E_HEADED = "1"` first to watch the browser.

## Project map

Where each part of the project is documented or implemented, and how to check
it.

| Topic | Where | How to check |
| --- | --- | --- |
| Problem description | [Intro](#recipe-cost-calculator), [Features](#features), [Expected behaviour](#expected-behaviour) | Read the top of this README; the worked example is checked by `tests/test_readme.py`. |
| Product specification and task tracker | [`_docs/architecture.md`](_docs/architecture.md), [`_docs/issues/`](_docs/issues/) | Every `issueN.md` has a status line and acceptance criteria. Issues 22 to 31 and 34 also carry an Engineer comment and a QA verdict (Issue 25, a live check, records live runs instead of a QA verdict); Issues 24 to 31 and 34 include the orchestrator's closing comment. Good examples: [`issue29.md`](_docs/issues/issue29.md), [`issue30.md`](_docs/issues/issue30.md), [`issue31.md`](_docs/issues/issue31.md). |
| Agent team | [`_docs/team/`](_docs/team/), [`_docs/process.md`](_docs/process.md) | The PM, Engineer and QA roles and the orchestrator's lifecycle; [`issue29.md`](_docs/issues/issue29.md) shows an Engineer comment, a QA FAIL, the fix, a QA PASS and the closing. |
| Context management | [`AGENTS.md`](AGENTS.md), [`_docs/`](_docs/) | `AGENTS.md` tells every agent session which `_docs` files to read first and to record durable rules there. |
| Application | [`calculator/`](calculator/), [`config/urls.py`](config/urls.py), [`templates/`](templates/) | Run the [Quick start](#quick-start), open `http://localhost:8080/` and enter the [worked example](#worked-example). |
| Testing | [`tests/`](tests/), [`e2e/`](e2e/), [`_docs/testing-guidelines.md`](_docs/testing-guidelines.md) | Run `python -m pytest` (see [Direct Python setup](#direct-python-setup)); `python -m pytest -m compose` and `python -m pytest e2e` need Docker. |
| Containerization | [`Dockerfile`](Dockerfile), [`compose.yaml`](compose.yaml), [`quickstart.env`](quickstart.env) | Run the [Quick start](#quick-start); `docker compose --env-file quickstart.env ps` shows `db` and `web` as `healthy`. |
| Deployment | [`docs/operator-guide.md`](docs/operator-guide.md), [`deploy.yml`](.github/workflows/deploy.yml), [`promote-to-production.yml`](.github/workflows/promote-to-production.yml) | Dev (port `8000`) and production (port `8001`) run on the author's machine through a local self-hosted runner. This public repository has no runner: the jobs gated by `SELF_HOSTED_RUNNER` (the build and dev deploy in **Build and push**, and **Deploy observability**) show as skipped, and the manual **Deploy** and **Promote dev to production** workflows are not gated, so a run would wait for a runner. A recorded demo is still open: [Issue 33](_docs/issues/issue33.md). |
| CI/CD | [`ci.yml`](.github/workflows/ci.yml), [`build.yml`](.github/workflows/build.yml), [CI/CD](#cicd) | The **CI** workflow runs the whole test suite on every pull request; a push to `main` runs it inside **Build and push**, before the build and dev deploy. Results are in the repository's **Actions** tab. |
| Observability | [`observability/README.md`](observability/README.md), [`config/telemetry.py`](config/telemetry.py), [`calculator/metrics.py`](calculator/metrics.py), [`recipe-business-metrics.json`](observability/grafana/provisioning/dashboards/recipe-business-metrics.json) | When an OTLP endpoint is set, the application exports OpenTelemetry traces and metrics to the stack. Traces go to Tempo and are viewed in Grafana **Explore**; metrics go to Prometheus and are shown on the provisioned business-metrics dashboard. Structured logs correlated by trace ID are planned and not built yet. |
| Alerting | [`component-creation-failures.yaml`](observability/grafana/provisioning/alerting/component-creation-failures.yaml), [Creation failure alert](observability/README.md#creation-failure-alert) | The rule fires on repeated recipe or ingredient creation failures; the observability guide has a dev-only live check. |
| On-call agent | [`on-call-engineer/README.md`](on-call-engineer/README.md), [`issue29.md`](_docs/issues/issue29.md) | The poller hands a firing alert to a headless coding agent on its own branch; the issue's "Live check" records a drill on dev. |
