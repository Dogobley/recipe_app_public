# Issue 31: Run the tests in CI on every pull request and gate deployments on them

Status: closed (2026-10-22)

## Goal

Every pull request and every push to `main` runs the whole automated test suite
on a GitHub-hosted runner against PostgreSQL, so the result is visible on
GitHub without any machine of ours. A push to `main` builds and deploys to dev
on the self-hosted runner only after the tests pass, and only on a repository
that has opted in to a self-hosted runner. Elsewhere, such as this public
repository, the self-hosted jobs are skipped instead of waiting for a runner
forever.

## Acceptance criteria

Test workflow:

- [x] A new workflow, `.github/workflows/ci.yml`, named **CI**, runs on every
      `pull_request` and can be called from other workflows (`workflow_call`) and
      run by hand (`workflow_dispatch`).
- [x] Its jobs run on `ubuntu-latest` (GitHub-hosted), use Python 3.13 and
      install dependencies only from `requirements.txt`.
- [x] A **tests** job runs `python -m pytest` with a PostgreSQL 17 service
      container as the test database. The run proves it used PostgreSQL, for
      example through a test or a step that fails if the database vendor is not
      `postgresql`.
- [x] An **integration** job runs `python -m pytest -m compose` and then
      `python -m pytest e2e`, after installing Chromium with
      `python -m playwright install --with-deps chromium`. It needs no secret or
      repository variable.
- [x] A failing test, a failed install, or a failed service start makes the
      workflow fail.
- [x] The workflow needs no secrets and grants only `contents: read`.

Gating deployments on tests:

- [x] On every push to `main`, the tests in `ci.yml` run once (they are not
      started twice for the same push), and the build and dev deploy start only
      after they pass.
- [x] A failing test on `main` prevents the image build and the dev deploy.

Self-hosted jobs on repositories without a runner:

- [x] The automatically triggered self-hosted jobs (the build and dev deploy in
      `build.yml`, and the deploy in `deploy-observability.yml`) run only when
      the repository variable `SELF_HOSTED_RUNNER` is `true`. When it is unset
      or anything else, those jobs show as skipped and nothing waits for a
      runner. The tests still run.
- [x] When `SELF_HOSTED_RUNNER` is `true`, a push to `main` still builds,
      tags, pushes and deploys to dev exactly as before. The manual Deploy and
      Promote dev to production workflows are unchanged.

Pre-existing failure:

- [x] `tests/test_production_deployment.py::test_collected_static_asset_is_served_by_the_application`
      passes on a clean checkout and in the full suite. Today it fails unless
      `staticfiles/` already exists, because `config/urls.py` binds
      `STATIC_ROOT` when it is imported, so the test's settings override never
      reaches the static view. Static files are still served from
      `STATIC_ROOT` in the container.

Documentation:

