# Issue 30: Run the whole system from a fresh clone with one command

Status: closed (2026-10-22)

## Goal

Someone who has just cloned the repository, with only Docker installed, starts
the complete application (Django web service and PostgreSQL) with one command,
without creating or editing any file first. Deployments keep refusing to start
with missing or placeholder settings.

## Acceptance criteria

Tracked environment files:

- [x] `.env.example` is tracked by git (it is currently matched by `.gitignore`,
      so a fresh clone does not have it). It still holds placeholders only.
- [x] `.env` and `.env.prod` are still ignored by git.
- [x] A tracked `quickstart.env` at the repository root defines every variable
      that `compose.yaml` requires with `${NAME:?...}`, with working values:
  - no value from `PLACEHOLDER_VALUES` in `config/settings.py` and no
    `replace-with-` value
  - `DJANGO_DEBUG=false`
  - `COMPOSE_PROJECT_NAME=recipe-cost-calculator-quickstart`
  - `WEB_PORT=8080`
  - `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`
  - `DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080`
  - `DEPLOYMENT_ENVIRONMENT=local`
- [x] `quickstart.env` opens with a comment saying it is for local evaluation
      only, that its values are public, and that dev and production use `.env`
      and `.env.prod` instead.
- [x] `quickstart.env` parses the same on a Windows checkout as on Linux and
      macOS: `docker compose --env-file quickstart.env config` shows no
      carriage return in any value.

One-command start:

- [x] From a fresh clone with Docker running and no `.env` file,
      `docker compose --env-file quickstart.env up --build --detach` starts
      `db` and `web`, and `docker compose --env-file quickstart.env ps` shows
      both as `healthy`. No other step is needed.
- [x] After that command, `http://localhost:8080/health/`, `http://localhost:8080/`
      and `http://localhost:8080/static/calculator/site.css` each return `200`.
- [x] An ingredient created through the browser at `http://localhost:8080/` is
      still there after `docker compose --env-file quickstart.env down` and the
      same `up` command again.
- [x] `docker compose --env-file quickstart.env down -v` removes the quick-start
      database volume.
- [x] The quick-start stack uses its own Compose project, containers, network and
      volume. Starting or removing it does not change the dev
      (`DEPLOY_PATH/.env`, port `8000`) or production (`.env.prod`, port `8001`)
      containers or volumes on the same host.

Deployments unchanged:

- [x] `compose.yaml` still fails fast: `docker compose config` with no `.env`
      and no `--env-file` exits non-zero and names a missing variable, as it
      does today.
- [x] The production settings still reject a missing secret, the example
      placeholders, and `DJANGO_DEBUG=true`.
- [x] `.env.prod.example`, the release workflows and the observability stack are
      unchanged.

Documentation:

- [x] The README has a **Quick start** section directly below the title and
      intro. It lists the prerequisite (Docker with Compose v2), the single
      command, the URL to open, how to stop it, how to wipe its data, and that
      `quickstart.env` is not for deployments.
- [x] Every README and operator-guide instruction that copies `.env.example`
      works from a fresh clone.
- [x] The operator guide states that `quickstart.env` is for local evaluation
      only and that the dev and production deployments keep using `.env` and
      `.env.prod`.

Tests:

- [x] The default suite (`python -m pytest`, no Docker) checks the git-tracking
      rules and the contents of `quickstart.env` described above.
- [x] The Compose suite (`python -m pytest -m compose`) starts the stack from
      `quickstart.env`, on an isolated project and a free loopback port, and
      checks that both services are healthy and that the health, home and
      stylesheet URLs return `200`.
- [x] `python -m pytest` and `python -m pytest -m compose` both pass.

## Out of scope

- Running the test suite in CI on every pull request belongs to
  [Issue 31](issue31.md).
- Describing the problem, features and expected behaviour in the README belongs
  to [Issue 32](issue32.md).
- Demo or seed data for the quick start.
- Changes to the dev or production deployment process.

## Constraints

