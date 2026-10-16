# Issue 26: Rehearse a production rollback to an older release

Status: closed (2026-10-15)

## Goal

The rollback path from [Issue 24](issue24.md) is proven on this machine: deploying an older release tag to prod runs it with its own commit's `compose.yaml`, and rolling forward again restores the current release.

## Acceptance criteria

- [x] Before starting, the current prod release tag (`APP_VERSION` on the prod web container) and an older release tag present in the registry are recorded.
- [x] Running **Deploy** for `prod` with the older tag finishes green. Its log prints the older tag and the matching commit.
- [x] The prod web container then reports the older tag in `APP_VERSION`, and answers on `http://localhost:8001/health/` with 200.
- [x] If the older release was built before commit `9bdd779`, Prometheus still shows its release tag as `service_version`, not `latest`, `prod` or an empty value.
- [x] Running **Deploy** for `prod` with the recorded current tag restores it. `APP_VERSION` matches the recorded value and health returns 200.
- [x] The recipes listed on `http://localhost:8001/recipes/` are the same before the rollback, after it, and after rolling forward.
- [x] `docs/operator-guide.md`'s "Releasing and rolling back" section matches the steps actually used. Any step that differed is corrected.

## Out of scope

- Database migrations that can't run in reverse. Rolling back across a schema change is not covered. This rehearsal must use releases with the same migrations; check with `showmigrations`.

## Constraints

- Run this only after [Issue 25](issue25.md) has passed.
- Each Deploy run is an operator action and needs the user's approval.
- Take a database backup first, using the operator guide's backup procedure.
- Never print `deploy/.env.prod`.
- Change only `docs/operator-guide.md`, and only if a documented step was wrong.
- Do not add dependencies.

## Rehearsal (live), 2026-10-15

The user ran every step. The orchestrator gave the commands and read Prometheus (`:9090`) and git. Local time is UTC-5.

- **Migrations.** `git diff 6c30e73..HEAD` and `git diff c28a8f3..HEAD` touch no migration files, so all three releases share the same schema.
- **Backup first.**
  - Command: the operator guide's Backup commands with `--env-file .env.prod` on every `docker compose` call, run in `DEPLOY_PATH`.
  - Result: `backups\recipe_cost_calculator-20261015-145658.sql`, 33,384 bytes.
  - Finding 1: the guide's commands have no `--env-file`, so they back up **dev**.
- **Recorded before starting.**
  - Prod first reported `APP_VERSION=latest`, because the user had started it by hand with `docker compose --env-file .env.prod up -d`.
  - The user then ran **Deploy** `prod` with `20261015-194410-ef75e05`, and prod reported `APP_VERSION=20261015-194410-ef75e05`. That became the recorded current release.
  - Recipes: `asdas`, `caczxc`, `dfsd`.
- **First rollback target failed: `20261014-182432-6c30e73`.**
  - Deploy failed with "Bind for 0.0.0.0:8000 failed: port is already allocated" on `recipe-cost-calculator-prod-web-1`.
  - Cause: commit `6c30e73`'s `compose.yaml` publishes `"8000:8000"`. `WEB_PORT` (prod 8001) and `DEPLOYMENT_ENVIRONMENT` were only added in `9bdd779`. A pre-`9bdd779` release collides with dev on 8000, and the prod web container cannot start. Dev and the prod database were not affected.
  - Prod was restored by **Deploy** `prod` with `20261015-194410-ef75e05` (health 200).
  - Finding 2: releases built before `9bdd779` cannot be deployed to prod on this host. The criterion about "built before `9bdd779`" is therefore not applicable.
- **Rollback to `20261015-020111-c28a8f3` (includes `9bdd779`).**
  - Deploy green. Summary: "Deploying release 20261015-020111-c28a8f3 (commit c28a8f3f5706f36c23f8628d28d2f9c4db327860) to prod."
  - `APP_VERSION=20261015-020111-c28a8f3`; `http://localhost:8001/health/` 200.
  - Prometheus: prod `service_version="20261015-020111-c28a8f3"`. The user's view of `dfsd` was counted as `recipe_views_total{service_version="20261015-020111-c28a8f3",recipe="dfsd"}`.
  - Recipes: `asdas`, `caczxc`, `dfsd`.
- **Roll forward to `20261015-194410-ef75e05`.**
  - Deploy green. Summary: "Deploying release 20261015-194410-ef75e05 (commit ef75e05b53a83c0ad5e7393e7c121ed2829be456) to prod."
  - `APP_VERSION=20261015-194410-ef75e05`; health 200.
  - Recipes: `asdas`, `caczxc`, `dfsd`.

Docs changes needed in `docs/operator-guide.md`:

1. Backup: show how to back up prod (`--env-file .env.prod`, run from `DEPLOY_PATH`).
2. Releasing and rolling back: say that only releases that include `9bdd779` can be deployed to prod on this host, and name a way to check it (`git merge-base --is-ancestor 9bdd779 <sha>`). Say that a rollback must be checked for the same migrations. Say that prod must be started by Deploy or Promote, not by a manual `docker compose up`, so `APP_VERSION` names a release.

## Engineer comment

Changed only `docs/operator-guide.md`, to match the steps used in the live rehearsal:

