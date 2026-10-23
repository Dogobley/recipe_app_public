# Operator guide

This guide operates the Recipe Cost Calculator for one user. It uses the
repository's production-oriented Docker Compose configuration: the `web`
service runs Django with Gunicorn and the `db` service runs PostgreSQL. It does
not require a reverse proxy, a separate frontend service, or any third-party
hosted service.

Commands below are PowerShell commands and must be run from the repository
root unless noted otherwise. They have been checked against the tracked
`compose.yaml`, `.env.example`, `Dockerfile`, and Django management commands.
Every command that interacts with a Git remote, Docker, a running deployment,
or a backup file is an **environment-specific example**: it needs the stated
assumptions, your chosen values, and an operator's review before execution.
The commands use the exact service names and paths from this repository.
Commands specifically labelled **environment-specific example** additionally
contain a value that must be replaced before use.

## Quick start for local evaluation

To try the application without configuring a deployment, run this from the
repository root of a fresh clone; it needs no `.env` and no edits:

```powershell
docker compose --env-file quickstart.env up --build --detach
docker compose --env-file quickstart.env ps
(Invoke-WebRequest http://localhost:8080/health/).StatusCode
```

Open `http://localhost:8080/`. Stop it with
`docker compose --env-file quickstart.env down` (data is kept), and wipe its
database with `docker compose --env-file quickstart.env down -v`.

`quickstart.env` is for local evaluation only. Its values, including the secret
key and database password, are committed and public, so it must never be used
for a deployment or for data you need to keep private. It runs as its own
Compose project, `recipe-cost-calculator-quickstart`, with its own containers,
network, image and `recipe-cost-calculator-quickstart_postgres_data` volume on
port `8080`, so starting or removing it never changes dev or production. The dev
and production deployments keep using `.env` and `.env.prod`, as described in
the rest of this guide; every other `docker compose` command here targets them,
not the quick start.

## Prerequisites and first local deployment

Install Git and Docker Desktop with Docker Compose v2, start Docker Desktop,
and make sure host port `8000` is free. Docker Desktop must be allowed to pull
the public `postgres:17-alpine` and Python base images on the first build.

The following checkout command is an **environment-specific example**: replace
`<repository-url>` with the Git remote that your organization provides.

```powershell
git clone <repository-url> recipe-cost-calculator
Set-Location recipe-cost-calculator
```

From an already clean checkout, create the untracked deployment configuration:

```powershell
Copy-Item .env.example .env
```