- Change only `.gitignore`, `.gitattributes`, the new `quickstart.env`,
  `README.md`, `docs/operator-guide.md`, and tests under `tests/`. Change
  `compose.yaml` or `tests/compose/` fixtures only if a criterion cannot be met
  otherwise, and keep its `${NAME:?...}` fail-fast checks.
- Add no dependencies.
- Follow `_docs/testing-guidelines.md`, including its Compose integration test
  rules (isolated project name, free loopback port, volume removed afterwards).
- Keep `_docs/architecture.md` accurate: if the quick start changes anything it
  describes under Deployment, update that section.

## Engineer comment

Changed files (nothing committed; all changes are in the worktree):

- `.gitignore`: removed the `.env.example` line. `.env` and `.env.prod` are
  still ignored. `.env.example` is unchanged apart from LF endings and still
  holds the `replace-with-` placeholders. It becomes tracked when this change
  is committed.
- `.gitattributes`: `quickstart.env text eol=lf` and `.env.example text eol=lf`,
  so a Windows checkout (`core.autocrlf=true`, as on this machine) writes both
  with LF.
- `quickstart.env` (new, LF): it opens with a comment saying it is for local
  evaluation only, that its values are public, and that dev and production use
  `.env` and `.env.prod` instead. It sets every `${NAME:?...}` variable
  (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`,
  `DJANGO_CSRF_TRUSTED_ORIGINS`, `POSTGRES_DB/USER/PASSWORD`), plus
  `COMPOSE_PROJECT_NAME=recipe-cost-calculator-quickstart`, `WEB_PORT=8080`,
  `DEPLOYMENT_ENVIRONMENT=local` and `DJANGO_TIME_ZONE=UTC`. It also sets
  `IMAGE_REPOSITORY=recipe-cost-calculator-quickstart` and `IMAGE_TAG=local`,
  so the quick start builds its own image tag and never overwrites
  `recipe_app:*`. None of its values are in `PLACEHOLDER_VALUES`, and none
  contain `replace-with-`.
- `README.md`: a new **Quick start** section directly below the title and
  intro. It covers the prerequisite (Docker with Compose v2), the one command,
  `http://localhost:8080/`, stop (`down`), wipe (`down -v`), the separate
  project and port, and that `quickstart.env` is not for deployments.
- `docs/operator-guide.md`: a new "Quick start for local evaluation" section
  before "Prerequisites and first local deployment". It states that
  `quickstart.env` is for local evaluation only and that the dev and
  production deployments keep using `.env` and `.env.prod`. The Environments
  section also gained a note that the quick start is not one of them.
- `_docs/architecture.md` (Deployment): one paragraph on the quick start's
  project, port and separate containers, network and volume.
- `tests/test_quickstart.py` (new, default suite, 17 tests): git ignore rules
  via `git check-ignore --no-index` (`.env.example` and `quickstart.env` not
  ignored; `.env` and `.env.prod` ignored), `git check-attr eol` = `lf` and no
  `\r` byte in either env file, `.env.example` still has placeholders, and
  `quickstart.env` covers every `${NAME:?` variable in `compose.yaml` with no
  placeholder or `replace-with-` value. It also checks the six required
  values and the opening comment, and that the quickstart values pass the
  production settings checks (settings reloaded with `DJANGO_ENV=production`).
  Production settings still reject `DJANGO_DEBUG=true`. In the docs: the
  README's first `##` section is Quick start and has the required items, the
  operator guide has the local-evaluation-only statement, and every
  `Copy-Item <source>` in the README and the operator guide names a file that
  exists and is not ignored.
- `tests/compose/test_quickstart_stack.py` (new, `compose` marker, 7 tests):
  - `docker compose --env-file quickstart.env config --format json` has no
    `\r` in any value and uses project `recipe-cost-calculator-quickstart`,
    port `8080`, volume `recipe-cost-calculator-quickstart_postgres_data` and
    network `recipe-cost-calculator-quickstart_default`.
  - `compose.yaml` with no `.env` and no `--env-file` (empty project
    directory) exits non-zero and names the missing variable.
  - The stack starts from `quickstart.env` on its own project
    (`recipe-cost-calculator-quickstart-itest`) with the existing
    free-loopback-port override. Both services are `healthy`, and `/health/`,
    `/` and `/static/calculator/site.css` return 200.
  - It is removed with `down --volumes` before and after the run.

  The test subclasses the existing `Stack`, so `tests/compose/conftest.py`,
  `compose.override.yaml` and `compose.yaml` are unchanged.

`.env.prod.example`, `.github/`, `observability/`, `compose.yaml`, `config/`
and the compose fixtures are unchanged: `git diff --quiet` on them is clean.

Manual verification from a real fresh clone (scratch dir): I cloned this repo,
copied the changed files in, committed them in that scratch clone only, then
ran `git clone` of the scratch clone with the machine's `core.autocrlf=true`.
The new clone had `.env.example` and `quickstart.env` tracked and checked out
with LF (`file`: "ASCII text"; `compose.yaml` came out CRLF). It had no `.env`.
`git check-ignore` still matched `.env` and `.env.prod`. There was no `.env`
in this repo's root either.

- `docker compose --env-file quickstart.env config --format json`: no value
  contains `\r`; project `recipe-cost-calculator-quickstart`. Note: Compose
  v2.28.1 also strips CR from a CRLF copy of the file, so `eol=lf` is a guard
  for other Compose versions and env-file readers, not a fix for a failure I
  could reproduce here.
- `docker compose --env-file quickstart.env up --build --detach`: exit 0. `ps`
  showed `db` and `web` both `(healthy)`, with `web` on `0.0.0.0:8080->8000`.
  `curl` returned `200` for `/health/`, `/` and `/static/calculator/site.css`.
- In Chromium (Playwright, through the visible Ingredients > Add ingredient
  form), I created "Quickstart persistence flour" and saw "Ingredient added
  successfully." After `down`, the volume
  `recipe-cost-calculator-quickstart_postgres_data` remained. After the same
  `up` command, both services were healthy again and the ingredient was still
  in the list.
- `docker compose --env-file quickstart.env down -v`: the volume and network
  were removed, and no quick-start container, volume or network was left.
- Isolation: before and after the whole run, the container list (IDs, names,
  projects, and the status of `deploy-*` and
  `recipe-cost-calculator-prod-*`), the creation times of
  `deploy_postgres_data`, `ai_dev_project_postgres_data` and
  `recipe-cost-calculator-prod_postgres_data`, and the network list were
  identical. The dev and prod containers were stopped (Exited 6 days ago)
  during this check, and I did not start them. Their isolation while running
  rests on the separate project, port and volume names shown by `config`.
- `docker compose config --quiet` in the repo root with no `.env`: exit 15,
  "required variable POSTGRES_DB is missing a value: Set POSTGRES_DB in .env".

Tests:

- `.venv/Scripts/python.exe -m pytest`: 422 passed, 1 failed, 30 deselected.
  The one failure is the existing
  `tests/test_production_deployment.py::test_collected_static_asset_is_served_by_the_application`
  (Issue 31). The baseline was 405 passed, 1 failed, 23 deselected; this
  change adds 17 default tests and 7 compose tests.
- `.venv/Scripts/python.exe -m pytest -m compose`: 30 passed, 423 deselected.
- `.venv/Scripts/python.exe -m pytest tests/test_quickstart.py` in the fresh
  clone: 17 passed.

The local venv is Python 3.12; the container image uses 3.13. The criterion
"`python -m pytest` passes" is met except for the existing Issue 31 failure,
which is out of scope here.

## QA: PASS

Method: cloned this repository into a scratch directory, copied in every
changed and untracked file from `git status`, committed them in that scratch
clone only, then ran `git clone` on the scratch clone with this machine's
`core.autocrlf=true`. That second clone (no `.env`, no `.env.prod`) was the
"fresh clone" for every check below. The real dev and production containers
were stopped (Exited 6 days ago) and I did not start them. To check isolation
against a running deployment, I also ran a stand-in dev deployment from another
scratch clone: `.env` copied from `.env.example`, project `qa30-devsim`, port
`8000`, its own image name. Nothing in this repository was staged, committed or
edited except this comment.

Tracked environment files:

- [x] `.env.example` is tracked by git and still holds placeholders only - PASS
      The fresh clone has it (`git ls-files`) and `git check-ignore` does not
      match it. `DJANGO_SECRET_KEY`, `DJANGO_DB_PASSWORD` and `POSTGRES_PASSWORD`
      are the `replace-with-` placeholders; other values are non-secret defaults.
- [x] `.env` and `.env.prod` are still ignored by git - PASS
      `git check-ignore -v` in the fresh clone matches both (`.gitignore:6`, `:8`).
- [x] Tracked `quickstart.env` defines every `${NAME:?...}` variable with working
      values - PASS
      It covers all 7 required names in `compose.yaml`. No value is in
      `PLACEHOLDER_VALUES` or contains `replace-with-`. The six fixed values
      match exactly. The values pass the production settings checks (fresh
      Python process with `DJANGO_ENV=production`: settings accepted).
- [x] `quickstart.env` opens with the local-evaluation-only comment - PASS
      Line 1 starts the comment: local evaluation only, values public, dev and
      production read `.env` and `.env.prod` instead.
- [x] `quickstart.env` parses the same on a Windows checkout - PASS
      Fresh clone with `core.autocrlf=true`: `git ls-files --eol` shows
      `w/lf attr/text eol=lf` for `quickstart.env` and `.env.example`, while
      `compose.yaml` is `w/crlf`. `docker compose --env-file quickstart.env config`
      output contains no `\r`, and walking the JSON config found no `\r` in any
      value.

One-command start:

- [x] Fresh clone, no `.env`: `up --build --detach` starts `db` and `web`, both
      `healthy` - PASS
      Port 8080 was free. The command exited 0. `docker compose --env-file
      quickstart.env ps` showed `db` and `web` `Up (healthy)`, with web on
      `0.0.0.0:8080->8000`. No other step.
- [x] `/health/`, `/` and `/static/calculator/site.css` on `localhost:8080`
      return 200 - PASS
      `curl`: 200, 200, 200 (`http://127.0.0.1:8080/` also 200).
- [x] An ingredient created through the browser survives `down` and `up` - PASS
      In Chromium (Playwright), through Ingredients > Add ingredient, I created
      "QA30 quickstart persistence" and saw "Ingredient added successfully."
      After `down` the volume remained. After the same `up` both services were
      healthy and the ingredient was listed.
- [x] `down -v` removes the quick-start database volume - PASS
      `recipe-cost-calculator-quickstart_postgres_data` and the network were
      removed. No quick-start container, volume or network was left.
- [x] Own Compose project, containers, network and volume; dev and production
      unchanged - PASS
      Config: project `recipe-cost-calculator-quickstart`, volume
      `recipe-cost-calculator-quickstart_postgres_data`, network
      `recipe-cost-calculator-quickstart_default`, image
      `recipe-cost-calculator-quickstart:local`. I took snapshots before start,
      while running, and after `down -v`: container IDs and names; State,
      StartedAt and RestartCount of `deploy-*`, `recipe-cost-calculator-prod-*`
      and the running `qa30-devsim-*`; creation times of `deploy_postgres_data`,
      `ai_dev_project_postgres_data`, `recipe-cost-calculator-prod_postgres_data`
      and `qa30-devsim_postgres_data`; networks; `recipe_app*` images. While it
      was running, the only differences were the two quick-start containers and
      network. After removal everything was identical. The running stand-in dev
      stack stayed healthy, kept its own record, and did not show the
      quick-start ingredient. The full `docker ps -a`, `docker volume ls` and
      `docker network ls` output before and after the whole QA run is identical
      (apart from uptime text).

Deployments unchanged:

- [x] `compose.yaml` still fails fast - PASS
      `docker compose config --quiet` in the fresh clone with no `.env`: exit 15,
      "required variable POSTGRES_DB is missing a value: Set POSTGRES_DB in .env".
- [x] Production settings still reject a missing secret, the placeholders and
      `DJANGO_DEBUG=true` - PASS
      Fresh Python processes with `DJANGO_ENV=production`: a missing
      `DJANGO_SECRET_KEY`, `DJANGO_SECRET_KEY=replace-with-a-long-random-secret`,
      `DJANGO_DB_PASSWORD=replace-with-a-local-database-password` and
      `DJANGO_DEBUG=true` each raised `ImproperlyConfigured` with the expected
      message.
- [x] `.env.prod.example`, the release workflows and the observability stack are
      unchanged - PASS
      `git diff --quiet HEAD -- .env.prod.example .github observability
      compose.yaml config tests/compose/conftest.py
      tests/compose/compose.override.yaml Dockerfile docker-entrypoint.sh` is
      clean, and none of these paths is untracked or modified in `git status`.

Documentation:

- [x] README **Quick start** directly below the title and intro, with all items -
      PASS
      It is the first `##` section after the title and intro paragraph. It lists
      Docker with Compose v2, the one command, `http://localhost:8080/`, stop
      (`down`), wipe (`down -v`), and "**not for deployments**".
- [x] Every README and operator-guide instruction that copies `.env.example`
      works from a fresh clone - PASS
      README line 147 and operator guide line 61 (`Copy-Item .env.example .env`)
      ran successfully in PowerShell in the fresh clone, as did
      `Copy-Item .env.prod.example .env.prod`. For comparison, a clone of HEAD
      has no `.env.example`, and 3 default tests fail there for that reason.
- [x] Operator guide states `quickstart.env` is local-evaluation only and dev and
      production keep `.env` and `.env.prod` - PASS
      The new "Quick start for local evaluation" section says both. The
      Environments section adds that the quick start is not one of them.

Tests:

- [x] Default suite checks the git-tracking rules and `quickstart.env` contents -
      PASS
      `tests/test_quickstart.py` (17 tests) covers the ignore rules, `eol=lf`,
      the placeholders in `.env.example`, the required variables, no placeholder
      values, the six fixed values, the opening comment, and the docs.
- [x] Compose suite starts the stack from `quickstart.env` on an isolated project
      and a free loopback port, and checks health and the three URLs - PASS
      `tests/compose/test_quickstart_stack.py` uses project
      `recipe-cost-calculator-quickstart-itest` and the `127.0.0.1::8000`
      override. It checks that both services are `healthy` and that the three
      URLs return 200, and runs `down --volumes` before and after. No `*itest*`
      container or volume was left.
- [x] `python -m pytest` and `python -m pytest -m compose` both pass - PASS
      (with the known Issue 31 exception)
      The only default-suite failure is
      `tests/test_production_deployment.py::test_collected_static_asset_is_served_by_the_application`.
      Confirmed pre-existing: a clone of HEAD plus the original `.env.example`
      gives the same failure (405 passed, 1 failed). It fails only in the full
      run; run alone it passes, both at HEAD and with this change. It is out of
      scope here (Issue 31).

Not covered by automated tests (verified manually above; the Tests criteria do
not require them): persistence across `down` and `up`, `down -v` removing the
quick-start volume, isolation from a running dev or production stack, and the
line endings of a fresh Windows (`autocrlf`) clone end to end. The default test
checks the attribute and the working file's bytes, not a fresh clone.

Tests:

- `.venv/Scripts/python.exe -m pytest` (this repo): 422 passed, 1 failed (Issue
  31, pre-existing), 30 deselected
- `.venv/Scripts/python.exe -m pytest` (fresh clone): 422 passed, 1 failed (same
  test), 30 deselected
- `.venv/Scripts/python.exe -m pytest -m compose` (this repo): 30 passed, 423
  deselected
- `.venv/Scripts/python.exe -m pytest tests/test_quickstart.py` (fresh clone):
  17 passed
- `.venv/Scripts/python.exe -m pytest -m compose tests/compose/test_quickstart_stack.py`
  (fresh clone): 7 passed
- Baseline, clone of HEAD plus the original `.env.example`:
  `.venv/Scripts/python.exe -m pytest`: 405 passed, 1 failed (same test), 23
  deselected

## Closed by orchestrator

QA PASS on all acceptance criteria. The only `python -m pytest` failure is the pre-existing `test_collected_static_asset_is_served_by_the_application`, confirmed failing at the baseline and tracked in [Issue 31](issue31.md).
