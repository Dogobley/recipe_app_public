# Issue 22: Make business metrics reach Grafana with correct environment and version labels

Status: closed

## Goal

The business-metrics dashboard from [Issue 21](issue21.md) shows live data for every deployment, and its environment and version filters tell dev from prod and one release from another.

Today the dashboard is empty, and these are the causes:

- Production has no `OTEL_EXPORTER_OTLP_ENDPOINT`, so metrics go to the container logs instead of the collector.
- Every deployment reports `deployment_environment="production"`, because `compose.yaml` hard-codes `DJANGO_ENV: production`.
- `service_version` is the mutable `dev`/`prod`/`latest` image tag rather than the release tag the build computes.

## Acceptance criteria

Data reaches Grafana:

- [ ] After a prod deploy, `docker inspect` on the prod web container shows `OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318` and `OTEL_PYTHON_DJANGO_EXCLUDED_URLS=health/`.
- [ ] Within two minutes of creating and viewing a recipe on prod, the panels in all three rows of <http://localhost:3000/d/recipe-business-metrics> (Recipes created, Recipe views, Average recipe cost) show data.
- [ ] Prod health-check requests do not appear as traces in Grafana → Explore → Tempo.

The environment filter tells deployments apart:

- [ ] A prod deployment reports `deployment_environment="prod"` and a dev deployment reports `"dev"`. Both values appear in the dashboard's Environment dropdown once each has served traffic.
- [ ] Selecting only `prod` shows no dev data, and the reverse.
- [ ] `DJANGO_ENV` is still `production` in both containers, so production settings (DEBUG off, required secrets) stay enforced.
- [ ] A deployment whose env file does not set `DEPLOYMENT_ENVIRONMENT` reports `production`, so nothing breaks for an operator who has not updated their env file.

The version filter shows real releases:

- [ ] An image built by `.github/workflows/build.yml` reports its build tag (format `YYYYMMDD-HHMMSS-shortsha`) as `service_version`. The dev deploy, its promotion to prod, and any later redeploy of the `dev` or `prod` tag all keep reporting it.
- [ ] After promotion, the Version dropdown shows the same release tag under both `dev` and `prod`.
- [ ] A local `docker compose up --build` without `IMAGE_TAG` reports `latest`, and a plain `docker build .` reports `unknown`. Neither shows an empty version.

Dev and prod can run side by side:

- [ ] With both deployments running, dev answers on `http://localhost:8000/health/` and prod on `http://localhost:8001/health/`, without a port conflict.

Dashboard filter edge case:

- [ ] With "All" selected, the cost panels never show an entry with a blank environment or version, even if Prometheus still holds an older series without those labels.

Docs and tests:

- [ ] `.env.example` and `docs/operator-guide.md` show `http://host.docker.internal:4318` as the endpoint example, and document `DEPLOYMENT_ENVIRONMENT` and `WEB_PORT`.
- [ ] `docs/operator-guide.md` describes `APP_VERSION` as set at build time from the build tag.
- [ ] `README.md` states that prod deploys use the `compose.yaml` on the `prod` branch, so these changes reach prod only after `main` is merged into `prod`.
- [ ] `python -m pytest` and `python -m pytest -m compose` pass.

## Out of scope

- Warning at startup when production telemetry has no OTLP endpoint (the silent console fallback is why this went unnoticed) - moved to [Issue 23](issue23.md).
- Merging `main` into `prod` and running the production deploy. This is an operator action after QA passes, not part of the implementation.
- Removing old `production`/`latest` series from Prometheus. They age out of the dashboard's time range and the stricter "All" value keeps unlabelled ones off the cost panels.
- Alerting rules.

## Constraints

- Follow the step-by-step plan at `<local plan file>`.
- Expected files to change:
  - `compose.yaml`, `Dockerfile` and `.github/workflows/build.yml`
  - `observability/grafana/provisioning/dashboards/recipe-business-metrics.json`
  - `.env.example`, `docs/operator-guide.md`, `README.md` and `observability/README.md`
  - tests under `tests/`
- Do not change `config/telemetry.py` or `config/settings.py`. Telemetry already prefers `DEPLOYMENT_ENVIRONMENT` over `DJANGO_ENV`, and settings must keep reading `DJANGO_ENV`.
- The env files `.env`, `.env.prod`, `deploy/.env` and `deploy/.env.prod` are gitignored and hold secrets.
  - Change them only by adding or replacing single variable lines.
  - Never print or commit them.
