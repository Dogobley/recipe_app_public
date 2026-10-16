# Issue 24: Deploy each release with the compose.yaml from the commit that built it

Status: closed (2026-10-15)

## Goal

A deployment always runs an image with the `compose.yaml` from the same commit that built that image. Promoting to production needs no branch merge, and the `prod` branch is no longer used to deploy.

The pipeline already builds each image once and promotes that same image, but Deploy takes prod's `compose.yaml` from a long-lived `prod` branch that nothing keeps up to date. The last promotion shipped new code with old settings without any error ([Issue 25](issue25.md) fixes that once).

The target model follows the article ["DevOps and observability for an AI-built app"](https://aishippingblog.com/p/devops-and-observability-for-an-ai):

- one branch, `main`
- push to `main` deploys to dev
- promotion is manual and confirmed, and takes the image dev is actually running
- dev and prod differ only in their env files

## Acceptance criteria

Code and settings come from the same commit:

- [ ] A push to `main` deploys to dev using the `compose.yaml` from the pushed commit, even if `main` moves again before the deploy job starts.
- [ ] Running **Deploy** with a release tag such as `20261014-191754-9bdd779` uses the `compose.yaml` from commit `9bdd779`, for both `dev` and `prod`. The run log prints the release tag and the commit it checked out.
- [ ] Running **Deploy** with a tag that does not end in a commit of this repository (`dev`, `prod`, `latest` or a typo) fails before any container changes. The error says a release tag is required.
- [ ] No workflow file references the `prod` branch (`grep -rn "'prod'" .github/workflows` finds no checkout `ref`).

Promotion takes what dev is running, and needs confirmation:

- [ ] **Promote dev to production** with no tag given promotes the release tag the running dev container reports in `APP_VERSION`, not whatever the `dev` registry tag points to. If a newer build pushed `dev` but failed its health check, Promote still ships the last healthy dev release.
- [ ] Promote has a required "confirm" checkbox. Running it unchecked fails without retagging or deploying anything.
- [ ] Promote with an explicit release tag promotes that tag. With a tag that is not in the registry, it fails before retagging, and prod keeps running.
- [ ] If the dev container is not running or not healthy and no tag is given, Promote fails with a message saying so, and prod is unchanged.
- [ ] After Promote, the prod web container reports the same `APP_VERSION` as the release that was promoted, and the workflow run summary shows that release tag and its commit.
- [ ] Promoting the release that is already in prod succeeds and leaves prod healthy.

Rollback:

- [ ] Running **Deploy** for `prod` with an older release tag runs that release with its own commit's `compose.yaml`, and the prod web container reports the older `APP_VERSION`.
- [ ] Rolling back to a release built before `9bdd779` still reports its release tag as `service_version`. Older images have no baked `APP_VERSION`, but their own `compose.yaml` sets it from `IMAGE_TAG`.

Prod-only content moves to `main`:

- [ ] `main` has a tracked `.env.prod.example`. It holds the template from the `prod` branch (`COMPOSE_PROJECT_NAME=recipe-cost-calculator-prod`, `WEB_PORT=8001`, port 8001 CSRF origins, placeholders) plus `DEPLOYMENT_ENVIRONMENT=prod`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318` and `OTEL_PYTHON_DJANGO_EXCLUDED_URLS=health/`. It contains no real secret.
- [ ] `docs/operator-guide.md` on `main` has the "Environments: dev and production" section from the `prod` branch, updated for the new release flow.
- [ ] `_docs/architecture.md` on `main` describes the two environments: one `compose.yaml`, separate Compose projects, ports 8000 and 8001, and differences only in env files.

Docs and tests:

- [ ] `README.md`'s CI/CD section describes Build, Deploy (including rollback with an older release tag) and Promote (confirmation, defaulting to what dev runs). The sentence saying changes reach prod only after merging `main` into `prod` is removed.
- [ ] `docs/operator-guide.md` has a "Releasing and rolling back" section with the exact steps, including how to find which release each environment runs (`docker inspect` or the Promote run summary).
- [ ] Tests check the workflows' text:
  - Deploy derives the checkout commit from the release tag.
  - Deploy rejects tags without a commit.
  - Promote has a required confirm input and reads the release from the dev container.
- [x] `python -m pytest` passes.

## Out of scope

- The one-time update of the `prod` branch, needed before this issue lands to unblock Issue 22 - moved to [Issue 25](issue25.md).

## Constraints

- Change only these files:
  - `.github/workflows/deploy.yml`, `.github/workflows/promote-to-production.yml` and, if Build must pass its commit explicitly, `.github/workflows/build.yml`
  - `.env.prod.example`, `README.md`, `docs/operator-guide.md` and `_docs/architecture.md`
  - tests under `tests/`
- Keep building once and promoting the same image. Promote retags; it never rebuilds.
- Release tags keep the format `YYYYMMDD-HHMMSS-shortsha`. The commit is the part after the last `-`.
  - Checking out a short SHA needs the repository history (`fetch-depth: 0`), or resolve it to the full SHA first.
- Find the dev container through Compose in `DEPLOY_PATH` (`docker compose --env-file .env ps -q web`). Do not hard-code a container name; the dev project name comes from the folder (`deploy`).
- Dev and prod must keep using the same `compose.yaml`. Every difference goes in `.env` / `.env.prod`.
- Do not delete the `prod` branch. Once QA passes, the operator deletes it or leaves it as an archive.
- Separate hosts per environment, as in the article, are deliberately not adopted: one host is enough for a single-user app.
- A GitHub Environment approval gate is deliberately not adopted: the confirm checkbox gives the same manual approval without repository settings.
- Read `_docs/testing-guidelines.md` before writing tests and follow the text-inspection style of `tests/test_production_deployment.py`.
- Do not add dependencies.
- Do not commit or push unless the user asks.

## Engineer comment

Implemented every acceptance criterion; nothing committed or pushed, issue left open.

Changes:
- `.github/workflows/deploy.yml`: `image_tag` is now required (dispatch and call). The job checks out with `fetch-depth: 0`, validates the tag against `^\d{8}-\d{6}-([0-9a-f]{7,40})$`, resolves the short SHA with `git rev-parse --verify`, and `git checkout --detach`es that commit before copying its `compose.yaml`. It prints the release tag and commit and writes them to the run summary. A non-release tag (`dev`, `prod`, `latest`, typo, unknown SHA) fails with "A release tag ... is required" before registry login or any compose command. No `prod` branch reference remains; `build.yml` is unchanged (the tag already ends in the pushed commit's short SHA, so a push deploys that commit's compose.yaml).
- `.github/workflows/promote-to-production.yml`: new required boolean `confirm`, checked first (fails before login/retag/deploy). With no tag, it finds the dev container via `docker compose --env-file .env ps -q web` in `DEPLOY_PATH`, requires health `healthy`, and reads `APP_VERSION` from the container's config env (not the `dev` registry tag). It validates the release format, `docker pull`s it (fails before retagging if missing), retags `prod`, pushes, exposes `release_tag` as a job output, and writes release and commit to the run summary. `deploy-prod` now deploys `needs.promote.outputs.release_tag`.
- `.env.prod.example` added from the `prod` branch template plus `DEPLOYMENT_ENVIRONMENT=prod`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_PYTHON_DJANGO_EXCLUDED_URLS`; placeholders only.
- `docs/operator-guide.md`: "Environments: dev and production" section copied from the `prod` branch and updated, plus new "Releasing and rolling back" section (docker inspect, Promote summary, promote, rollback).
- `README.md`: CI/CD section rewritten (Build, Deploy with rollback, Promote with confirm/default); the "merge main into prod" sentence is removed.
- `_docs/architecture.md`: Deployment section describes the two environments and the release flow.
- `tests/test_release_workflows.py`: text checks for the criteria above.

Tests: `.venv/Scripts/python -m pytest` -> 318 passed, 23 deselected.

Not verifiable without a live stack / GitHub: actual workflow runs (push deploy, manual Deploy, rollback, Promote cases including unchecked confirm, missing tag, unhealthy dev, re-promoting the current release), that `docker inspect` of the prod container reports the promoted `APP_VERSION`, and rollback to pre-`9bdd779` releases (relies on that commit's own compose.yaml, which is not in this repo state). Note: a boolean `required` input can still be submitted unchecked, hence the explicit confirm step. The `prod` branch was left untouched (Issue 25).

## QA: PASS

Verified against the worktree (uncommitted changes) by reading the workflow text and docs. Live GitHub Actions and Docker runs were not possible here; those criteria are marked verified-by-inspection (the text logic is correct, so they are not FAILs).

- [x] Push to `main` deploys to dev with the pushed commit's `compose.yaml` - PASS (by inspection). `build.yml` tags the image with `GITHUB_SHA[0:7]` and calls Deploy; Deploy checks out the commit named by the tag (`git checkout --detach`) before `Copy-Item compose.yaml`, so a moved `main` does not matter.
- [x] Deploy with a release tag uses that commit's `compose.yaml` for dev and prod; log prints tag and commit - PASS (by inspection). `fetch-depth: 0`, regex `^\d{8}-\d{6}-([0-9a-f]{7,40})$`, `git rev-parse --verify`, `git checkout --detach`, prints "Release tag:" and "Commit checked out:", writes the step summary.
- [x] Deploy rejects `dev`/`prod`/`latest`/typo before any container change, error says a release tag is required - PASS (by inspection). The validation step runs before the registry login and every `docker compose` call; an unknown SHA also fails with "A release tag is required".
- [x] No workflow references the `prod` branch - PASS. `grep "prod'" .github/workflows` only finds the `.env.prod` selection and a log message; no checkout `ref`.
- [x] Promote with no tag uses the dev container's `APP_VERSION`, not the `dev` registry tag - PASS (by inspection). It finds the container with `docker compose --env-file .env ps -q web` in `DEPLOY_PATH` and reads `APP_VERSION` from `.Config.Env`.
- [x] Promote has a required confirm checkbox; unchecked fails without retagging or deploying - PASS (by inspection). `confirm` is `required: true`, `type: boolean`. The first step fails unless it equals `true`, before login, retag and deploy (`deploy-prod` needs `promote`).
- [x] Explicit tag is promoted; a tag missing from the registry fails before retagging - PASS (by inspection). `docker pull` runs and fails before `docker tag` and `docker push`.
- [x] Dev not running or not healthy with no tag fails with a message and prod unchanged - PASS (by inspection). Both cases have explicit error messages, and nothing downstream runs.
- [x] After Promote, prod reports the promoted `APP_VERSION`; run summary shows release and commit - PASS (by inspection). `deploy-prod` deploys `needs.promote.outputs.release_tag`, and the summary line shows the release and commit. The image bakes `APP_VERSION` via `build-arg`. The live `docker inspect` of prod is unverifiable here.
- [x] Promoting the release already in prod succeeds - PASS (by inspection). Pull, retag and redeploy are idempotent, with no "already exists" check.
- [x] Deploy `prod` with an older tag runs that release with its own commit's `compose.yaml`; prod reports the older `APP_VERSION` - PASS (by inspection). This is the same path as the Deploy criteria above.
- [x] Rollback before `9bdd779` still reports its tag as `service_version` - UNVERIFIABLE, not a FAIL. The workflow takes `compose.yaml` from the release's own commit, so the result depends on that commit's file. The current `compose.yaml` passes `APP_VERSION: ${IMAGE_TAG}` as a build arg and Deploy exports `IMAGE_TAG`.
- [x] `.env.prod.example` tracked on `main` with the prod-branch template plus the three additions, placeholders only - PASS. Compared with `git show prod:.env.prod.example`: identical template, plus `DEPLOYMENT_ENVIRONMENT=prod`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318` and `OTEL_PYTHON_DJANGO_EXCLUDED_URLS=health/`. No real secrets. It is untracked in git status until committed, which is expected because nothing is committed yet.
- [x] `docs/operator-guide.md` has "Environments: dev and production", updated for the release flow - PASS. The section is present (it also exists on the `prod` branch) and links to the release flow.
- [x] `_docs/architecture.md` describes the two environments - PASS. It covers one `compose.yaml`, separate Compose projects, ports 8000/8001, and differences only in env files.
- [x] README CI/CD describes Build, Deploy with rollback, and Promote with confirm and default to dev; the "merge main into prod" sentence is removed - PASS.
- [x] Operator guide has "Releasing and rolling back" with exact steps and `docker inspect` / Promote summary - PASS.
- [x] Tests check Deploy commit derivation, tag rejection, and Promote confirm and dev-container read - PASS. `tests/test_release_workflows.py` has 8 tests covering them.
- [x] `python -m pytest` passes - PASS.

Tests: `.venv/Scripts/python -m pytest`, 318 passed, 0 failed, 23 deselected (includes the 8 tests in `tests/test_release_workflows.py`).

Not covered by tests, and not verifiable here: real workflow runs on GitHub and the self-hosted runner. `git checkout --detach` and `$Matches` behaviour in PowerShell were reviewed by reading only. No code was changed.

## Reopened: Promote cannot find the dev container

The first live run of **Promote dev to production** (confirm ticked, no tag), on 2026-10-14 during [Issue 25](issue25.md), failed at "Resolve the release to promote":

```
Error: The dev web container is not running, so there is no dev release to promote. Production is unchanged.
```

At that moment the dev web container (`deploy-web-1`) was running and healthy and reported `APP_VERSION=20261014-214154-5e6e01d`. Production was unchanged: the prod web container still had the start time 2026-10-14T19:53:34Z.

Cause: `promote-to-production.yml`, step "Resolve the release to promote":

```powershell
$container = (docker compose --env-file .env ps -q web | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or -not $container) { ... }
```

In Windows PowerShell 5.1, `Select-Object -First 1` stops the pipeline once it has one item, which terminates `docker compose`, so `$LASTEXITCODE` is `-1` even though the container ID was returned. Reproduced with `powershell.exe` in `deploy/`:

- As written: `LASTEXITCODE=-1 container=[1a5836c5…]`, so the error branch runs.
- Collecting the output first, `$ids = @(docker compose --env-file .env ps -q web)`, and taking the first ID afterwards: `LASTEXITCODE=0`, with the same container.

The text-only tests in `tests/test_release_workflows.py` and the QA review could not catch this.

### Acceptance criteria (reopen)

- [x] The release lookup in "Resolve the release to promote" collects the `docker compose ... ps -q web` output before selecting the first ID, so a running dev container yields exit code 0. The existing not-running and not-healthy errors still fire when they should.
- [x] No other step in the release workflows pipes a native command directly into `Select-Object -First` and then checks `$LASTEXITCODE`.
- [x] A test in `tests/test_release_workflows.py` fails if that pattern comes back.
- [ ] `python -m pytest` passes.
- [x] Live check: after the fix is pushed and Build redeploys dev, Promote with confirm ticked and no tag gets past "Resolve the release to promote" and names the release dev reports. This is recorded in Issue 25.

Constraints: change only `.github/workflows/promote-to-production.yml` and `tests/test_release_workflows.py`. Pushing and running Promote need the user's approval. Do not add dependencies.

## Engineer comment (reopen fix)

Committed in `a707e89` (only `.github/workflows/promote-to-production.yml` and `tests/test_release_workflows.py`). Not pushed; issue left open.

- `promote-to-production.yml`, "Resolve the release to promote": the lookup is now `$ids = @(docker compose --env-file .env ps -q web)`, then a `$LASTEXITCODE` check (fails with "docker compose ps failed ... Production is unchanged."), then `$container = $ids | Where-Object { "$_".Trim() } | Select-Object -First 1`. Selecting from a variable does not stop a native process, so a running dev container now yields exit code 0. The existing "not running" (no ID) and "not healthy" errors are unchanged and still fire.
- Checked every workflow under `.github/workflows/` (`build.yml`, `deploy.yml`, `promote-to-production.yml`): the only native command piped into `Select-Object -First` before a `$LASTEXITCODE` check was the one fixed. The other `Select-Object -First` (APP_VERSION lookup) pipes a variable, not a native command. Nothing to report in other workflows.
- `tests/test_release_workflows.py`: a detector for the pattern (native command, not a `$variable` or Verb-Noun cmdlet, piped into `Select-Object -First` with `$LASTEXITCODE` on the same or next three lines), a test proving it flags the old line and accepts the new one, a test scanning all `*.yml`/`*.yaml` workflow files, and a test that Promote collects IDs and checks the exit code before selecting. The detector also flags the pre-fix `promote-to-production.yml` from `HEAD~1`.

Tests: `.venv/Scripts/python -m pytest` -> 321 passed, 23 deselected.

Pending (operator action, needs user approval): push the fix, let Build redeploy dev, then run Promote with confirm ticked and no tag and check it gets past "Resolve the release to promote" and names the release dev reports (to be recorded in Issue 25).

## QA (reopen fix): PASS

I checked the reopen criteria against commit `a707e89`. I read the code and ran the patterns in Windows PowerShell 5.1 (`powershell.exe`, 5.1.26100). The live check still needs operator action, so it is not part of this verdict.

- [x] "Resolve the release to promote" collects the `docker compose ... ps -q web` output before it selects the first ID, so a running dev container gives exit code 0. The not-running and not-healthy errors still fire - PASS.
      Code: `$ids = @(docker compose --env-file .env ps -q web)`, then the `$LASTEXITCODE` check, then `$ids | Where-Object {...} | Select-Object -First 1`, then the existing not-running and not-healthy checks.
      I ran the real command read-only in `deploy/`. The old pattern gave `LASTEXITCODE=-1` with container `1a5836c5…`. The new pattern gave `LASTEXITCODE=0` with the same container, health `healthy` and `APP_VERSION=20261014-214154-5e6e01d`.
      With `cmd /c "echo a& echo b& echo c"`, the old pattern gave `-1` and the new one gave `0`. `git log --oneline -50` gave `0` both ways, because it finishes before the pipeline stops, so not every command shows the bug.
      I ran the new logic on simulated output:
      - no output: "not running"
      - blank lines only: "not running"
      - non-zero exit: the new "docker compose ps failed" error
      - several IDs: the first ID
      A real empty result (`ps -q --status exited web`) gave exit 0 and 0 IDs, so the "not running" branch ran.
- [x] No other step in the release workflows pipes a native command into `Select-Object -First` and then checks `$LASTEXITCODE` - PASS.
      I searched `.github/workflows/` (`build.yml`, `deploy.yml`, `promote-to-production.yml`) for `Select-Object`. Apart from a comment, it appears only in `$ids | ... | Select-Object -First 1` and `$envLines | ... | Select-Object -First 1`. Both pipe a variable, not a native command.
- [x] A test in `tests/test_release_workflows.py` fails if the pattern comes back - PASS.
      I put a scratch copy of `.github/workflows/` with the pre-fix `promote-to-production.yml` (`a707e89~1`) in my scratchpad. I pointed the test module's `WORKFLOWS` at it from a scratch script, and no repo file changed.
      Both `test_no_workflow_pipes_a_native_command_into_select_first_before_an_exit_code_check` and `test_promote_collects_dev_container_ids_before_selecting_the_first` failed, naming line 68 of the old file.
- [x] `python -m pytest` passes - PASS.
- [ ] Live check (push, Build redeploys dev, Promote with confirm ticked and no tag gets past "Resolve the release to promote") - NOT VERIFIED, pending operator action.
      It needs the user's approval to push and to run Promote. It is to be recorded in Issue 25. This is not a code failure.

Tests: `.venv/Scripts/python -m pytest`: 321 passed, 0 failed, 23 deselected. `tests/test_release_workflows.py` alone: 11 passed.

Not covered by the tests:
- The detector only matches the full `Select-Object -First`. It misses aliases such as `docker ps -q | select -first 1`.
- It only looks for `$LASTEXITCODE` within three lines after the pipe.
- The tests read the workflow text only. Only the manual PowerShell 5.1 runs above show the runtime behaviour.

No code or tests were changed.

## Live check (reopen), 2026-10-15: PASS

- The fix (`a707e89`) was pushed; Build redeployed dev. Dev later ran `20261015-011621-66d0c23` (after Issue 28's push).
- The user ran **Promote dev to production** with confirm ticked and no tag; it finished green (reported by the user; run URL not recorded here).
- Afterwards `docker ps` showed `recipe-cost-calculator-prod-web-1` recreated (new container `ba166a43924f`, healthy) on image `localhost:5000/recipe_app:20261015-011621-66d0c23`, the same release the dev web container reports in `APP_VERSION`. The prod database container (`0b12e09ccc89`) was not restarted.
- Prometheus `target_info` shows `deployment_environment=prod` with `service_version=20261015-011621-66d0c23`.

## Closed by orchestrator

QA (reopen fix) PASS on the code criteria, and the live Promote run passed.

## Live check from Issue 25 (2026-10-15)

Criteria checked live in [Issue 25](issue25.md):

- Dev deploy prints and runs the release tag and its commit (`20261015-020111-c28a8f3`, commit `c28a8f3f…`) - PASS
- Promote with confirm unticked fails at "Require confirmation" - PASS
- Deploy for prod with tag `prod` fails with the release-tag error, prod container unchanged - PASS
- Promote with confirm ticked and no tag promotes the dev release; summary and prod Deploy log show the same tag and commit; prod `APP_VERSION` matches - PASS
- Prod data unchanged across the promotion - PASS
- Rollback to an older release: not exercised; moved to [Issue 26](issue26.md).