- [x] The README's CI/CD section describes the CI workflow, what each job runs,
      where to see the result on a pull request, that deployments wait for the
      tests, and the `SELF_HOSTED_RUNNER` variable (added to the "Required
      repository configuration" table).
- [x] The README states how to run, locally, the same commands CI runs,
      including how to point `python -m pytest` at a PostgreSQL database.
- [x] `docs/operator-guide.md` and `_docs/architecture.md` agree with the new
      flow wherever they describe the pipeline.

Tests:

- [x] Tests in the default suite check the workflow files for the triggers, the
      runner, the PostgreSQL service, the job dependencies and the
      `SELF_HOSTED_RUNNER` conditions described above.
- [x] `python -m pytest` passes with no failures, both with the SQLite fallback
      and against a PostgreSQL database configured the same way as in CI.
- [x] `python -m pytest -m compose` and `python -m pytest e2e` pass locally.

## Live check (after the user pushes)

Not part of the QA gate, since it needs the changes on GitHub. Once pushed, a
pull request shows the **CI** checks passing, and the push to `main` shows the
tests passing and the self-hosted jobs skipped.

## Out of scope

- A recorded demo of the local deployment belongs to [Issue 33](issue33.md).
- Describing the problem in the README belongs to [Issue 32](issue32.md).
- Branch protection rules, which are configured on GitHub and not in the
  repository.

## Constraints

- Change only `.github/workflows/`, `config/urls.py` (for the static test),
  `README.md`, `docs/operator-guide.md`, `_docs/architecture.md`, and tests
  under `tests/`.
- Keep every existing assertion in `tests/test_release_workflows.py` passing.
- Add no dependencies. Use only first-party GitHub actions (`actions/*`).
- Follow `_docs/testing-guidelines.md`.

## Engineer comment

Changed files (nothing committed; all changes are in the worktree, and the
Issue 30 work is untouched):

- `.github/workflows/ci.yml` (new), named **CI**. Triggers: `pull_request`
  (no filter), `workflow_call` and `workflow_dispatch`, with no `push` trigger.
  Top-level `permissions: contents: read`. It uses no secret and no variable,
  and only `actions/checkout@v4` and `actions/setup-python@v5` (Python
  `"3.13"`, pip cache keyed on `requirements.txt`). Both jobs run on
  `ubuntu-latest` and install with `python -m pip install -r requirements.txt`
  only.
  - **tests**: a `postgres:17-alpine` service with a `pg_isready` health check
    (the job waits for it, and a service that never becomes healthy fails the
    job), port `5432:5432`, and job env
    `DJANGO_DB_ENGINE=django.db.backends.postgresql`,
    `DJANGO_DB_NAME/USER/PASSWORD=calculator`, `DJANGO_DB_HOST=127.0.0.1`,
    `DJANGO_DB_PORT=5432` and `CI_EXPECTED_DATABASE_VENDOR=postgresql`. It
    runs `python -m pytest`.
  - **integration**: `python -m playwright install --with-deps chromium`,
    then `python -m pytest -m compose`, then `python -m pytest e2e`.
  - No step uses `continue-on-error`, `if`, `|| true` or a custom shell, so
    the default `bash -e` fails the job on any failing command.
- `.github/workflows/build.yml`: a new first job `ci`
  (`uses: ./.github/workflows/ci.yml`). `build` now has `needs: ci` and
  `if: vars.SELF_HOSTED_RUNNER == 'true'`, and `deploy-dev` (`needs: build`)
  has the same `if`. The triggers and every build/tag/push/deploy step are
  unchanged. Because ci.yml has no push trigger and build.yml is its only
  caller, a push to `main` runs the tests once, as `ci / tests` and
  `ci / integration` inside the Build and push run. The `if` has no status
  function, so a failed test skips the build and deploy.
- `.github/workflows/deploy-observability.yml`: the `deploy` job gained
  `if: vars.SELF_HOSTED_RUNNER == 'true'`. Nothing else changed.
- `deploy.yml` and `promote-to-production.yml` are unchanged
  (`git diff --quiet HEAD` is clean on both).
- `config/urls.py`: the `^static/` route now calls a small view,
  `collected_static`, which calls
  `serve(request, path, document_root=settings.STATIC_ROOT)` on each request.
  It still serves from `STATIC_ROOT`, but the value is no longer bound when
  the module is imported. Root cause of the failure: the test passed alone
  because nothing had imported `config.urls` before its `settings` override.
  In the full run (and even running just
  `tests/test_production_deployment.py`), the earlier `/health/` test loads
  the URL conf first, so the route kept the original `STATIC_ROOT`
  (`staticfiles/`, which does not exist on a clean checkout) and returned 404.
- `README.md` (CI/CD): a **CI** bullet covering both jobs and their commands,
  the PostgreSQL proof, where the result appears on a pull request
  (**CI / tests** and **CI / integration** in the Conversation and Checks
  tabs), the manual run, and what makes it fail. The **Build** bullet and
  "Running a deployment" step 2 now say the build and dev deploy wait for the
  tests, that a failing test stops them, and that they need
  `SELF_HOSTED_RUNNER`. The "Required repository configuration" table has a
  `SELF_HOSTED_RUNNER` row, and the text under it now says which workflows
  need the runner. A new "Running the CI checks locally" subsection gives the
  CI commands and a PowerShell recipe: a throwaway `postgres:17-alpine`
  container plus the same `DJANGO_DB_*` / `CI_EXPECTED_DATABASE_VENDOR`
  variables. "Direct Python setup" links to it.
- `docs/operator-guide.md`: "Release to dev" describes the CI gate and the
  `SELF_HOSTED_RUNNER` variable (and that Deploy and Promote ignore it). The
  observability "Deploy or update" paragraph notes the gate. "Dependency
  updates" says CI runs the same install and suite against PostgreSQL.
- `_docs/architecture.md`: the Testing Strategy line notes the SQLite local
  fallback and that CI uses PostgreSQL. A Deployment paragraph describes the CI
  workflow, the single test run per push, the gate, and the
  `SELF_HOSTED_RUNNER` condition.
- `tests/test_ci_database.py` (new, 1 test): when
  `CI_EXPECTED_DATABASE_VENDOR` is set, it asserts `connection.vendor` equals
  it, makes a real `SELECT 1` round trip, and, for PostgreSQL, checks that the
  database is pytest-django's `test_*` database. Without the variable it is
  skipped. With the variable set but no `DJANGO_DB_*` variables, it fails
  (`'sqlite' == 'postgresql'`), which I checked.
- `tests/test_ci_workflows.py` (new, 19 tests): `.venv` has no YAML library
  and none may be added, so the module has a small loader for the block-YAML
  subset the workflows use. A test pins the loader's behaviour. The tests
  check:
  - every workflow parses;
  - CI's name and exact trigger set, with no push; `contents: read` only, with
    no `secrets.`/`vars.`; `ubuntu-latest`, Python 3.13 and the single
    requirements install in both jobs;
  - the PostgreSQL 17 service, its health check, that the `DJANGO_DB_*`
    values match the service, the vendor variable and `python -m pytest`;
  - the exact integration command sequence, and no failure-hiding keys;
  - build.yml's `ci` caller, `build` needs `ci`, `deploy-dev` needs `build`,
    no `always()`/`failure()`, and build.yml as the only caller of ci.yml;
  - the build still tags, pushes and deploys dev unchanged;
  - the `SELF_HOSTED_RUNNER` condition on the three jobs, plus a generic check
    that every self-hosted job started by an automatic trigger is gated;
  - ci.yml never reads the variable, and Deploy and Promote are ungated;
  - the README, operator guide and architecture content.
- `tests/test_production_deployment.py`: one regression test. It loads the URL
  conf with a `/health/` request, then overrides `STATIC_ROOT`. The file
  written there is served with its exact bytes, and `site.css`, which is not
  in that `STATIC_ROOT`, returns 404. With the old `config/urls.py` both this
  test and the original static test fail; with the fix both pass.

Notes on the criteria:

- GitHub expression string comparison ignores case, so `SELF_HOSTED_RUNNER`
  set to `TRUE` or `True` also enables the jobs. Any other value, or no value,
  skips them.
- The `if` is on the job itself, so a manual **Run workflow** of Build and
  push or Deploy observability is also skipped without the variable. Without
  that, a manual run on a repository without a runner would wait forever. The
  manual Deploy and Promote dev to production workflows are not gated, as
  required.
- I used `DJANGO_DB_HOST=127.0.0.1` rather than `localhost`. On this Windows
  host, psycopg tries `::1` first for `localhost`, and a container published
  on `127.0.0.1` makes every connection hang until a timeout. The PostgreSQL
  suite took 7m15s with `localhost` and 47s with `127.0.0.1`. Both work on
  the GitHub runner.
- `observability/README.md` (outside the allowed files) still says the
  observability workflow runs on a push that changes `observability/` on the
  self-hosted runner. That is still true when `SELF_HOSTED_RUNNER` is `true`.
  It does not mention the variable; the operator guide and README do.

Verification (I could not run GitHub Actions here; there is no `act`,
`actionlint` or `gh`):

- YAML: every workflow file parses with PyYAML 6.0.3 from the machine's
  global Python 3.12 (run with `-I`, outside `.venv`, used only for this
  check). The test loader's result is identical to PyYAML's for all five
  files.
- `.venv/Scripts/python.exe -m pytest` (SQLite fallback): **443 passed,
  1 skipped** (the PostgreSQL proof test), 30 deselected. That is the
  baseline's 422 passed + 1 previously failing, plus 21 new tests.
- PostgreSQL, configured as in CI: a throwaway container
  `issue31-ci-postgres` (`postgres:17-alpine`, PostgreSQL 17.11) on
  `127.0.0.1:54078`, with `DJANGO_DB_ENGINE=django.db.backends.postgresql`,
  `DJANGO_DB_NAME/USER/PASSWORD=calculator`, `DJANGO_DB_HOST=127.0.0.1`,
  `DJANGO_DB_PORT=54078` and `CI_EXPECTED_DATABASE_VENDOR=postgresql`.
  `python -m pytest`: **444 passed**, 30 deselected (46.7s). The proof test
  PASSED. The container was removed with `docker rm --force --volumes`.
- `test_collected_static_asset_is_served_by_the_application` passes alone and
  in the full run. There is no `staticfiles/` directory in this checkout.
- `python -m pytest -m compose`: **30 passed** (1m24s). Static delivery from
  `STATIC_ROOT` in the container is covered there (`/static/calculator/site.css`
  returns 200). No `*itest*` container or volume was left.
- `python -m pytest e2e`: **could not run locally**. The installed Playwright
  1.64.1 wants Chromium build 1248, and only 1243 is installed ("Executable
  doesn't exist ... chromium_headless_shell-1248"). I did not install a
  browser. Instead: `python -m pytest --collect-only e2e` collects the one
  journey test (it is not deselected by the `-m "not compose"` addopts), and
  `python -m playwright install --with-deps chromium --dry-run` resolves to
  Chromium v1248, so the CI install step fetches the build this Playwright
  needs.
- Python 3.13 is not installed here; the local runs used the `.venv`'s 3.12.
  CI uses 3.13, like the Dockerfile.
- I did not touch the dev, prod or observability Compose projects. Only the
  `registry` container was running on the host, and it was left alone.

The Live check (a PR showing **CI** passing, and a push to `main` showing the
tests passing and the self-hosted jobs skipped) needs the changes on GitHub
and is still to do.

## QA: PASS

Test workflow:

- [x] `ci.yml` is named **CI** and runs on `pull_request`, `workflow_call` and `workflow_dispatch` - PASS
      Read the YAML and parsed it with PyYAML 6.0.3 (global Python, `-I`): `name: CI`, triggers exactly `pull_request` (no filter), `workflow_call`, `workflow_dispatch`; no `push`.
- [x] Jobs run on `ubuntu-latest`, Python 3.13, dependencies only from `requirements.txt` - PASS
      Both jobs: `runs-on: ubuntu-latest`, `actions/setup-python@v5` with `"3.13"`, the only install is `python -m pip install -r requirements.txt`. Also ran the tests job's commands in a throwaway Linux `python:3.13` container (Python 3.13.17) against a `postgres:17-alpine` container: the install succeeded and `python -m pytest` gave 437 passed, 7 skipped (Windows-PowerShell-only tests), 0 failed, with the PostgreSQL vendor test passing.
- [x] **tests** runs `python -m pytest` with a PostgreSQL 17 service and proves it used PostgreSQL - PASS
      Service `postgres:17-alpine` with a `pg_isready` health check and `5432:5432` (the job runs on the runner host, so `127.0.0.1:5432` is correct); the job env selects PostgreSQL and sets `CI_EXPECTED_DATABASE_VENDOR=postgresql`. `tests/test_ci_database.py` passed against PostgreSQL 17.11. With only `CI_EXPECTED_DATABASE_VENDOR=postgresql` set (SQLite fallback) it failed (`'sqlite' == 'postgresql'`) and the full suite reported 1 failed, 443 passed, so the run fails.
- [x] **integration** installs Chromium with `--with-deps`, then runs `-m compose`, then `e2e`, with no secret or variable - PASS
      Steps in that exact order; no `env`, `secrets.` or `vars.` in the file. The Compose fixture generates its own env file, and `compose.yaml` needs no external network or variable (no `.env` exists in this checkout, so the local pass is equivalent to a clean one). Both commands pass locally (see below).
- [x] A failing test, a failed install or a failed service start fails the workflow - PASS
      No `continue-on-error`, step or job `if`, custom shell or `|| true`; the default `bash -e` stops at the first failing command, and a service container that never turns healthy fails job setup. Verified that the vendor check fails the pytest run when the database is not PostgreSQL.
- [x] No secrets, only `contents: read` - PASS
      Top-level `permissions: contents: read`, no job-level permissions, no `secrets.`. As a called workflow it asks for no more than the caller grants (`build.yml` has `contents: read`), so the call is valid.

Gating deployments on tests:

- [x] On every push to `main` the tests run once, and the build and dev deploy start only after they pass - PASS
      `ci.yml` has no `push` trigger; `build.yml` (push to `main`) calls it as job `ci` and is its only caller. A merge into `main` does not fire `pull_request` (the default types exclude `closed`). `build` has `needs: ci`; `deploy-dev` has `needs: build`.
- [x] A failing test on `main` prevents the image build and the dev deploy - PASS
      The job `if` on `build` and `deploy-dev` has no status function, so the implicit `success()` applies: a failed `ci` skips `build`, and the skipped `build` skips `deploy-dev`.

Self-hosted jobs on repositories without a runner:

- [x] Automatically triggered self-hosted jobs run only when `SELF_HOSTED_RUNNER` is `true`; the tests still run - PASS
      `build`, `deploy-dev` (a reusable-workflow caller, where a job-level `if` is allowed) and the `deploy` job of `deploy-observability.yml` have `if: vars.SELF_HOSTED_RUNNER == 'true'`. `vars` is available in a job-level `if`, and an unset variable is `''`, so the jobs are skipped without being queued for a runner. The `ci` job has no `if`. No other workflow has an automatic trigger with a self-hosted job.
- [x] With `SELF_HOSTED_RUNNER=true`, a push to `main` builds, tags, pushes and deploys dev as before; manual Deploy and Promote are unchanged - PASS
      `git diff` of `build.yml` only adds the `ci` job, `needs: ci` and the two `if` lines; every build, tag and push step and the `deploy-dev` call are unchanged. `git diff --stat HEAD` is empty for `deploy.yml` and `promote-to-production.yml`.

Pre-existing failure:

- [x] `test_collected_static_asset_is_served_by_the_application` passes on a clean checkout and in the full suite; static files are still served from `STATIC_ROOT` in the container - PASS
      With no `staticfiles/` directory it passes alone (1 passed), with its file (13 passed) and in the full run. In a scratch copy with the old `config/urls.py` restored, the file run failed this test and the new regression test (2 failed), confirming the fix. In the Compose stack `/static/calculator/site.css` returned 200 with `text/css` (`test_collected_stylesheet_is_served_by_the_web_container` and the quick-start static smoke check passed).

Documentation:

- [x] The README CI/CD section describes CI, each job, where to see the result on a pull request, the deployment gate, and `SELF_HOSTED_RUNNER` (in the configuration table) - PASS
      Read the section: a CI bullet with both jobs and their commands; **CI / tests** and **CI / integration** in the Conversation and Checks tabs; the Build bullet and "Running a deployment" step 2 describe the gate; the table has a `SELF_HOSTED_RUNNER` row.
- [x] The README shows how to run the CI commands locally, including pointing `python -m pytest` at PostgreSQL - PASS
      "Running the CI checks locally" lists the commands and a throwaway `postgres:17-alpine` recipe with the same variables; I followed the same recipe for the PostgreSQL run below.
- [x] `docs/operator-guide.md` and `_docs/architecture.md` agree with the new flow - PASS
      "Release to dev", "Deploy or update" (observability) and "Dependency updates" in the operator guide, and the testing and Deployment sections in the architecture, match the YAML; I found no stale description of the pipeline.

Tests:

- [x] Default-suite tests check the triggers, runner, PostgreSQL service, job dependencies and `SELF_HOSTED_RUNNER` conditions - PASS
      `tests/test_ci_workflows.py` covers each of them, plus a generic check that every automatically triggered self-hosted job is gated. `tests/test_release_workflows.py` is unchanged and passes.
- [x] `python -m pytest` passes with the SQLite fallback and against PostgreSQL configured as in CI - PASS
      See the results below.
- [x] `python -m pytest -m compose` and `python -m pytest e2e` pass locally - PASS
      See the results below.

Tests:

- `.venv/Scripts/python.exe -m pytest` (SQLite fallback): 443 passed, 1 skipped (the PostgreSQL proof test), 30 deselected, 0 failed
- `.venv/Scripts/python.exe -m pytest` against a throwaway `postgres:17-alpine` (PostgreSQL 17.11) on `127.0.0.1:52212`, with `DJANGO_DB_ENGINE=django.db.backends.postgresql`, `DJANGO_DB_NAME/USER/PASSWORD=calculator`, `DJANGO_DB_HOST=127.0.0.1`, `DJANGO_DB_PORT=52212` and `CI_EXPECTED_DATABASE_VENDOR=postgresql`: 444 passed, 30 deselected, 0 failed (`test_ci_database.py` PASSED)
- `.venv/Scripts/python.exe -m pytest` with only `CI_EXPECTED_DATABASE_VENDOR=postgresql` (SQLite): 1 failed (the vendor test, as intended), 443 passed
- A Linux CI simulation (`python:3.13` container plus `postgres:17-alpine` on a private network, same variables): `python -m pip install -r requirements.txt` succeeded, then `python -m pytest` gave 437 passed, 7 skipped, 30 deselected, 0 failed
- `.venv/Scripts/python.exe -m pytest "tests/test_production_deployment.py::test_collected_static_asset_is_served_by_the_application"`: 1 passed; `tests/test_production_deployment.py`: 13 passed (no `staticfiles/` directory)
- `.venv/Scripts/python.exe -m pytest -m compose`: 30 passed, 444 deselected (1m27s)
- `.venv/Scripts/python.exe -m pytest e2e`: 1 passed (21s)

What I could not check here: I did not run the workflows on GitHub (there is no `act`, `actionlint` or `gh`); I checked them by reading and parsing the YAML. The Live check is outside this gate. I removed every container, volume and network I created. `docker ps -a`, `docker volume ls` and `docker network ls` match the state before testing, and I did not touch the dev, prod, observability or registry containers. Nothing in the code was changed.

## Closed by orchestrator

QA PASS on all acceptance criteria. The live check on GitHub (CI checks on a pull request, self-hosted jobs skipped on push) is still open until the user pushes.