- Set the version label inside the image at build time (`ARG`/`ENV APP_VERSION`), not at deploy time, so promoting retags without changing what the image reports.
- Dashboard variables use `allValue: ".+"`.
- Read `_docs/testing-guidelines.md` before writing tests and follow the text-inspection style of `tests/test_production_deployment.py` for compose, Dockerfile and workflow checks.
- Do not add dependencies.
- Do not commit or push unless the user asks.

## Engineer comment

Implemented per the plan; issue left open for QA, nothing committed.

What changed:
- `compose.yaml`: web gets `DEPLOYMENT_ENVIRONMENT: ${DEPLOYMENT_ENVIRONMENT:-production}` (`DJANGO_ENV` unchanged); runtime `APP_VERSION` removed; `build` now passes `APP_VERSION: "${IMAGE_TAG:-latest}"` as a build arg; ports are `"${WEB_PORT:-8000}:8000"`.
- `Dockerfile`: `ARG APP_VERSION=unknown` + `ENV APP_VERSION=$APP_VERSION` (before `USER app`).
- `.github/workflows/build.yml`: `docker build --build-arg "APP_VERSION=${tag}" ...`.
- Dashboard JSON: both variables `allValue: ".+"`; `tests/test_grafana_dashboard.py` updated.
- `tests/compose/conftest.py`: `WEB_PORT` and `DEPLOYMENT_ENVIRONMENT` added to the dropped shell vars.
- Docs: `.env.example`, `docs/operator-guide.md` (endpoint example, `DEPLOYMENT_ENVIRONMENT`, `WEB_PORT`, `APP_VERSION` baked at build time), `README.md` (prod uses the `prod` branch's `compose.yaml`; reaches prod only after `main` is merged into `prod`), `observability/README.md` (`dev`/`prod` values, `allValue`).
- Local gitignored env files (single-line set/append only, not printed): `.env.prod` and `deploy/.env.prod` got `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_PYTHON_DJANGO_EXCLUDED_URLS=health/`, `DEPLOYMENT_ENVIRONMENT=prod`; `.env` and `deploy/.env` got `DEPLOYMENT_ENVIRONMENT=dev`. `deploy/compose.yaml` was not touched (the deploy workflow copies it).
- New tests in `tests/test_production_deployment.py` (text inspection): compose env/port/build-arg, Dockerfile ARG/ENV, workflow build-arg, docs/.env.example content.

Test results (using `.venv/Scripts/python`; the bare system `python` lacks opentelemetry):
- `python -m pytest`: 303 passed, 23 deselected.
- `python -m pytest -m compose`: 23 passed (Docker was available).

Not verified (needs a live deploy / merge to `prod`, out of scope here): the `docker inspect` of the prod container, data appearing in all three Grafana rows, absence of health traces in Tempo, `prod`/`dev` appearing in the dropdowns, the same release tag under both environments after promotion, and dev (8000) and prod (8001) running side by side. The "All" blank-label criterion is covered only by the `allValue` test, not by a live Prometheus query. `latest`/`unknown` fallbacks follow from the Compose/Dockerfile defaults but were not checked by running an image.

## QA: PASS

Data reaches Grafana:

- [ ] Prod container shows `OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318` and `OTEL_PYTHON_DJANGO_EXCLUDED_URLS=health/` - NOT VERIFIABLE (live). `compose.yaml` passes both through from the env file, and the gitignored prod env files define both variable names (values not printed). Would pass once `main` is merged into `prod` and deployed.
- [ ] Panels in all three rows show data within two minutes - NOT VERIFIABLE (live). The endpoint wiring is in place and the dashboard queries filter on `deployment_environment` / `service_version`.
- [ ] Prod health checks do not appear as traces in Tempo - NOT VERIFIABLE (live). `OTEL_PYTHON_DJANGO_EXCLUDED_URLS` is passed through and set to `health/` in the prod env files.

The environment filter tells deployments apart:

- [x] Prod reports `deployment_environment="prod"`, dev reports `"dev"` - PASS (config). `docker compose config` with `DEPLOYMENT_ENVIRONMENT=prod` gives `DEPLOYMENT_ENVIRONMENT: prod`; `config/telemetry.py` reads that variable before `DJANGO_ENV`. The dev env files set `dev` and the prod ones set `prod`. The dropdown showing both is not verifiable live.
- [x] Selecting only `prod` shows no dev data, and the reverse - PASS (config). All dashboard queries filter with `deployment_environment=~"$environment"`. Not run against live Grafana.
- [x] `DJANGO_ENV` is still `production` in both containers - PASS. `docker compose config` shows `DJANGO_ENV: production` with `DEPLOYMENT_ENVIRONMENT` set to either value, and `config/settings.py` is unchanged.
- [x] Unset `DEPLOYMENT_ENVIRONMENT` reports `production` - PASS. `docker compose config` with the variable unset gives `DEPLOYMENT_ENVIRONMENT: production`.

The version filter shows real releases:

- [x] An image built by `build.yml` reports its build tag as `service_version` - PASS. The workflow passes `--build-arg "APP_VERSION=${tag}"` and the Dockerfile has `ARG`/`ENV APP_VERSION`. I built an image with `--build-arg APP_VERSION=20261014-000000-abc1234`; `printenv APP_VERSION` returned that tag, including when the container started with an extra `-e` variable. `compose.yaml` no longer sets `APP_VERSION` at runtime, so a retag or redeploy of the `dev`/`prod` tag keeps the baked value. The first `compose.yaml` build-arg site is also covered by the new test.
- [x] After promotion the same release tag appears under both `dev` and `prod` - PASS (by design). The value is baked into the image, and promotion only retags it. The dropdown is not verifiable live.
- [x] Local `docker compose up --build` without `IMAGE_TAG` reports `latest`, and a plain `docker build .` reports `unknown` - PASS. `docker compose config` gives `APP_VERSION: latest` for the build arg, and a plain `docker build .` image returns `unknown` from `printenv APP_VERSION`.

Dev and prod can run side by side:

- [x] Dev on 8000, prod on 8001, without a port conflict - PASS (config). `compose.yaml` uses `"${WEB_PORT:-8000}:8000"`, and `docker compose config` shows `published: "8001"` with `WEB_PORT=8001`. `WEB_PORT` is defined in `.env.prod` and `deploy/.env.prod` but not in the dev files, so dev stays on 8000. Both running at once was not exercised live.

Dashboard filter edge case:

- [x] "All" never shows a blank environment or version - PASS (config). Both variables have `allValue: ".+"`, and `tests/test_grafana_dashboard.py` asserts it. The `.+` regex does not match an empty label. Not checked against a live Prometheus series.

Docs and tests:

- [x] `.env.example` and `docs/operator-guide.md` show `http://host.docker.internal:4318` and document `DEPLOYMENT_ENVIRONMENT` and `WEB_PORT` - PASS
- [x] `docs/operator-guide.md` describes `APP_VERSION` as set at build time from the build tag - PASS
- [x] `README.md` says prod deploys use the `compose.yaml` on the `prod` branch, so changes reach prod only after `main` is merged into `prod` - PASS
- [x] `python -m pytest` and `python -m pytest -m compose` pass - PASS

Tests:

- `.venv/Scripts/python -m pytest -q`: 303 passed, 23 deselected, 0 failed
- `.venv/Scripts/python -m pytest -m compose -q`: 23 passed, 303 deselected, 0 failed
- Manual: `docker compose config` for default, prod and tagged settings; two `docker build` runs (default and with `APP_VERSION`) checked with `printenv`.

Gaps and notes:

- The new tests inspect text only. No test builds an image and checks `APP_VERSION`; I did that by hand.
- The live criteria need the operator to merge `main` into `prod` and deploy. Re-check them after that deploy.
- Nothing in the code was changed.

## Live check from Issue 25 (2026-10-15)

Production criteria checked live in [Issue 25](issue25.md), release `20261015-020111-c28a8f3`:

- Prod web env (`docker inspect`): `DEPLOYMENT_ENVIRONMENT=prod`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318`, `OTEL_PYTHON_DJANGO_EXCLUDED_URLS=health/`, `DJANGO_ENV=production` - PASS
- No "Telemetry is going to the console only" warning in prod logs - PASS
- Prometheus lists `prod` in `deployment_environment`, with prod recipe views and average cost under the release tag - PASS
- Prod and dev series stay separate per environment and version - PASS
- No prod health-check traces in Tempo - PASS
