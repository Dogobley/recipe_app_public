# Issue 27: Deploy the observability stack through the pipeline, separate from the application, with dev and prod connected

Status: closed (2026-10-15)

## Goal

The operator deploys or updates the observability stack (collector, Prometheus, Loki, Tempo, Grafana) with one GitHub Actions run, without restarting dev or prod. Both application environments send telemetry to it, and Grafana shows `dev` and `prod` separately.

Today the stack in `observability/` already runs as its own Compose project (`observability`), but it is started by hand from the repository checkout, its config is bind-mounted from that checkout, and Grafana uses the committed default `admin` / `admin` credentials. Dev is already connected. Prod is connected by Issue 22's settings, which are verified live in [Issue 25](issue25.md).

## Acceptance criteria

Deployment:

- [x] A workflow **Deploy observability** can be run by hand from the Actions tab. It also runs on a push to `main` that changes files under `observability/`.
- [x] The workflow copies the stack's files from the commit it runs on to a fixed folder outside the runner's work directory, named by a repository variable (for example `OBSERVABILITY_PATH`), and starts the stack from there. Containers never bind-mount files from `actions-runner/_work`, which the runner cleans.
- [x] The run ends green only when every service is ready:
  - Prometheus `/-/ready`
  - Loki `/ready`
  - Tempo `/ready`
  - Grafana `/api/health`
  - the collector's metrics endpoint on `:8888`

  Otherwise it ends red and names the service that is not ready.
- [x] The Compose project name stays `observability`, so the existing volumes are reused. Metrics, traces and dashboards stored before a redeploy are still there after it. Check that a Prometheus query over the hour before the redeploy still returns data.
- [x] Running the workflow twice in a row with no changes succeeds both times and recreates no container the second time.

Separation from the application:

- [x] The prod and dev web containers have the same container ID and start time before and after an observability deploy.
- [x] With the observability stack stopped, dev (`:8000`) and prod (`:8001`) still answer `/health/` with 200 and serve the recipe list. The logs may show export errors, but no request fails. Starting the stack again resumes telemetry within two minutes, with no application restart.
- [x] The application's `compose.yaml` and the observability `compose.yaml` share no services, volumes or networks. The application reaches the collector only through `OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318`.

Credentials:

- [x] The Grafana admin user and password come from an untracked env file in the deploy folder, not from the committed `compose.yaml`. A committed example file lists the variable names with placeholder values.
- [x] If that env file or the password is missing, the workflow fails before changing any container. It must never fall back to `admin` / `admin`.
- [x] Grafana anonymous access and sign-up stay disabled.

Both environments connected:

