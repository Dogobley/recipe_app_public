# Issue 25: Verify the release flow and production telemetry live, after the first issue-24 promotion

Status: closed (2026-10-15)

## Goal

The first real run of the new release flow from [Issue 24](issue24.md) is checked end to end on this machine. Production exports telemetry labelled `prod`, which settles the production criteria of [Issue 22](issue22.md).

Issues 22 and 24 were closed after checks that only read configuration and workflow text; nothing ran against GitHub Actions or the deployed containers.

Issue 24 replaced the original plan for this issue, a one-time merge of `main` into the `prod` branch. Deploy now checks out the commit named in the release tag, so production no longer reads `compose.yaml` from the `prod` branch.

## Acceptance criteria

Dev deploy (push to `main`):

- [x] Pushing the issue 24 commit to `main` starts **Build and push**. It finishes green and deploys dev.
- [x] The Deploy run log and summary for dev print a release tag (`YYYYMMDD-HHMMSS-shortsha`) and the full commit it checked out. The short SHA in the tag matches the start of that commit.
- [x] The dev web container reports that release tag in `APP_VERSION` and answers on `http://localhost:8000/health/` with 200.

Promotion guards (each run must leave prod unchanged; compare the prod container ID before and after):

- [x] **Promote dev to production** with the confirm box unticked fails at "Require confirmation".
- [x] **Deploy** run by hand with image tag `prod` fails before any container changes, with the "release tag is required" message.

Promotion:

- [x] **Promote** with confirm ticked and no tag finishes green. Its summary names the release tag the dev container reports and its commit.
- [x] The prod Deploy run log prints the same release tag and commit.
- [x] The prod web container reports that release in `APP_VERSION`, and answers on `http://localhost:8001/health/` with 200 while dev still answers on 8000.
- [x] The recipes listed on `http://localhost:8001/recipes/` are the same before and after the promotion.