- **Backup.** The commands now pass `--env-file .env.prod` on every `docker compose` call and say to run them from the `DEPLOY_PATH` folder, so they back up production. The text says the `--env-file` picks the environment, dev uses `--env-file .env`, and without it Compose reads `.env` and backs up dev.
- **Restore.** It had the same problem. Same fix: every `docker compose` call has `--env-file .env.prod`, it runs from `DEPLOY_PATH`, and the health check uses port `8001`. Dev uses `--env-file .env` and port `8000`.
- **Environments.** The sentence "every `docker compose` command targets dev as written" now names Backup and Restore as the exceptions.
- **Releasing and rolling back.**
  - Start production only through Deploy or Promote. A manual `docker compose --env-file .env.prod up -d` makes `APP_VERSION` read `latest`. The fix is to re-run Deploy with the release tag.
  - New "Before rolling back" checks:
    1. Take a production backup.
    2. Confirm the releases have the same migrations: `git diff --stat <old-sha> <current-sha> -- '*migrations*'` must print nothing.
    3. Confirm the older release includes `9bdd779`: `git merge-base --is-ancestor 9bdd779 <old-sha>; $LASTEXITCODE` must print `0`. The guide explains why: the older `compose.yaml` publishes `"8000:8000"`, which causes "port is already allocated".
  - If a Deploy fails, re-run Deploy with the previous release tag. Roll forward the same way.

Checked against git: `9bdd779` is an ancestor of `c28a8f3` (exit 0) and not of `6c30e73` (exit 1). The migrations diff between `c28a8f3` and `ef75e05` prints nothing.

## QA: PASS

- [x] Current prod release tag and an older registry tag recorded before starting - PASS
      Recorded current `20261015-194410-ef75e05` (after replacing the hand-started `latest`), older tags `20261014-182432-6c30e73` and `20261015-020111-c28a8f3`, and recipes `asdas`, `caczxc`, `dfsd`.
- [x] Deploy `prod` with the older tag finishes green and logs the tag and commit - PASS
      `20261015-020111-c28a8f3` green; summary names the tag and commit `c28a8f3f5706...`. The first target, `6c30e73`, failed for a recorded and explained cause (Finding 2).
- [x] Prod web reports the older tag and `:8001/health/` returns 200 - PASS
      `APP_VERSION=20261015-020111-c28a8f3`, health 200.
- [x] Pre-`9bdd779` release shows its tag as `service_version` - N/A, adequately documented
      The rehearsal shows why: `git show 6c30e73:compose.yaml` publishes `"8000:8000"`, so a pre-`9bdd779` release cannot run as prod on this host (port collision with dev). The guide now blocks this case with the ancestor check. For the release that did run, Prometheus showed `service_version="20261015-020111-c28a8f3"`.
- [x] Deploy `prod` with the recorded current tag restores it - PASS
      `APP_VERSION=20261015-194410-ef75e05`, health 200.
- [x] Recipes the same before, after rollback, after roll forward - PASS
      `asdas`, `caczxc`, `dfsd` at all three points.
- [x] `docs/operator-guide.md` matches the steps used; wrong steps corrected - PASS
      - Backup (lines 345-358) and Restore (lines 375-400): every `docker compose` call has `--env-file .env.prod`, run from `DEPLOY_PATH`, prod health on `8001`, dev variant (`.env`, `8000`) stated. This matches the backup actually taken. `.env.prod` sets `COMPOSE_PROJECT_NAME`, and `compose.yaml` defaults `IMAGE_TAG`, so `exec`/`cp` reach the prod project from `DEPLOY_PATH`. This is consistent with `deploy.yml` (`Set-Location $deployPath`, `--env-file $envFile`).
      - Before rolling back (lines 207-227): I ran the checks in PowerShell 5.1. `git merge-base --is-ancestor 9bdd779 c28a8f3; $LASTEXITCODE` printed `0`; with `6c30e73` it printed `1`. `git diff --stat c28a8f3 ef75e05 -- '*migrations*'` and `6c30e73 ef75e05` print nothing. As a sanity check, the same pathspec does match `calculator/migrations/*` files when diffed from the empty tree.
      - Start prod only through Deploy/Promote (lines 202-205) and re-run Deploy with the previous tag after a failed Deploy (lines 234-236) match what was done live.

Findings (non-blocking):

1. `docs/operator-guide.md:314` ("Database migrations": "first take a backup") and `docs/operator-guide.md:422` ("Update and rollback": "Run the backup procedure above") sit in sections whose commands target dev. The Backup procedure now backs up production as written, so an operator following those sections literally would back up prod instead of dev. A one-line pointer to the dev variant (`--env-file .env`) would remove the ambiguity.

Constraints: commit `1f2a29a` changes only `docs/operator-guide.md`. No env file was read or printed during QA. No container or workflow was run.

Tests: `.venv/Scripts/python -m pytest`: 406 passed, 23 deselected, 0 failed.

## Closed by orchestrator

QA PASS. The live rehearsal above passed. The "built before `9bdd779`" criterion is not applicable on this host, and the guide now blocks that case with the ancestor check.

Follow-up (non-blocking QA finding): the "Database migrations" and "Update and rollback" sections of `docs/operator-guide.md` point to the Backup procedure, which now targets production. Each needs a one-line pointer to the dev variant (`--env-file .env`).
