# Recipe Cost Calculator

An in-progress Django application for calculating confectionery recipe costs.

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

- **Build** ([.github/workflows/build.yml](.github/workflows/build.yml)) — on
  every push to `main`, builds the image on the self-hosted runner, pushes it
  to the local registry with the timestamp tag and the `dev` tag, then
  deploys it to the dev environment.
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
   on every push: it builds the image, tags it with a
   `YYYYMMDD-HHMMSS-shortsha` tag plus `dev`, pushes both to the local
   registry, then deploys to the dev environment.

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

All three workflows run on a **self-hosted runner** installed on this machine
(Settings → Actions → Runners → New self-hosted runner, Windows): they must run
locally because the registry lives at `localhost:5000`. The machine needs
Docker Desktop running, a local registry container, Git Bash, and a `.env`
(dev) plus `.env.prod` (production) file in `DEPLOY_PATH`.

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

For non-container development, create and activate a virtual environment, then
install dependencies:

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