Production telemetry (closes Issue 22's production criteria):

- [x] `docker inspect` on the prod web container shows:
  - `DEPLOYMENT_ENVIRONMENT=prod`
  - `OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318`
  - `OTEL_PYTHON_DJANGO_EXCLUDED_URLS=health/`
  - `DJANGO_ENV=production`
- [x] The prod web logs (`docker compose --env-file .env.prod logs web`, run from `deploy/`) contain no "Telemetry is going to the console only" warning.
- [x] Within two minutes of viewing a recipe on prod, the dashboard (<http://localhost:3000/d/recipe-business-metrics>) lists `prod` in the Environment dropdown. Selecting only `prod` shows data in the Recipe views and Average recipe cost rows, under the promoted release tag.
- [x] After promotion, the Version dropdown shows the same release tag under both `dev` and `prod`.
- [x] Selecting only `prod` shows no dev data, and the reverse.
- [x] With both environments selected, the cost panels show two entries, one per environment and version, with no blank entry.
- [x] Prod health-check requests do not appear as traces in Grafana → Explore → Tempo. Allow about five minutes for Tempo to make new traces searchable, or flush it first.

Records:

- [x] Issue 22 and Issue 24 each get a note listing which of their criteria this run checked live, and the result of each.

## Out of scope

- Rollback to an older release (an Issue 24 criterion) is not exercised here, to avoid an extra production change. It is moved to [Issue 26](issue26.md).
- Deleting the `prod` branch stays an operator decision after this issue passes (see the constraints in Issue 24).

## Constraints

- No code changes. If a check fails, record the failure and the evidence, and file or reopen the owning issue: 24 for workflows, 22 for telemetry.
- These are operator actions, and each needs the user's approval:
  - committing and pushing to `main`
  - running Promote
  - running the failing Deploy check
- Never print `deploy/.env` or `deploy/.env.prod`. Check variables through `docker inspect` on the containers.
- Generate traffic only with read-only requests (page views and health checks). Do not create or delete prod data.
- Record evidence for each criterion: workflow run URLs or IDs, command output, and the Prometheus queries used.

## Engineer comment (local prod-sync merge)

Status stays open. Done locally only; nothing pushed, no workflow run, no `deploy/` files touched.

- `git fetch`; local branch `prod-sync` created from `origin/prod` in a separate worktree (scratchpad `prod-sync`), so the main worktree and its uncommitted issue 24 changes are untouched.
- Merged `origin/main` (9bdd779 is an ancestor of the result). Conflicts: `compose.yaml` and `README.md` resolved to main's version; `promote-to-production.yml` (deleted on prod, modified on main) kept as main's; `.gitignore` taken from main (removes a duplicated `.env.prod` line). `compose.yaml` is identical to `origin/main`.
- `.env.prod.example` on prod lacked the telemetry variables; added `DEPLOYMENT_ENVIRONMENT=prod`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318`, `OTEL_PYTHON_DJANGO_EXCLUDED_URLS=health/`.
- Note: the issue's Goal says the merge plan was replaced by issue 24 (deploy checks out the release commit). This merge follows the caller's explicit instruction and is optional for the checks above.

Gap: issue 24's workflow changes, `.env.prod.example` changes and the operator guide "Releasing and rolling back" section exist only as uncommitted changes on `main`, so they are not in `prod-sync`. They reach production only after being committed to `main`.

Operator action needed: review and commit issue 24 work on main; push; decide whether to push `prod-sync` to `prod` at all; run the live checks (dev deploy, guards, Promote, telemetry, Grafana) and record evidence.

## Live run 1 (2026-10-14): Promote failed, Issue 24 reopened

- Dev deploy: dev web container `deploy-web-1` healthy, reporting `APP_VERSION=20261014-214154-5e6e01d` (commit `5e6e01d`). The Deploy run log and summary criteria have not been recorded yet.
- **Promote** with confirm ticked and no tag: **FAIL** at "Resolve the release to promote", with "The dev web container is not running…", although that container was running and healthy. Production was unchanged: the prod web container's start time was still 2026-10-14T19:53:34Z.
- Cause: a PowerShell 5.1 pipeline bug in the workflow (`Select-Object -First 1` kills `docker compose`, so `$LASTEXITCODE` is `-1`). Details and the reproduction are in [Issue 24](issue24.md) under "Reopened: Promote cannot find the dev container".
- Issue 24 is reopened. The remaining criteria here wait for that fix. The promotion guards have not been run yet.

## Live run 2 (2026-10-15): Promote passed; remaining checks pending

Checked by the orchestrator. Prod reads (`docker inspect` on the prod container, `curl` to `:8001`, prod logs) were blocked by the session's permission rules, so those criteria still need the operator.

- Dev deploy: after pushing `66d0c23`, dev web reports `APP_VERSION=20261015-011621-66d0c23` and `http://localhost:8000/health/` returns 200. (Deploy run log and summary not recorded.)
- Promote, confirm ticked, no tag: **green** (user report). `docker ps`: prod web `ba166a43924f` healthy on image tag `20261015-011621-66d0c23`, the dev release. Prod db container not restarted.
- Promotion guards (confirm unticked; Deploy with tag `prod`): **not run yet**. Baseline prod web container ID for that check: `ba166a43924f`.
- Telemetry:
  - `GET /api/v1/label/deployment_environment/values` returns `["dev","prod"]`.
  - `count by (deployment_environment, service_version) (target_info)`: `dev` and `prod` both under `20261015-011621-66d0c23`, so the Version variable shows the same tag under both environments.
  - `max by (deployment_environment, service_version) (recipes_average_cost)`: one `prod` / `20261015-011621-66d0c23` series.
  - Recipe views on prod: no data yet (no prod recipe has been viewed since the promotion).
  - Tempo (`{ resource.deployment.environment = "prod" }`, last hour): 0 prod traces, including none for health checks. Not conclusive until a prod page view produces a trace.
  - An extra series with no `deployment_environment`/`service_version` labels exists in `target_info` (the legacy unlabeled series noted in Issue 21's QA).
- Still open: guards, prod `APP_VERSION`/health on 8001, recipe list before/after, `docker inspect` env vars, prod log warning, a prod recipe view for the dashboard and Tempo checks, the env-separation and two-entry cost checks after that, and the notes on Issues 22 and 24.

## Live run 3 (2026-10-15): PASS

Prod reads were run by the user and pasted into the session; the orchestrator ran the Prometheus and Tempo queries. Release under test: `20261015-020111-c28a8f3` (commit `c28a8f3f5706f36c23f8628d28d2f9c4db327860`).

Dev deploy:
- Dev web `deploy-web-1` runs image `localhost:5000/recipe_app:20261015-020111-c28a8f3`, healthy; `http://localhost:8000/health/` 200. The tag's short SHA `c28a8f3` is the start of the commit printed by Deploy.

Promotion guards:
- Promote with confirm unticked: failed (user report). Prod unchanged.
- Deploy by hand, `environment=prod`, `image_tag=prod`: failed with the release-tag error (user report). The prod web container was `521e7ba8177d` before and after (`docker ps`, "Up 16 minutes" at the check).

Promotion:
- Promote, confirm ticked, no tag: green. The run (in the private repository) was the first promotion (`66d0c23`); the user then pushed and promoted again. That run's summary: "Deploying release `20261015-020111-c28a8f3` (commit `c28a8f3f5706f36c23f8628d28d2f9c4db327860`) to prod." The prod Deploy log prints the same tag and commit.
- Prod web `APP_VERSION=20261015-020111-c28a8f3` (`docker inspect`, user); `http://localhost:8001/health/` 200 while dev answers on 8000.
- Recipes on `http://localhost:8001/recipes/` are the same before and after the promotion (user check; no saved snapshot).

Production telemetry:
- `docker inspect` on the prod web container: `DEPLOYMENT_ENVIRONMENT=prod`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318`, `OTEL_PYTHON_DJANGO_EXCLUDED_URLS=health/`, `DJANGO_ENV=production`.
- Prod web logs (`docker compose --env-file .env.prod logs web`) contain no "Telemetry is going to the console only" line.
- `GET /api/v1/label/deployment_environment/values` returns `["dev","prod"]`. After a prod recipe view, `sum by (deployment_environment, service_version) (recipe_views_total{deployment_environment=~"dev|prod", service_version=~"20261015-020111-c28a8f3"})` gives dev 1 and prod 5; `max by (...) (recipes_average_cost{...})` gives dev 12750 and prod 58045.91.
- Version variable query (`label_values(..., service_version)` scoped by environment): `dev` and `prod` each list `20261015-020111-c28a8f3`.
- Separation: the panel selectors with `deployment_environment=~"prod"` return only prod series, and with `"dev"` only dev series.
- Both environments selected: the cost expression returns exactly two series, `dev / 20261015-020111-c28a8f3` and `prod / 20261015-020111-c28a8f3`, none with blank labels.
- Tempo, `{ resource.deployment.environment = "prod" }` over the last hour: traces for `GET home`, `GET recipes/`, `GET recipes/<int:pk>/`, static files and one `GET` (`/favicon.ico`, 404). Searches for prod spans whose `http.target`, `http.route` or `url.path` contain `health` return 0 traces.

Finding (operator practice, not a criterion failure): between the two promotions the user ran `docker compose --env-file .env.prod up -d` by hand in `deploy/`. That bypasses the release flow and takes `IMAGE_TAG` from the env file, so prod briefly reported `APP_VERSION=latest` and its metrics carried `service_version=latest`. Use Deploy or Promote for prod. Those `latest` series show in the Version dropdown until they age out of the dashboard range.

Records: notes added to Issue 22 and Issue 24.

## Closed by orchestrator

All criteria checked live and passed.