- [x] After a deploy, and after viewing a recipe on each environment, `http://localhost:9090/api/v1/label/deployment_environment/values` lists both `dev` and `prod`. The business dashboard (<http://localhost:3000/d/recipe-business-metrics>) shows data for each one when selected alone.

Docs:

- [x] `observability/README.md` and `docs/operator-guide.md` describe:
  - the workflow and the repository variable
  - the env file and how to change the Grafana password
  - how to start and stop the stack by hand from the deploy folder
  - that stopping the stack never affects the application
- [x] `python -m pytest` passes.

## Out of scope

- Alert rules. These are in [Issue 28](issue28.md).
- Polling alerts and handing them to an agent. This is in [Issue 29](issue29.md).
- Running the stack on a different machine. Everything stays on this host, the same decision as in [Issue 24](issue24.md).
- Retention and storage sizing. The defaults stay.

## Constraints

- Run this only after [Issue 25](issue25.md) has passed, so prod is already sending telemetry and the "both environments" check means something.
- Follow the style of `.github/workflows/deploy.yml`: the self-hosted Windows runner, `shell: powershell`, and `$ErrorActionPreference = 'Stop'`. Don't pipe a native command into `Select-Object -First` and then check `$LASTEXITCODE` (see the bug reopened in [Issue 24](issue24.md)).
- Change only:
  - `observability/`
  - a new workflow under `.github/workflows/`
  - `docs/operator-guide.md`, `README.md`
  - tests under `tests/`
- Keep the image versions pinned.
- Never print or commit the Grafana env file.
- Creating the repository variable, the deploy folder's env file and the first workflow run are operator actions. Ask the user.
- Read `_docs/testing-guidelines.md` before writing tests. Do not add dependencies.

## Engineer comment

Implemented everything that can be done in code. The live criteria still need the operator (see below).

What changed:

- `.github/workflows/deploy-observability.yml` (**Deploy observability**). It runs by hand (`workflow_dispatch`) and on a push to `main` that changes `observability/**`, with a concurrency group so two runs never overlap. It uses the self-hosted runner and `shell: powershell` with `$ErrorActionPreference = 'Stop'` in every step, like `deploy.yml`. Steps:
  1. **Check the deploy folder and the Grafana credentials.** Reads the `OBSERVABILITY_PATH` repository variable and refuses a folder inside `actions-runner\_work` or the workspace. It requires `<OBSERVABILITY_PATH>\.env`, then resolves it with `docker compose config --format json` in memory (never printed; the password is `::add-mask::`ed). It fails with "No container was changed" when the file is missing, or when `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` is missing or empty, or the password is `admin` or the `replace-with-*` placeholder. This runs before any file is copied or any container changes.
  2. **Copy the stack's files.** Copies `observability/` from the checked-out commit to the deploy folder. A file is written only when its SHA-256 differs, so an unchanged redeploy rewrites no bind-mounted file. Files removed from `grafana/` are removed in the deploy folder too. `.env` is never touched. The step outputs which services' config files changed.
  3. **Start the stack.** Runs `docker compose --project-name observability up -d` from the deploy folder. There is no `--force-recreate`, `--build`, `--remove-orphans`, `down` or volume command. Compose does not recreate a container when only a bind-mounted file's content changes. So a service whose config file changed, and whose container ID is the same before and after `up`, gets `docker compose restart <service>`. Restart keeps the container ID. A second run with no changes therefore recreates and restarts nothing.
  4. **Wait for every service to be ready.** Gives every service a shared 5-minute deadline: Prometheus `/-/ready`, Loki `/ready`, Tempo `/ready`, Grafana `/api/health`, collector `http://localhost:8888/metrics`. On failure it emits `::error::<Service> is not ready: <url> did not answer 200.` for each service that is not ready, prints its last 50 log lines and exits 1.
  5. **Apply the Grafana admin password.** `GF_SECURITY_ADMIN_PASSWORD` only applies when Grafana creates a new database, and the existing `observability_grafana_data` volume still has admin/admin. So the workflow pipes the password to `grafana cli admin reset-admin-password --password-from-stdin` through `exec` (I checked that this flag exists in `grafana/grafana:13.2.4`). It then checks that `GET /api/user` accepts the configured user and password. This changes no container.
- `observability/compose.yaml`: Grafana now uses `GF_SECURITY_ADMIN_USER: ${GRAFANA_ADMIN_USER:?...}` and `GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:?...}`, and sets `GF_AUTH_ANONYMOUS_ENABLED: "false"` alongside `GF_USERS_ALLOW_SIGN_UP: "false"`. Compose itself refuses to start without the values, so there is no fallback to admin/admin even when the stack is started by hand. Images, ports, volumes and the project name `observability` are unchanged.
- `observability/env.example` (new, committed): `GRAFANA_ADMIN_USER=admin`, `GRAFANA_ADMIN_PASSWORD=replace-with-a-strong-grafana-password`. The real file is `.env` in the deploy folder. Compose reads it automatically for interpolation, so `docker compose up -d` / `down` work from the deploy folder with no extra flags. Naming: `.gitignore` already ignores `.env` at any depth (good, so `observability/.env` can never be committed by accident). It also ignores `.env.example`, which is why the example is called `env.example` instead of `observability/.env.example`. I did not change `.gitignore`. If you prefer the conventional `.env.example` name, the `.env.example` line would need to go from `.gitignore` (the root `.env.example` is tracked only because it was force-added).
- Docs: `observability/README.md` has new sections "Deploy with the pipeline", "Grafana credentials" (including how to change the password) and "Start and stop by hand" from the deploy folder, plus the statement that stopping the stack never affects the application. The alert-API examples no longer use `admin:admin`. I removed the "shared external network / `http://collector:4318`" alternative, because it contradicts the separation criterion. `docs/operator-guide.md` has a new "Observability stack" section covering the one-time setup, the deploy, the password change, manual start and stop, and isolation. `README.md` links to the workflow, the variable and the example.
- Tests: `tests/test_observability_deployment.py` (16 text-level tests) checks:
  - the triggers and the PowerShell style
  - that the Select-Object guard scans this workflow and it passes (the existing glob in `test_release_workflows.py` already covers it, and the new test asserts it explicitly)
  - the `OBSERVABILITY_PATH` copy, and that the stack only bind-mounts `./` paths
  - the project name, volumes and `--project-name observability` on every deploy-folder Compose call
  - no flags or commands that force recreation or remove containers, the hash-compare plus restart-only-if-kept logic, and pinned images
  - the five readiness URLs and the error that names the service
  - that the credentials are required and there is no admin/admin, that anonymous access and sign-up are off, and that the example has placeholders only and is not ignored
  - that the env-file and password checks come before the first `Copy-Item` and `up -d`, and that the password is masked, passed on stdin and never printed
  - that the app and stack Compose files share no services, volumes or networks (no `networks:`, `external:` or `network_mode`), and that both env templates point only at `http://host.docker.internal:4318`
  - that both docs cover the required topics

  Locally I also parsed every workflow step with the PowerShell parser. I dry-ran steps 1 and 2 against a scratch folder: missing file, missing password and `admin` password each fail; a valid file passes; the first copy writes everything; the second copy writes nothing; a changed `loki.yaml` and a stale dashboard map to `loki grafana`. No containers were involved.
- Result: `.venv/Scripts/python -m pytest` gives **394 passed, 23 deselected**.

Operator setup (not done by me):

1. Pick a fixed folder outside `actions-runner\_work`, for example `C:\Users\<you>\observability`, and create the repository variable `OBSERVABILITY_PATH` with that path.
2. Copy `observability\env.example` to `<OBSERVABILITY_PATH>\.env`. Set a real `GRAFANA_ADMIN_PASSWORD` and keep `GRAFANA_ADMIN_USER=admin`, because the existing Grafana volume's login is `admin` and the user name only applies to a new volume.
3. Run **Actions -> Deploy observability**.
   - Expect the first run to recreate all five containers once: the bind-mount source moves from the repository checkout to the deploy folder, and Grafana's environment changes. The volumes are kept.
   - From then on Grafana no longer accepts admin/admin.
   - The on-call engineer uses a service-account token (`ONCALL_GRAFANA_TOKEN`), so it is not affected.

Pending live checks (need the runner, Docker and the operator):

- [ ] The first run is green, and the stack runs from `OBSERVABILITY_PATH` (`docker inspect` the bind sources: none under `actions-runner/_work`).
- [ ] A second run with no changes is green, and no container ID or start time changed.
- [ ] Volumes are kept: a Prometheus query over the hour before the redeploy still returns data, and the dashboards are still there.
- [ ] Dev and prod web containers have the same ID and start time before and after an observability deploy.
- [ ] With the stack stopped (`docker compose down` from the deploy folder, never `-v`), `:8000` and `:8001` still return 200 on `/health/` and serve the recipe list. After `docker compose up -d`, telemetry resumes within 2 minutes with no app restart.
- [ ] A missing `.env` or password makes the run red before any container changes.
- [ ] Grafana rejects admin/admin and accepts the `.env` credentials. Anonymous access and sign-up are off.
- [ ] After viewing a recipe on each environment, `http://localhost:9090/api/v1/label/deployment_environment/values` lists `dev` and `prod`, and the business dashboard shows data for each one selected alone.
- [ ] Readiness failure path: the run names the service that is not ready (optional to provoke).

## QA: PASS

Verdict covers the criteria that can be checked without the operator's real
workflow run. Live criteria on the real stack are NOT VERIFIED (pending
operator setup of `OBSERVABILITY_PATH`, the deploy folder's `.env` and the
first run); they are not failures. Workflow steps were extracted from
`.github/workflows/deploy-observability.yml` and run unchanged in
`powershell.exe` 5.1 (stdout/stderr redirected, as on the runner) against a
scratch checkout and deploy folder with a dummy `.env`; steps 3-5 only had
`--project-name observability` -> `qa27` and the host ports remapped (override
file `ports: !override`, 1xxxx ports) so the running `observability` project
was never touched. The `qa27` project was removed with `down -v` afterwards.
The real `observability`, dev and prod containers had the same IDs and start
times before and after QA.

Deployment:

- [x] Workflow **Deploy observability** runs by hand and on push to `main`
      changing `observability/**` - PASS (`workflow_dispatch` + `push` with
      `branches: [main]`, `paths: observability/**`; self-hosted,
      `shell: powershell`, `$ErrorActionPreference = 'Stop'` in every step,
      no `Select-Object -First` on native output).
- [x] Copies the stack from the commit to the `OBSERVABILITY_PATH` folder and
      starts it from there; no bind mounts from `actions-runner/_work` - PASS
      (code + isolated run). Unset variable, a path under
      `actions-runner\_work` and a path inside `GITHUB_WORKSPACE` each exit 1
      with an `::error::`. First copy wrote all 11 files; second copy wrote
      nothing ("already up to date", names/mtimes/sizes identical); a changed
      `loki.yaml` and a stale dashboard gave `restart_services=loki grafana`
      and the stale file was removed; `.env` hash and mtime unchanged across
      all copies. `qa27` Grafana's bind source was the scratch deploy folder.
      Live check that the real stack's bind sources moved off the checkout:
      NOT VERIFIED (real stack still mounts from the repository checkout, as
      expected before the first run).
- [x] Green only when every service is ready, otherwise red naming the
      service - PASS (isolated). Step 4 against `qa27`: all five URLs
      (Prometheus `/-/ready`, Loki `/ready`, Tempo `/ready`, Grafana
      `/api/health`, collector `:8888/metrics`) answered 200, exit 0. With
      `qa27` Tempo stopped (deadline shortened to 20 s in my copy only):
      exit 1, `::error::Tempo is not ready: http://localhost:13200/ready did
      not answer 200.`, the other four reported ready.
- [ ] Project name stays `observability`, volumes reused, Prometheus data
      from the hour before a redeploy still queryable - NOT VERIFIED (live).
      Code: `name: observability` in compose, `--project-name observability`
      on every deploy-folder call, no `down`, `-v`, `--force-recreate`,
      `--remove-orphans` or volume command; `docker compose config` from the
      deploy folder resolves `name: observability`. Isolated: Grafana was
      recreated (env change) and its existing `qa27_grafana_data` still held
      the seeded admin/admin login, so the volume was reused.
- [x] Two runs in a row with no changes both succeed, second recreates
      nothing - PASS (isolated). Second copy + start + ready + password
      steps all exit 0; `docker inspect` ID, StartedAt and RestartCount of
      all five `qa27` containers identical before and after. A run with one
      changed config restarted only `loki` (same container ID). Live repeat
      on the real stack: NOT VERIFIED.

Separation from the application:

- [ ] Dev/prod web containers keep ID and start time across an observability
      deploy - NOT VERIFIED (live). Code: every Compose call in the workflow
      carries `--project-name observability` and runs from the deploy
      folder; nothing references the app projects. During this QA the
      `deploy-web-1` and `recipe-cost-calculator-prod-web-1` IDs/start times
      did not change while `qa27` was deployed repeatedly.
- [ ] With the stack stopped dev/prod still answer `/health/` and serve
      recipes; telemetry resumes within 2 minutes - NOT VERIFIED (requires
      stopping the real stack).
- [x] App and observability compose share no services, volumes or networks;
      app reaches the collector only via
      `OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318` - PASS
      (app: `db`/`web`/`postgres_data`; stack: five services, four
      `*_data` volumes; neither declares `networks`, `external` or
      `network_mode`; `.env.example` and `.env.prod.example` point only at
      `host.docker.internal:4318`).

Credentials:

- [x] Grafana admin user/password from an untracked env file; committed
      example with placeholders - PASS. `compose.yaml` uses
      `${GRAFANA_ADMIN_USER:?}` / `${GRAFANA_ADMIN_PASSWORD:?}`;
      `observability/env.example` is tracked and not ignored;
      `observability/.env` is ignored (`.gitignore:6`). `docker compose -p
      qa27 up -d` with no `.env` failed (exit 15, "required variable
      GRAFANA_ADMIN_USER is missing a value") and created no container,
      volume or network.
- [x] Missing env file or password fails before any container change, never
      admin/admin - PASS. Step 1 exit 1 with `::error::... No container was
      changed.` for: missing folder, missing `.env`, no password line, empty
      password, `admin`, `Admin`, the `replace-with-*` placeholder, empty
      user; `DEPLOY_PATH` not written so later steps do not run. A valid
      CRLF `.env` passed. The dummy password appeared in output only on the
      `::add-mask::` line. Step 5 on a volume seeded with admin/admin:
      `reset-admin-password --password-from-stdin` succeeded, `/api/user`
      then returned 401 for admin/admin and 200 for the `.env` password.
- [x] Anonymous access and sign-up disabled - PASS (`qa27`: unauthenticated
      `/api/search`, `/api/user`, the dashboard API all 401;
      `POST /api/user/signup` 401 "User signup is disabled";
      `/api/admin/settings` shows `auth.anonymous.enabled=false`,
      `users.allow_sign_up=false`).

Both environments connected:

- [ ] `deployment_environment` lists `dev` and `prod` after a deploy and the
      business dashboard shows each - NOT VERIFIED (live; the workflow
      does not change collector/Prometheus config or the app's endpoint).

Docs:

- [x] `observability/README.md` and `docs/operator-guide.md` describe the
      workflow and variable, the env file and password change, manual
      start/stop from the deploy folder, and that stopping never affects the
      application - PASS (`README.md` links them too).
- [x] `python -m pytest` passes - PASS.

Observation (not a criterion failure): the copy step mirrors deletions only
under `grafana/`; a top-level file removed from `observability/` stays in the
deploy folder (harmless, Compose references files explicitly).

Tests: `.venv/Scripts/python -m pytest`, 394 passed, 23 deselected;
`.venv/Scripts/python -m pytest tests/test_observability_deployment.py tests/test_release_workflows.py`,
27 passed.


## Engineer comment (fix after first live run)

**Symptom.** In the first live run (push of 07b44c0), **Apply the Grafana admin password** went red with "Grafana rejected the admin user 'admin'". Grafana's log showed `[password-auth.invalid] invalid password`. Afterwards neither the `.env` password nor admin/admin worked.

**Root cause.** Reproduced in Windows PowerShell 5.1 against a throwaway `grafana/grafana:13.2.4` Compose project (`issue27repro`, port 13000, no volume; removed afterwards):

- The runner runs `chcp 65001` before every step, which I confirmed in `actions-runner/_diag/Worker_*.log`. Under that code page, `[Console]::InputEncoding` is UTF-8 *with* a BOM preamble.
- Windows PowerShell then prepends the BOM to whatever it pipes into a native command. Setting `$OutputEncoding` to BOM-less UTF-8 makes no difference.
- Probe `'Probe$x#1' | docker compose exec -T grafana od -c`:
  - at the default code page: `P r o b e $ x # 1 \r \n`
  - after `chcp 65001`, as on the runner: `357 273 277 P r o b e $ x # 1 \r \n`
- So `reset-admin-password --password-from-stdin` stored BOM + password. The check then sent the password without the BOM and got 401.
- Grafana's CLI is not the problem. It strips the trailing `\r\n` and keeps every other character exactly (tested: leading and trailing spaces, tabs, backslash, `$`, `#`, `%`, quotes).
- A plain `System.Diagnostics.Process` with redirected stdin has the same flaw. .NET writes `Console.InputEncoding`'s preamble when it creates the stdin writer, which I reproduced.

Two more ways the password could differ from what the operator wrote, also reproduced against Compose 2.28:

- `docker compose config` writes every literal `$` as `$$` in its output. The step read `$$` while Grafana's `GF_SECURITY_ADMIN_PASSWORD` received `$`.
- Compose's `.env` rules:
  - an unquoted `pa$word` becomes `pa`, with a "variable is not set" warning;
  - `"pa$word"` interpolates too;
  - `'pa$word'` and `pa$$word` give `pa$word`;
  - an unquoted `with space #1` becomes `with space`.

Repeated failed logins also trip Grafana's lockout (5 failures within 5 minutes). It answers 401 with "too many consecutive incorrect login attempts". So after the live failure plus manual admin/admin attempts, the real Grafana may refuse logins for up to 5 minutes.

**Fix** (`.github/workflows/deploy-observability.yml`):

- **Password reset.**
  - It no longer uses `$password | docker ...`.
  - A small `Invoke-Native` helper starts `docker` through `System.Diagnostics.Process`, with BOM-less UTF-8 set as `[Console]::InputEncoding` only while the process starts.
  - It writes the exact UTF-8 bytes of `password + "\n"` to stdin's base stream and decodes stdout/stderr as UTF-8, so the result does not depend on the code page.
  - The password is still never on a command line or printed, and it stays `::add-mask::`ed.
- **Value read from Compose.** In both steps, the value read from `docker compose config --format json` gets `.Replace('$$', '$')`, so the step uses exactly the value Grafana receives.
- **`.env` pre-check.** It runs before Compose and before any container changes, reading the raw line in memory without printing it. It rejects a password where Compose would silently change the value:
  - an unescaped `$` in an unquoted or double-quoted value. The error says to write `$$` or single-quote the value.
  - an unquoted value containing ` #`. The error says to single-quote it.
- **Accurate errors.** Grafana answers 401 for every login failure. So the step reads only Grafana's log line for this `/api/user` request (`--since` the check, last `status=401` line) and reports one of:
  - "temporarily blocked logins … wait 5 minutes";
  - "Grafana has no user named '<user>'" (`identity.not-found`);
  - "Grafana has the user '<user>' but rejected the password just applied … nothing about the user name is wrong" (`password-auth.invalid`);
  - otherwise a generic 401 message.
- **Docs.** `observability/env.example`, `observability/README.md` and `docs/operator-guide.md` explain the `$$` / single-quote and ` #` rules, and the README lists the new error cases.

**Reproduction after the fix.** The exact step script, with project name and port swapped, ran against the throwaway Grafana, both under `chcp 65001` (via `cmd /c`, as the runner does) and at the default code page. Each password was then checked with an independent login using the intended password. All 7 cases were green with login 200 in both modes:

- `Plain-pass1`
- `'with space #1'`
- `pct%amp&<>!`
- `q'uo"te1`
- `d$$llar$$1` (meaning `d$llar$1`)
- `'single$quoted1'`
- a non-ASCII `nñandú-pw1`

Before the fix, under `chcp 65001`, the same cases failed. The error classification was also tested: an unknown user gave "has no user named", a deliberately wrong stored password gave "rejected the password just applied", and a lockout gave "temporarily blocked".

**Tests** (in `tests/test_observability_deployment.py`, now 28 tests, 12 of them new):

- Text checks:
  - the password is not piped, and is sent as bytes with the BOM-less input encoding;
  - the password is not in any `Invoke-Native` arguments;
  - `$$` is undone in both steps;
  - the three error causes;
  - the pre-check comes before `docker compose`;
  - `env.example` explains quoting.
- Windows-only tests, skipped elsewhere:
  - the step's own `Invoke-Native` function runs under `chcp 65001` and sends `Pa$s #%&'"ñé-1\n` to a Python stdin echo, which must receive exactly those UTF-8 bytes. With the fix removed it fails on `\xef\xbb\xbf`.
  - the credentials pre-check runs on temporary `.env` files with docker deliberately off PATH. It must reject `pa$word-1`, `"pa$word-1"` and `with space #1` before Compose, without echoing the value, and accept `pa$$word-1`, `'pa$word #1'` and `"with space #1"`.
- `.venv/Scripts/python -m pytest`: **406 passed, 23 deselected**.

**What I did not touch.** The running `observability` project and its volumes, the operator's `observability-deploy\.env` (not read), the app containers, and prod. I did not push or run the workflow.

**Next live step (operator).**
1. If the password in `observability-deploy\.env` contains `$` (unescaped and not single-quoted) or an unquoted ` #`, adjust it as above. Otherwise the next run stops early with a clear error.
2. Wait at least 5 minutes after the last failed login.
3. Re-run **Deploy observability**. It resets the real Grafana admin password to the `.env` value, which recovers the current unknown-password state, then verifies the login.

## QA (re-check after live fix): PASS

Re-verified commit 1beda6a. The method was the same as before. Workflow steps were taken from `.github/workflows/deploy-observability.yml` and run unchanged in `powershell.exe` 5.1 through a `cmd` launcher. The launcher ran `chcp 65001` first, as the runner does, or kept the default code page (850). Steps 3-5 only had the project changed to `qa27` and the ports remapped through an override file. They ran against a throwaway `qa27` stack whose `grafana/grafana:13.2.4` volume was seeded with admin/admin, the same as the real volume before the first run.

Afterwards `qa27` was removed with `down -v`: 0 containers, volumes and networks left. Scratch files were deleted. The real `observability`, dev and prod containers had the same IDs and start times before and after. I did not read the operator's `observability-deploy\.env`.

Live fix:

- **Original failure reproduced.** I ran the 532567a password step under `chcp 65001`. Grafana stored BOM + password: login with the exact password got 401, login with U+FEFF + password got 200. The step then reported the wrong cause, "Grafana rejected the admin user 'admin' ... keep the existing admin login name". The same old step at the default code page worked (200), which confirms the code-page root cause.
- **Fix works.** I ran the new step under `chcp 65001` with the same password. The exact password got 200, BOM + password got 401 and admin/admin got 401.
- **Password matrix: PASS.** Every value below passed step 1, `up`, and the password step. Afterwards Grafana accepted the intended value (200), and admin/admin got 401 at the end. The cases were split between 65001 and the default code page.

  | Raw value in `.env` | Intended password |
  | --- | --- |
  | `pa$$word` | `pa$word` |
  | `'pa$word'` | `pa$word` |
  | `'pa$$word'` | `pa$$word` |
  | `'pa #word'` | `pa #word` |
  | `"pa #word2"` | `pa #word2` |
  | `pa#word` | `pa#word` |
  | `100%pa%PATH%ss` | `100%pa%PATH%ss` |
  | `ab"c'd` | `ab"c'd` |
  | `'two  words here'` | `two  words here` |
  | `'contraseña€ü'` | `contraseña€ü` |
  | `Ñandú-密码-x` | `Ñandú-密码-x` |
  | `'S$e #c"r%e t€'` | `S$e #c"r%e t€` |

  I also had step 1 dump the value it resolved, in my scratch copy only. It matched the intended value in every case, so the `$$` un-doubling is correct.
- **Early `.env` check: PASS.** Each of these exits 1 in step 1 with "contains a $ ..." or "space followed by # ..." and "No container was changed": `pa$word`, `pa${HOME}x`, `"pa$word"`, `export GRAFANA_ADMIN_PASSWORD=pa$word`, `pa #word`, and a tab before `#`. `DEPLOY_PATH` is not set, so no later step runs. No output repeated the value.
- **The three error messages are accurate: PASS.**
  - Lockout: after more than 5 failed logins, the step said "Grafana temporarily blocked logins for 'admin' ... Wait 5 minutes", and Grafana's log showed "too many consecutive incorrect login attempts". After 5.5 minutes without failures the same runs passed.
  - Unknown user: `GRAFANA_ADMIN_USER=nobody` gave "Grafana has no user named 'nobody' ...".
  - Wrong password: I prepended a BOM to the bytes in my scratch copy only. The step said "Grafana has the user 'admin' but rejected the password just applied ...". The unmodified step then recovered it (200).
- **Password never on a command line or in output: PASS.**
  - A poller logged every Windows process command line every 150 ms during the runs, 62 reset invocations in all. The `docker`/`docker-compose.exe` calls were `compose --project-name qa27 exec -T grafana grafana cli admin reset-admin-password --password-from-stdin`, with no value. No `powershell`/`cmd`/`docker` command line held any test password; the only hits were my own test harness.
  - Every step output contained the passwords only on the `::add-mask::` line. That line was valid UTF-8 for non-ASCII values, so the runner can mask them.
- Observation, not a criterion failure: a value with text after the closing quote, such as `'pa$word'X`, is resolved by Compose to `pa$word` without any warning, and the early check allows it. The docs say to wrap the whole value, so this needs a malformed `.env`.

Criteria:

- [x] Workflow can be run by hand and runs on a push to `main` under `observability/**` - PASS (unchanged).
- [x] Copies to `OBSERVABILITY_PATH` and runs from there, never bind-mounting from `_work` - PASS (isolated).
  - Changing `prometheus.yml` plus adding a stale dashboard gave `restart_services=prometheus grafana`. Both restarted with the same container IDs, and the stale file was removed.
  - An unchanged copy writes nothing. `.env` hash unchanged.
  - Live: the orchestrator recorded that the first live run recreated the containers from the deploy folder.
- [x] Green only when every service is ready, and names the service that is not - PASS (isolated).
  - All five URLs ready: exit 0.
  - `qa27` Loki stopped: exit 1 with `::error::Loki is not ready: http://localhost:13100/ready did not answer 200.`
  - Live: readiness passed on the first run (orchestrator).
- [ ] Project name `observability` kept, volumes reused, data from the hour before still there - NOT VERIFIED.
  - The first live run kept the volumes (orchestrator), but the Prometheus query over the previous hour has not been checked.
  - Isolated: the Grafana volume survived the recreate (the seeded login was still present).
- [x] Second run with no changes succeeds and recreates nothing - PASS (isolated). I ran the full run (steps 1-5) twice. Both exited 0, and the second left the container IDs, start times and restart counts unchanged. Not yet repeated live.
- [ ] Dev and prod web containers keep the same ID and start time across a deploy - NOT VERIFIED as a before/after pair here. The orchestrator recorded that the app containers were unchanged on the first live run, and the code targets only `--project-name observability`.
- [ ] Apps keep serving `/health/` and recipes with the stack stopped, and telemetry resumes within two minutes - NOT VERIFIED (live).
- [x] The two compose files share no services, volumes or networks, and the endpoint is only `host.docker.internal:4318` - PASS (unchanged).
- [x] Credentials come from the untracked `.env`, with a committed example - PASS. `env.example` now explains the quoting rules.
- [x] A missing env file or password fails before any container changes, never admin/admin - PASS.
  - Missing `.env`, no password line, empty password and `admin` each exit 1 in step 1, under 65001.
  - The new early check is above.
  - After a deploy, admin/admin gets 401.
- [x] Anonymous access and sign-up disabled - PASS. Unauthenticated `/api/search` got 401, sign-up got 401, and the settings show `false` / `false`.
- [ ] `dev` and `prod` both in Prometheus, and the dashboard shows each - NOT VERIFIED (live).
- [x] Docs cover the workflow, the `.env`, the password change, manual start and stop, and isolation - PASS. The README and operator guide now also cover the `$`/` #` quoting and the three login failure causes.
- [x] `python -m pytest` passes - PASS.

Tests:

- `.venv/Scripts/python -m pytest`: 406 passed, 23 deselected.
- `.venv/Scripts/python -m pytest tests/test_observability_deployment.py tests/test_release_workflows.py`: 39 passed.

## Live check, 2026-10-15: PASS

The user ran the workflows and the stop/start steps. The orchestrator read Prometheus (`:9090`), which is read-only and does not touch prod. Times are local (UTC-5).

- **Password fix live.** The push run of `1beda6a`/`d1b8cc6` ended green, and the user logged in to Grafana as `admin` with the password from `observability-deploy\.env`.
- **Second run with no changes recreates nothing.** The user ran **Deploy observability** by hand and listed the containers before and after. It was green. All 9 IDs were identical, and every uptime only increased:
  - observability: grafana `60d50f7548a0`, collector `da8853a29d22`, prometheus `1c1b4ea33d14`, loki `f5c3adee8c95`, tempo `96d12b063f14`
  - app: prod web `521e7ba8177d`, prod db `7b468c918073`, dev web `dc05875f4cae`, dev db `36d5581553fa`
- **App containers untouched by observability deploys.**
  - Prod web `521e7ba8177d`, prod db and dev db have kept the same IDs since before the first live run.
  - Dev web changed once (`df09c8436fd6` to `dc05875f4cae`), when Build redeployed dev for the push of `1beda6a`/`d1b8cc6`. Build runs on every push to `main`, so that was not the observability deploy.
- **Grafana recreated after the password change.** Grafana's ID changed (`e7d91c1544b4` to `60d50f7548a0`) after the user changed `GRAFANA_ADMIN_PASSWORD` in the `.env`. That value is part of Grafana's container config, so Compose recreated only Grafana.
- **Stored data kept.** The Prometheus containers were created at 04:46:35Z in the first live run. Prometheus still returns `dev` series from 2026-10-14 14:38 and `prod` series from 2026-10-14 20:48, both before that recreate.
- **Apps unaffected while the stack is stopped.**
  - `docker compose --project-name observability stop`
  - `http://localhost:8000/health/` and `http://localhost:8001/health/` both answered OK.
  - The recipe pages loaded on both environments.
- **Telemetry resumes.**
  - The user ran `docker compose --project-name observability start` at 14:34:28.
  - Prometheus had fresh `dev` and `prod` samples at 14:35:15, under 1 minute later, with no application restart.
  - The user saw "Recipe views per recipe" with points at 14:37:00.
- **Both environments connected.**
  - `/api/v1/label/deployment_environment/values` returned `["dev","prod"]`.
  - The dashboard's recipe-views query returns series for `deployment_environment="dev"` alone (recipe `asdas`) and for `"prod"` alone (`dfsd`, `caczxc`).

Observation (not a criterion failure): changing the Grafana password in the `.env` recreates the Grafana container. Its data is kept in the volume.

## Closed by orchestrator

QA (re-check) PASS on all code criteria, and the live check above passed.