Edit `.env` as described in [Production configuration](#production-configuration),
then build and start the local deployment:

```powershell
docker compose up --build --detach
docker compose ps
(Invoke-WebRequest http://localhost:8000/health/).StatusCode
```

Both `web` and `db` must report `healthy`, and the request must output `200`.
The health endpoint checks both Django and PostgreSQL. For a fuller smoke
check, also run:

```powershell
(Invoke-WebRequest http://localhost:8000/).StatusCode
(Invoke-WebRequest http://localhost:8000/static/calculator/site.css).StatusCode
```

Each command must output `200`.

## Production configuration

Copy `.env.example` to `.env` and keep `.env` private; it contains deployment
secrets and is intentionally not committed. The Compose file reads the
variables below. `web` derives its `DJANGO_DB_*` connection values from the
`POSTGRES_*` values and connects to `db:5432` inside the Compose network.
Do not set `localhost` as the database host for the `web` container: there,
`localhost` means that container itself.

| Variable | Required for Compose production | Meaning and production value |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Yes | A unique, long random Django secret. |
| `DJANGO_DEBUG` | Yes | Must be `false`. |
| `DJANGO_ALLOWED_HOSTS` | Yes | Comma-separated public hostnames, for example `app.example.test`. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Yes | Comma-separated origins including scheme, for example `https://app.example.test`. |
| `DJANGO_TIME_ZONE` | No (defaults to `UTC`) | An IANA time zone such as `America/Bogota`. |
| `POSTGRES_DB` | Yes | The database name; choose a stable, non-secret name. |
| `POSTGRES_USER` | Yes | PostgreSQL role used by the application. |
| `POSTGRES_PASSWORD` | Yes | A long, unique database password. |
| `DJANGO_ENV` | Set by Compose | `compose.yaml` sets this to `production`; do not override it in the container. |
| `DJANGO_DB_ENGINE`, `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST`, `DJANGO_DB_PORT` | Direct-Python only | These optional `.env.example` entries are for direct local Django use. Production Compose derives them from `POSTGRES_*`, forces PostgreSQL, and uses `db:5432`. |
| `GUNICORN_WORKERS`, `GUNICORN_TIMEOUT`, `GUNICORN_GRACEFUL_TIMEOUT` | No | Optional container tuning; defaults are `2`, `60`, and `30` seconds. |
| `APP_VERSION` | Set at build time | The deployed version reported as `service.version`. It is baked into the image at build time from the build tag (`YYYYMMDD-HHMMSS-shortsha`), so promoting or redeploying a tag keeps reporting it. A local `docker compose up --build` without `IMAGE_TAG` reports `latest`; a plain `docker build .` reports `unknown`. |
| `DEPLOYMENT_ENVIRONMENT` | No (defaults to `production`) | The `deployment.environment` label, for example `dev` or `prod`, used to tell deployments apart in Grafana. It does not change `DJANGO_ENV`, which stays `production`. |
| `WEB_PORT` | No (defaults to `8000`) | Host port the web service is published on. Set `8001` for production so it can run beside dev. |
| `OTEL_SERVICE_NAME` | No (defaults to `recipe-cost-calculator`) | The `service.name` resource attribute attached to every span. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | OTLP/HTTP endpoint such as `http://host.docker.internal:4318`; when set, spans are exported there instead of the console. |
| `OTEL_SDK_DISABLED` | No (defaults to `false`) | Set to `true` to turn tracing off entirely. |

Every request is traced with OpenTelemetry. Each span carries the service
name, the deployment environment (`DEPLOYMENT_ENVIRONMENT`, default `production`), and
the deployed version (`APP_VERSION`). Spans are written to the container's standard
output by default, so `docker compose logs web` shows them; set
`OTEL_EXPORTER_OTLP_ENDPOINT` to send them to a collector instead.

Generate values locally; never paste these examples' output into source
control:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put the first result in `DJANGO_SECRET_KEY` and the second in
`POSTGRES_PASSWORD`. Replace every `replace-with-...` value in `.env` before
starting production. For local host-only use, `DJANGO_ALLOWED_HOSTS` and
`DJANGO_CSRF_TRUSTED_ORIGINS` can retain the documented `localhost` values;
for a public deployment they must name its real host and HTTPS origin.

Build and start a configured production deployment:

```powershell
docker compose up --build --detach
docker compose ps
docker compose logs --follow web db
```

`logs --follow` continues until you press `Ctrl+C`; it does not stop the
containers. After both services are healthy, run the health and static-asset
checks in the first section. Shut down gracefully while retaining the named
`postgres_data` volume with:

```powershell
docker compose down
```

Do not run `docker compose down -v` for an installation that has data to keep.
That command removes the PostgreSQL volume.

## Environments: dev and production

The same `compose.yaml` runs two independent environments on one host. Each is
its own Compose project, so containers, network, built image, and the
`postgres_data` volume are never shared, and each has its own secrets.

| | Dev | Production |
| --- | --- | --- |
| Environment file | `.env` (from `.env.example`) | `.env.prod` (from `.env.prod.example`) |
| Compose project | `ai_dev_project` (the checkout folder name) | `recipe-cost-calculator-prod` |
| Host port | `8000` | `8001` (`WEB_PORT`) |
| Database volume | `ai_dev_project_postgres_data` | `recipe-cost-calculator-prod_postgres_data` |
| Command prefix | `docker compose` | `docker compose --env-file .env.prod` |

The [quick start](#quick-start-for-local-evaluation) is not one of these
environments: `quickstart.env` is for local evaluation only, and dev and
production never read it.

Every `docker compose` command in this guide targets **dev** as written, except
in [Backup](#backup) and [Restore](#restore), which target production. To
run it against **production**, add `--env-file .env.prod` directly after
`docker compose` and use port `8001` in URLs:

```powershell
Copy-Item .env.prod.example .env.prod
docker compose --env-file .env.prod up --build --detach
docker compose --env-file .env.prod ps
(Invoke-WebRequest http://localhost:8001/health/).StatusCode
```

Both environments run the same `compose.yaml`; every difference between them
lives in `.env` and `.env.prod`. Only the Deploy workflow starts either one
(see [Releasing and rolling back](#releasing-and-rolling-back)), and it takes
`compose.yaml` from the commit that built the release being deployed.

Replace the placeholders in `.env.prod` before the first start, using values
generated for production only; never reuse the dev secret key or database
password. `.env.prod` is not committed. The two databases are separate: data
moves between environments only through the backup and restore procedures
below, and the restore safety check should be extended to compare
`COMPOSE_PROJECT_NAME` when both environments use the same database name.

## Releasing and rolling back

Every image is tagged with a release tag, `YYYYMMDD-HHMMSS-shortsha`, for
example `20261014-191754-9bdd779`. The part after the last `-` is the commit
that built it. A deployment always runs a release with the `compose.yaml` from
that commit, so code and settings never drift apart. There is only the `main`
branch; the old `prod` branch is not used to deploy.

**Find what each environment runs.** Read `APP_VERSION` from the running web
container (run each command from `DEPLOY_PATH`):

```powershell
docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' (docker compose --env-file .env ps -q web) | Select-String APP_VERSION
docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' (docker compose --env-file .env.prod ps -q web) | Select-String APP_VERSION
```

The first command is dev, the second production. The run summary of the
latest **Promote dev to production** run also shows the release and commit
promoted to production.

**Release to dev.** Push to `main`. **Build and push** first runs the CI
workflow ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)): its
`ci / tests` job runs `python -m pytest` against PostgreSQL 17 and its
`ci / integration` job runs `python -m pytest -m compose` and
`python -m pytest e2e`, both on GitHub-hosted runners. Only after both pass
does Build create the release tag, build and push the image on the self-hosted
runner, and deploy it to dev with the `compose.yaml` of the pushed commit. A
failing test stops the run before the build: no image is pushed and dev keeps
running its current release. The same CI workflow runs on every pull request,
so a change can be checked before it reaches `main`.

The build and dev deploy run only when the repository variable
`SELF_HOSTED_RUNNER` is `true` (**Settings -> Secrets and variables ->
Actions -> Variables**). Set it on the repository that has this host's
self-hosted runner. Unset or any other value, those jobs, and **Deploy
observability**, show as skipped and nothing waits for a runner; the tests
still run. The manual **Deploy** and **Promote dev to production** workflows
do not read the variable.

**Promote to production.**

1. Check dev (`http://localhost:8000/`) and confirm the release it runs, as above.
2. **Actions -> Promote dev to production -> Run workflow**.
3. Tick **confirm**. Leave **image_tag** empty to promote the release the dev
   container is running, or enter a release tag to promote that one.
4. Run it. The workflow retags that image `prod` (it never rebuilds) and
   deploys it to production. With the box unchecked, a tag missing from the
   registry, or no healthy dev container (when no tag is given), it fails and
   production is unchanged. Promoting the release already in production is safe.
5. Verify `http://localhost:8001/health/` returns `200` and that the production
   container's `APP_VERSION` equals the promoted release.

Start production only through **Deploy** or **Promote**. A manual
`docker compose --env-file .env.prod up -d` makes `APP_VERSION` read `latest`,
so the running release cannot be identified. If that happened, run **Deploy**
for `prod` with the release tag.

**Before rolling back.** From the repository checkout, with `<old-sha>` the
commit in the older release tag and `<current-sha>` the one in the running
release:

1. Take a production backup (see [Backup](#backup)).
2. Confirm both releases have the same migrations. This must print nothing;
   rolling back across a schema change is not supported:

   ```powershell
   git diff --stat <old-sha> <current-sha> -- '*migrations*'
   ```

3. Confirm the older release includes commit `9bdd779`. Only such releases can
   be deployed to production on this host: older ones publish `"8000:8000"` in
   their `compose.yaml` (no `WEB_PORT` or `DEPLOYMENT_ENVIRONMENT`), collide
   with dev on port `8000`, and the production web container fails with "port
   is already allocated". This must print `0`:

   ```powershell
   git merge-base --is-ancestor 9bdd779 <old-sha>; $LASTEXITCODE
   ```

**Roll back.** **Actions -> Deploy -> Run workflow**, choose environment
`prod` (or `dev`) and enter the older release tag as **image_tag**. The
workflow checks out that release's commit, deploys the image with that commit's
`compose.yaml`, and prints the release tag and commit. Then verify `APP_VERSION`
as above. Only release tags are accepted; `dev`, `prod`, `latest` or a typo
fail before any container changes. If the Deploy fails, run **Deploy** again
with the previous release tag to restore production. Roll forward the same way
with the newer release tag. Do not restore the database just to roll back
code; see [Update and rollback](#update-and-rollback) for schema concerns.

## Observability stack

The OpenTelemetry Collector, Prometheus, Loki, Tempo and Grafana run as their
own Compose project, `observability`, from
[`observability/compose.yaml`](../observability/compose.yaml). It shares no
services, volumes or networks with the application's `compose.yaml`; dev and
production reach the collector only through
`OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318` in `.env` and
`.env.prod`. Full details are in the
[observability guide](../observability/README.md).

**One-time setup (operator).**

1. Choose a fixed folder outside the runner's work directory (never under
   `actions-runner/_work`, which the runner cleans), for example
   `C:\Users\<you>\observability`.
2. Create the repository variable `OBSERVABILITY_PATH` with that path:
   **Settings -> Secrets and variables -> Actions -> Variables**.
3. Create the Grafana env file there from the committed example and replace the
   placeholder password (never commit or print it):

   ```powershell
   New-Item -ItemType Directory -Force C:\Users\<you>\observability
   Copy-Item observability\env.example C:\Users\<you>\observability\.env
   ```

   It sets `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD`. Keep the user
   name `admin` on an existing Grafana volume; the user name only applies to a
   new one.
   If the password contains `$`, write each `$` as `$$` or wrap the whole value
   in single quotes; an unquoted value must not contain ` #`. Compose would
   otherwise change the value, and the workflow refuses it.

**Deploy or update.** **Actions -> Deploy observability -> Run workflow**. It
also runs on a push to `main` that changes `observability/`. Either way its
job runs only when the repository variable `SELF_HOSTED_RUNNER` is `true`;
otherwise it shows as skipped (see
[Releasing and rolling back](#releasing-and-rolling-back)). It copies the
stack's files from that commit to `OBSERVABILITY_PATH`, runs
`docker compose --project-name observability up -d` there (reusing the existing
volumes), restarts only services whose config file changed, and is green only
when Prometheus, Loki, Tempo, Grafana and the collector are all ready; otherwise
it names the service that is not. If the variable, `.env` or the password is
missing, or the password is `admin`, it fails before changing any container.
Running it again with no changes recreates nothing.

**Change the Grafana password.** Edit `GRAFANA_ADMIN_PASSWORD` in `.env` in the
deploy folder and run **Deploy observability**; it applies the password to the
existing Grafana volume with
`grafana cli admin reset-admin-password --password-from-stdin`. Anonymous
access and sign-up stay disabled.

**Start and stop by hand** (from the deploy folder, where `compose.yaml` and
`.env` are):

```powershell
Set-Location C:\Users\<you>\observability
docker compose up -d
docker compose ps
docker compose down
```

`docker compose down` keeps the stored data; never add `-v` unless you mean to
delete it. Stopping the stack never affects the application: dev (`:8000`) and
production (`:8001`) keep answering `/health/` and serving recipes, their logs
may show telemetry export errors, and telemetry resumes within about two
minutes of `docker compose up -d` without restarting them.

## Database migrations

The web entrypoint applies migrations before Gunicorn accepts traffic. Inspect
the current state at any time:

```powershell
docker compose exec -T web python manage.py showmigrations
```

An `[X]` marks an applied migration. To apply pending migrations deliberately
(for example during a supervised update), first take a backup, then run:

```powershell
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py showmigrations
docker compose exec -T web python manage.py check
(Invoke-WebRequest http://localhost:8000/health/).StatusCode
```

If a migration fails, do not repeatedly restart or manually edit production
tables. Capture the error, inspect both services' logs, and verify the active
application image and migration state:

```powershell
docker compose logs --tail 200 web db
docker compose exec -T web python manage.py showmigrations
```

Correct the incompatible application or migration, test it outside production,
then restore the pre-migration backup if recovery requires replacing database
state. PostgreSQL migrations are normally transactional, but the backup is the
recovery point for any migration that changes persistent data.

## Backup

The following commands create a timestamped plain-SQL PostgreSQL dump in the
`backups` directory of the current folder, **outside** the database container.
They are an **environment-specific example** and assume a healthy, running
Compose deployment and sufficient local disk space. The temporary `/tmp` file
is only a transfer source and is removed afterward.

The `--env-file` selects the environment that is backed up. Run the commands
from the `DEPLOY_PATH` folder. As written they back up **production**
(`--env-file .env.prod`); for dev, use `--env-file .env` on every
`docker compose` call. Without `--env-file`, Compose reads `.env` and backs up
dev.

```powershell
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$database = (docker compose --env-file .env.prod exec -T db printenv POSTGRES_DB).Trim()
New-Item -ItemType Directory -Force backups | Out-Null
docker compose --env-file .env.prod exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges --file /tmp/operator-backup.sql'
docker compose --env-file .env.prod cp db:/tmp/operator-backup.sql "backups/$database-$timestamp.sql"
docker compose --env-file .env.prod exec -T db rm /tmp/operator-backup.sql
Get-Item "backups/$database-$timestamp.sql"
```

The dump contains the selected `POSTGRES_DB` database's schema and application
data at backup time, including Django tables, migration history, ingredients,
recipes, and recipe-ingredient rows. It does not contain PostgreSQL server
roles, Docker images, the named volume itself, or files outside that database.
Store the resulting `.sql` file securely and separately from the host.

## Restore

**Destructive: restoration replaces the current state of the target database.**
Take a fresh backup first and stop if the target is not exactly the intended
database. The commands below are an **environment-specific example**; replace
the backup filename and `recipe_cost_calculator` with the expected production
database name before running them.

As in [Backup](#backup), the `--env-file` selects the target environment. Run
the commands from the `DEPLOY_PATH` folder. As written they restore
**production** (`--env-file .env.prod`, port `8001`); for dev, use
`--env-file .env` on every `docker compose` call and port `8000`.

```powershell
$backup = 'backups/recipe_cost_calculator-20260908-120000.sql'
$expectedDatabase = 'recipe_cost_calculator'
$database = (docker compose --env-file .env.prod exec -T db printenv POSTGRES_DB).Trim()
$databaseUser = (docker compose --env-file .env.prod exec -T db printenv POSTGRES_USER).Trim()
if ($database -ne $expectedDatabase) { throw "Refusing restore: Compose target is '$database', expected '$expectedDatabase'." }
docker compose --env-file .env.prod exec -T db psql -U $databaseUser -d $database -c '\conninfo'
Get-Item $backup
```

The `\conninfo` output must identify the expected `$database`; `Get-Item` must
identify the backup you intend to load. Back up the current database using the
previous section before proceeding. With the target verified, load the dump:

```powershell
docker compose --env-file .env.prod cp $backup db:/tmp/operator-restore.sql
docker compose --env-file .env.prod exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/operator-restore.sql'
docker compose --env-file .env.prod exec -T db rm /tmp/operator-restore.sql
docker compose --env-file .env.prod exec -T web python manage.py showmigrations
docker compose --env-file .env.prod exec -T web python manage.py check
(Invoke-WebRequest http://localhost:8001/health/).StatusCode
```

The final command must output `200`; inspect the restored application records
through the web UI as an additional business-data check. If `psql` fails, do
not claim the restore succeeded: retain the current logs and repeat only after
fixing the dump or target selection.

## Update and rollback

This is an **environment-specific example**. It assumes the working tree is a
deployment checkout with a known prior Git revision and that the new revision
has already passed the complete test suite in a safe environment.

1. Record the current revision and take a backup before applying migrations:

   ```powershell
   git rev-parse HEAD
   git fetch --all --tags
   git status
   ```

   Run the backup procedure above and retain the resulting file before the
   next step.

2. Obtain the intended new application version, rebuild, start it, and apply
   any migration deliberately:

   ```powershell
   git pull --ff-only
   docker compose up --build --detach
   docker compose exec -T web python manage.py migrate --noinput
   docker compose exec -T web python manage.py showmigrations
   (Invoke-WebRequest http://localhost:8000/health/).StatusCode
   docker compose ps
   ```

   Require `200` and healthy `web` and `db` services before declaring success.

3. If health verification fails, collect logs, then roll the application back
   to the revision recorded in step 1. **Do not restore the database merely to
   roll back application code**; use the backup only when the migration itself
   must be reverted by replacing data. **Rollback safety gate:** retain the
   pre-update backup and verify the exact Compose database before changing
   either application code or database state:

   ```powershell
   $expectedDatabase = 'recipe_cost_calculator'
   $database = (docker compose exec -T db printenv POSTGRES_DB).Trim()
   if ($database -ne $expectedDatabase) { throw "Refusing rollback: Compose target is '$database', expected '$expectedDatabase'." }
   docker compose logs --tail 200 web db
   git checkout <previous-commit-id>
   docker compose up --build --detach
   (Invoke-WebRequest http://localhost:8000/health/).StatusCode
   ```

   The checkout command is destructive to uncommitted deployment changes;
   confirm `git status` is clean first. If the prior application version cannot
   read the migrated schema, stop it, explicitly verify the database target,
   restore the pre-update backup using the destructive restore procedure, then
   rebuild and health-check the prior revision.

## Dependency updates

Application dependencies are declared only in `requirements.txt`. Update that
file in a tested change, rebuild the image, and run the complete test suite
before deployment:

```powershell
python -m pip install -r requirements.txt
python -m pytest
docker compose build web
```

The first two commands are **environment-specific examples**: they assume an
activated Python 3.13 virtual environment and the database configuration
required by the test suite. The image rebuild validates that the container uses
the same `requirements.txt`; deploy it through the update procedure only after
the full suite passes. The CI workflow runs the same install and the whole
suite, against PostgreSQL, on every pull request and before every build from
`main`; the README's
[Running the CI checks locally](../README.md#running-the-ci-checks-locally)
shows how to point `python -m pytest` at a PostgreSQL database.

## Troubleshooting

| Symptom | Checks and safe first response |
| --- | --- |
| `db` is unhealthy | Run `docker compose ps` and `docker compose logs --tail 200 db`. Confirm `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` are present in `.env`; do not delete `postgres_data` to hide an initialization failure. |
| `web` is unhealthy or exits | Run `docker compose logs --tail 200 web db`. Check required Django variables, migration errors, and that `db` is healthy before restarting with `docker compose up --build --detach`. |
| Database connection refused or `OperationalError` | From `web`, PostgreSQL must be `db:5432`, never a Docker IP or `localhost`. Check `docker compose exec -T web python manage.py check`, then `docker compose ps` and the `db` logs. |
| Migration fails | Follow [Database migrations](#database-migrations): preserve logs, inspect `showmigrations`, correct and test the cause, then use a verified backup only if database recovery is required. |
| Static CSS is missing | Run `docker compose logs --tail 200 web`, rebuild with `docker compose up --build --detach`, then request `http://localhost:8000/static/calculator/site.css`. The web entrypoint runs `collectstatic`. |
| Host port `8000` is occupied | Identify and stop the other local process, or change the left side of `8000:8000` in `compose.yaml` and use that port in `DJANGO_CSRF_TRUSTED_ORIGINS` and all health URLs. Rebuild and verify health afterward. |
| Need live logs | `docker compose logs --follow web db`; press `Ctrl+C` only to stop log streaming. |

The authoritative deployment files are [`.env.example`](../.env.example),
[`compose.yaml`](../compose.yaml), [`Dockerfile`](../Dockerfile),
[`docker-entrypoint.sh`](../docker-entrypoint.sh), and
[`requirements.txt`](../requirements.txt). Application settings are in
[`config/settings.py`](../config/settings.py), and the health route is in
[`config/urls.py`](../config/urls.py).
