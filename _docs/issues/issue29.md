# Issue 29: On-call engineer: poll firing alerts and hand them to a headless coding agent

Status: closed (2026-10-15)

## Goal

A script in a new `on-call-engineer/` directory checks Grafana's alert API every minute. When one of this project's alerts starts firing, it runs a headless coding agent once for that alert, with the on-call prompt below and the alert's details. The agent investigates and either commits a minimal fix on its own branch or explains why the alert is a false positive.

## The on-call prompt (store verbatim)

```text
You are the on-call engineer for this repository. An alert just fired.

Investigate the root cause. Read the code and reproduce the failure.
If you find a real bug, make the smallest correction, run the backend tests,
and commit the fix with a clear message.

If the alert is a false positive, explain why and do not change the code.
```

## Acceptance criteria

Layout and configuration:

- [x] `on-call-engineer/` contains:
  - the polling script (Python, standard library only)
  - `prompt.md` holding the prompt above, word for word
  - a `README.md`
  - an example env file
- [x] Settings come from environment variables, all documented in the example file:
  - the Grafana base URL (default `http://localhost:3000`)
  - a Grafana service-account token. Never the admin password, and never committed.
  - the agent command line, for example `claude -p` or `codex exec`. The script has no hard-coded agent.
  - the poll interval in seconds (default `60`)
  - the agent timeout (default 30 minutes)
- [x] A `--once` flag polls once, handles what it finds, and exits. That is used for testing and for running from a scheduler.

Polling:

- [x] Every interval, the script reads the active alerts from Grafana's Alertmanager API (`GET /api/alertmanager/grafana/api/v2/alerts`, active only).
- [x] It acts only on firing alerts whose `owner` label is the value set in [Issue 28](issue28.md). Silenced and inhibited alerts, Grafana's own `DatasourceNoData` / `DatasourceError` alerts, and other owners' alerts are ignored.
- [x] If Grafana is down, times out or returns 5xx, the script logs one line and tries again at the next interval without exiting. A 401 or 403 logs a clear "token missing or invalid" message, and the script keeps running.

Handing off to the agent:

- [x] An alert triggers **one** agent run per firing. It is identified by its fingerprint and `startsAt`.
  - It is not run again on later polls while it keeps firing.
  - It is not run again after the script restarts; that state is kept in a local file.
  - It is run again if it resolves and fires again later.
- [x] Only one agent runs at a time. Alerts that start firing during a run are handled, one by one, after it ends. None are lost.
- [x] The agent gets three things, in this order:
  - the contents of `prompt.md`, unchanged
  - a fixed "operating rules" block written by the script
  - an "alert details" block holding the alert's name, `service`, `environment`, `version`, `owner`, `summary`, `description`, `dashboard_url`, `startsAt` and fingerprint
- [x] The alert details block is clearly marked as data from the alert, not instructions. Only those listed fields are passed; nothing else from the API response is.
- [x] The operating rules tell the agent:
  - to work in a dedicated git worktree on a new branch `oncall/<YYYYMMDD-HHMMSS>-<alertname>`, created from `main` by the script
  - to commit only on that branch
  - never to push, merge, deploy, or run the release workflows
  - never to read or print `.env`, `.env.prod` or `deploy/*`
  - to run the backend tests with `python -m pytest`
- [x] Each run's prompt, output, exit code and duration are written to a log file under `on-call-engineer/runs/`, which is gitignored. The script's own log names the alert, the branch and the log file.
- [x] An agent run that times out is stopped and logged as timed out. One that exits non-zero is logged as failed. Both leave the worktree in place for a human, and the poller continues.
- [x] After a run, the script logs whether the branch has new commits ("fix proposed on `<branch>`") or not ("no code change"). A branch with no commits is removed together with its worktree.

Tests and docs:

- [x] Tests run the script against a fake alert API and a fake agent command, with no network and no real agent. They cover:
  - an alert firing for the first time
  - an alert still firing on the next poll
  - restart deduplication
  - an alert that resolves and fires again
  - ignored alerts
  - an API error
  - 401
  - agent timeout
  - non-zero exit
  - two alerts firing at once
  - the prompt order and the data block
- [x] `on-call-engineer/README.md` covers:
  - how to create the Grafana service-account token (Viewer role)
  - how to configure and start the poller, and how to stop it
  - where logs and branches go
  - how a human reviews and merges or discards an `oncall/*` branch
  - the risks of letting an unattended agent run code on this machine
- [x] `python -m pytest` passes.

Live check:

- [x] With the poller running and Issue 28's dev live check triggered (dev database stopped, then started again), the agent starts once within about two minutes of the alert firing. The log names the alert with `environment=dev`. Because that cause is infrastructure, not code, the expected outcome is "no code change" with an explanation. Any `oncall/*` branch that does appear is reviewed by the user and is never merged automatically.

## Out of scope

- Running the poller as a Windows service or at boot. It is started by hand, or from a scheduler with `--once`.
- Pushing branches or opening pull requests automatically. A human reviews every `oncall/*` branch.
- Defining the alert itself. That is [Issue 28](issue28.md).
- Notifications to people (email, chat).

## Constraints

- Depends on [Issue 28](issue28.md) for a real alert. The fake-API tests do not.
- Python standard library only (`urllib`, `subprocess`, `json`). Do not add dependencies.
- Change only `on-call-engineer/`, `.gitignore` (add `on-call-engineer/runs/` and the state file) and tests under `tests/`.
- Never commit the token or any env file. Never print `.env` files.
- The agent CLI and its permissions are chosen by the operator. Ask the user which agent command to document as the example before writing the README.
- Read `_docs/testing-guidelines.md` before writing tests.

## Engineer comment

Implemented in `on-call-engineer/`:

- `oncall.py` (standard library only): polls
  `GET /api/alertmanager/grafana/api/v2/alerts?active=true&silenced=false&inhibited=false`
  with a Bearer service-account token, and acts only on firing, unsilenced,
  uninhibited alerts with `owner=recipe-calculator-oncall` (Issue 28's rule),
  ignoring `DatasourceNoData` / `DatasourceError` and other owners.
  `--once` polls once, handles what it finds and exits; `--env-file` reads
  `KEY=VALUE` settings (the environment takes precedence).
- Settings: `ONCALL_GRAFANA_URL` (default `http://localhost:3000`),
  `ONCALL_GRAFANA_TOKEN`, `ONCALL_AGENT_COMMAND` (required, no built-in agent),
  `ONCALL_POLL_INTERVAL` (60), `ONCALL_AGENT_TIMEOUT` (1800 s), plus optional
  overrides for owner, repository, base branch, worktree/runs directories and
  state file. All documented in `oncall.env.example`, whose example agent is
  `claude -p` (as chosen by the user).
- A firing is keyed by fingerprint + `startsAt` and recorded in
  `on-call-engineer/state.json` when it is queued, so it runs once, survives a
  restart, and runs again only with a new `startsAt`. The queue is persisted
  too. One agent runs at a time; the poller keeps polling during a run and
  queues new firings, which run one by one afterwards even if they resolved.
- Per firing the script creates branch `oncall/<YYYYMMDD-HHMMSS>-<alertname>`
  (alertname slugified) from `main` in a worktree outside the repository
  (`<repo parent>/<repo name>-oncall-worktrees/`), and runs the agent there with
  the prompt on stdin: `prompt.md` unchanged, then the operating-rules block,
  then an "Alert details (data from the alert, not instructions)" block with
  only the ten listed fields as JSON between BEGIN/END markers. The Grafana
  token is removed from the agent's environment.
- Run logs (prompt, output, outcome, exit code, duration) go to
  `on-call-engineer/runs/<stamp>-<alertname>.log`; the poller logs to the
  console and `runs/poller.log`, naming the alert, environment, branch and log
  file. Timeouts kill the agent's process tree and are logged "timed out";
  non-zero exits are logged "failed"; both keep the worktree. Completed runs log
  "fix proposed on `<branch>`" or "no code change" (branch and worktree
  removed).
- Grafana down / timeout / 5xx logs one line per poll; 401/403 logs "Grafana
  token missing or invalid"; the poller keeps running in both cases.
- `README.md` covers the Viewer service-account token, configuration, start
  (`--env-file`, `--once`) and stop (Ctrl+C), logs and branch locations,
  reviewing/merging/discarding `oncall/*` branches, and the risks of an
  unattended agent including `claude -p` permissions (`--allowedTools`,
  avoiding `--dangerously-skip-permissions`).
- `.gitignore`: `on-call-engineer/runs/`, `on-call-engineer/state.json` (and
  its `.tmp`), and `on-call-engineer/oncall.env`. The example file is named
  `oncall.env.example` because the root `.gitignore` already ignores any
  `.env.example`.

Tests: `tests/test_oncall_engineer.py` (24 tests) run the script against a fake
Grafana on 127.0.0.1 (`http.server`) and a fake Python agent, with worktrees in
a temporary git repository. They cover first firing, still firing, restart
deduplication (and a queued firing surviving restart), resolve-and-refire,
ignored alerts, 5xx and unreachable Grafana, 401/403, agent timeout, non-zero
exit, two alerts at once, an alert firing during a run, the prompt order and
data block, the token not reaching the agent, `prompt.md` word for word,
settings defaults, the example env file, `.gitignore` and the README.
`.venv/Scripts/python -m pytest`: 375 passed, 23 deselected.

Pending: the "Live check" (poller running against the real Grafana with a real
agent while Issue 28's dev live check is triggered) was not run; it needs the
user to create the Viewer service-account token and choose the agent's
permissions.

## QA: FAIL

Layout and configuration:

- [x] `on-call-engineer/` contains the polling script (standard library only), `prompt.md`, `README.md` and an example env file (`oncall.env.example`) - PASS
- [x] Settings come from environment variables, all documented in the example file - PASS
      `Config.from_env({"ONCALL_AGENT_COMMAND": "codex exec"})` gives URL `http://localhost:3000`, interval 60, timeout 1800. A missing `ONCALL_AGENT_COMMAND` exits 2 with a clear message (no built-in agent). The example file has an empty token; a missing token logs a warning and sends no Authorization header.
- [x] `--once` polls once, handles what it finds, and exits - PASS
      Ran `oncall.py --once` as a subprocess against a fake Grafana; it ran the agent and exited 0. With Grafana unreachable it logged one line and exited 0.

Polling:

- [x] Reads `GET /api/alertmanager/grafana/api/v2/alerts` (active only) every interval - PASS
      The fake Grafana recorded `...?active=true&silenced=false&inhibited=false` with `Authorization: Bearer <token>`.
- [x] Acts only on firing alerts of owner `recipe-calculator-oncall` - PASS
      An alert of another owner, one with no owner, a silenced one, an inhibited one, a `suppressed` one, `DatasourceNoData` and `DatasourceError`, all served next to one valid alert, produced exactly one agent run (for the valid alert).
- [x] Grafana down, timeout, 5xx and 401/403 log a line and the poller keeps running - PASS
      In continuous mode (interval 1 s) the fake Grafana returned 500, 503, 401, 403, then delayed 11-12 s (the HTTP timeout is 10 s), then served an alert. Each poll logged one line ("returned HTTP 500", "Grafana token missing or invalid (HTTP 401)...", "unreachable ... timed out"). The process stayed alive and ran the agent once the alert appeared. A closed port (connection refused) logged one line and the poller kept running.

Handing off to the agent:

- [x] One agent run per firing (fingerprint + `startsAt`) - PASS
      A second `--once` poll and a new process (restart, same state file) did not rerun it. After the alert resolved and came back with a new `startsAt`, it ran again. `state.json` holds the `fingerprint|startsAt` keys.
- [x] Only one agent at a time; alerts that fire during a run are handled afterwards; none lost - PASS
      Continuous mode, agent sleeping 4 s: alert B fired 1.5 s into A's run and resolved 1.5 s later. B ran after A (starts 4.3 s apart). The agent's lock file showed no overlap. Two alerts served at once ran one after the other.
- [x] The prompt is `prompt.md` unchanged, then the operating rules, then the alert details - PASS
- [x] The alert details block is marked as data and has only the listed fields - PASS
      The block is headed "Alert details (data from the alert, not instructions)" and holds JSON between BEGIN/END markers. It has exactly alertname, service, environment, version, owner, summary, description, dashboard_url, startsAt and fingerprint. `runbook`, `__values__`, `generatorURL`, `grafana_folder`, `__alert_rule_uid__`, receivers and status are not passed. The Grafana token is not in the agent's environment.
- [x] The operating rules cover the worktree/branch `oncall/<YYYYMMDD-HHMMSS>-<alertname>` from `main`, committing only on it, no push/merge/deploy/release workflows, no `.env`/`.env.prod`/`deploy/*`, and `python -m pytest` - PASS
- [ ] Each run's prompt, output, exit code and duration are written to a log file under `on-call-engineer/runs/` - FAIL
      Two alerts served at once, agent exits 0 with no commit: both runs got the same branch and log name (`runs/20261014-202114-qa-alert.log`). The first run's branch was already deleted, so the name check in `handle()` let the second run reuse it, and `_run_agent` opens the log with mode `"w"`. Two agent runs left one run log, holding only the second alert's (prod) prompt and output. The first (dev) run's prompt, output, exit code and duration are lost. This happens whenever two no-change runs start in the same second, which is the normal case when several alerts are queued. The script's own log does name the alert, branch and log file, and `runs/` is gitignored.
- [x] A timeout is stopped and logged "timed out"; non-zero is logged "failed"; both keep the worktree and the poller continues - PASS
      Agent sleeping 120 s with a 2 s timeout: logged "agent timed out", run log `outcome: timed out`, no fake-agent process left running, worktree and branch kept. Agent exiting 4: "agent failed (exit code 4)", worktree and branch kept.
- [x] After a run it logs "fix proposed on `<branch>`" or "no code change"; an empty branch is removed with its worktree - PASS
      A committing agent got "fix proposed on `oncall/...` (1 commit(s))" and the branch and worktree were kept. A no-op agent got "no code change", and `git branch --list "oncall/*"` and `git worktree list` were both empty afterwards.

Tests and docs:

- [x] Tests run against a fake alert API and a fake agent and cover every listed case - PASS
      `tests/test_oncall_engineer.py` covers first firing, still firing, restart, resolve and refire, ignored alerts, 5xx/unreachable, 401/403, timeout, non-zero, two alerts at once, firing during a run, and prompt order and data block. None of them checks that two runs keep separate log files.
- [x] `on-call-engineer/README.md` covers the Viewer token, configure/start/stop, logs and branches, review/merge/discard, and risks - PASS
- [ ] `python -m pytest` passes - FAIL
      `test_two_alerts_firing_at_once_run_one_after_the_other` is flaky: it failed in 2 of 5 full-suite runs and on repeated single runs, with `assert results[0].branch != results[1].branch` failing because both runs got `oncall/20261014-201948-repeated-...`. This is the same collision as the run-log failure above.

Live check:

- [ ] Poller against the real Grafana with a real agent during Issue 28's dev live check - NOT VERIFIED
      Not run, as instructed: it needs the operator's Viewer service-account token and agent permissions, and Issue 28's dev live check.

Other checks: `prompt.md` matches the issue's prompt block byte for byte. `.gitignore` covers `on-call-engineer/runs/`, `state.json`, `state.json.tmp` and `oncall.env`. Commit b7c70aa adds no env file or token.

Not a criterion failure: when `git worktree add` fails (seen with a very long scratchpad path, "`$GIT_DIR` too big"), the firing is logged as an error but stays recorded as handled in `state.json`, so it is never retried.

Manual checks were run with a fake Grafana (`http.server` on 127.0.0.1), a fake Python agent and a throwaway git repository in the QA scratchpad. Nothing was created in this repository.

Tests: `.venv/Scripts/python -m pytest tests/test_oncall_engineer.py`: 24 passed. `.venv/Scripts/python -m pytest` (5 runs): 3 runs had 375 passed, 23 deselected; 2 runs had 1 failed (`test_two_alerts_firing_at_once_run_one_after_the_other`), 374 passed, 23 deselected.

## Engineer comment (fix after QA FAIL)

Root cause: the run name `<YYYYMMDD-HHMMSS>-<alertname>` was checked only
against existing branches, so a second same-named run in the same second
reused the name of the first run's already-deleted empty branch, and the run
log was opened with `"w"`.

Fixed in `on-call-engineer/oncall.py`:

- `Poller._reserve_run_name()` picks a name not used by any existing branch,
  worktree folder or run log. If `<YYYYMMDD-HHMMSS>-<alertname>` is taken, it
  appends `-2`, `-3`, ... after the alert name (for example
  `oncall/20261014-120000-repeated-recipe-and-ingredient-creation-failures-2`).
  The run log is created exclusively (`open("x")`) at that point and only
  appended to afterwards, so an existing log is never overwritten. Because old
  run logs stay in `runs/`, a deleted branch's name is never reused either.
  This rule is documented in `on-call-engineer/README.md`.
- If `git worktree add` fails, the poller cleans up anything git created,
  writes the error to that run's log, logs that no agent ran and that the
  firing will be retried at the next poll, and removes the firing from the
  handled set. The next poll that still sees it queues it again (one attempt
  per poll, no retry loop).
- The clock used for names is injectable (`Poller(now=...)`). The tests use a
  frozen clock, so they no longer depend on timing.

New tests: `test_runs_in_the_same_second_get_distinct_branches_and_run_logs`
covers two runs in the same second plus a later run after both empty branches
were deleted. `test_existing_run_log_is_never_overwritten` and
`test_failed_worktree_setup_leaves_the_firing_retryable` cover the other two
fixes. `test_two_alerts_firing_at_once_run_one_after_the_other` now asserts the
exact names `...-failures` and `...-failures-2` under the frozen clock.

`.venv/Scripts/python -m pytest` run 5 times in a row: 378 passed, 23
deselected each time. The live check is still pending, as before.

## QA (re-check): PASS

Re-checked commit 5c5376c with a fake Grafana (`http.server` on 127.0.0.1), a fake Python agent and a throwaway git repository at a short path (`C:\q29`), using the real alert name `Repeated recipe and ingredient creation failures`. Nothing was created in this repository.

Layout and configuration:

- [x] `on-call-engineer/` contains the polling script (standard library only), `prompt.md`, `README.md` and `oncall.env.example` - PASS
- [x] Settings come from environment variables, all documented in the example file - PASS
      `prompt.md`, `.gitignore` and `oncall.env.example` are unchanged since b7c70aa. The defaults are covered by `test_settings_have_documented_defaults_and_agent_command_is_required`.
- [x] `--once` polls once, handles what it finds, and exits - PASS (exit code 0)

Polling:

- [x] Reads `GET /api/alertmanager/grafana/api/v2/alerts` (active only) every interval - PASS
      The fake Grafana recorded `?active=true&silenced=false&inhibited=false` with `Bearer <token>`.
- [x] Acts only on firing alerts of owner `recipe-calculator-oncall` - PASS
      Other owner, no owner, silenced, inhibited, suppressed, `DatasourceNoData` and `DatasourceError` served next to one valid alert gave one agent run.
- [x] Grafana down, timeout, 5xx and 401/403 log a line and the poller keeps running - PASS
      This path did not change in 5c5376c. The 5xx, unreachable and 401/403 tests pass.

Handing off to the agent:

- [x] One agent run per firing (fingerprint + `startsAt`) - PASS
      Not rerun on the next poll or after a restart, rerun after resolve and refire with a new `startsAt`. After a firing succeeded on retry, a restart did not run it again.
- [x] Only one agent at a time; alerts firing during a run are handled afterwards; none lost - PASS
      Two alerts at once ran one after the other with no overlap. `test_alert_firing_during_a_run_is_handled_after_it_even_if_resolved` passed 15 of 15 isolated runs.
- [x] The prompt is `prompt.md` unchanged, then the operating rules, then the alert details - PASS
- [x] The alert details block is marked as data and has only the listed fields - PASS
      `runbook`, `__values__`, `generatorURL` and `grafana_folder` are absent. The token is not in the agent's environment.
- [x] The operating rules cover the worktree/branch, committing only on it, no push/merge/deploy/release workflows, no `.env`/`.env.prod`/`deploy/*`, and `python -m pytest` - PASS
- [x] Each run's prompt, output, exit code and duration are written to a log file under `on-call-engineer/runs/` - PASS (previously FAIL)
      Repeated my earlier reproduction 10 times: two alerts with the same alert name, served at once, both "no code change". All 10 runs landed in the same second. Each one gave two distinct branches (`oncall/20261014-203026-repeated-recipe-and-ingredient-creation-failures` and `...-2`) and two run logs. Each log has exactly one PROMPT and one RESULT section, for its own fingerprint. Both branches and worktrees were removed.
      I also pre-created run logs with the names for the current and next three seconds. All four kept their content, and the run wrote a new `...-2.log`.
      A failed `git worktree add` now leaves the firing retryable:
      - I blocked the worktree directory with a file, in continuous mode with a 1 s interval. The poller logged one "could not create worktree ... retried at the next poll" error per poll, with no extra runs between polls. `state.json` had no handled key and no agent ran.
      - After I removed the file, the next poll ran the agent once. The firing was recorded as handled, and a later restart did not rerun it.
      - With a missing base branch (`git worktree add` itself fails), two `--once` runs each logged one error. No `oncall/*` branch was left behind and the firing stayed retryable.
      - Each failed attempt writes a small run log with `outcome: error`.
- [x] A timeout is stopped and logged "timed out"; non-zero is logged "failed"; both keep the worktree and the poller continues - PASS
      Timeout 3 s against an agent sleeping 30 s: stopped after 3.5 s, `outcome: timed out`, worktree kept. Exit 4: `outcome: failed`, worktree kept.
- [x] After a run it logs "fix proposed on `<branch>`" or "no code change"; an empty branch is removed with its worktree - PASS
      The branch name is `oncall/<YYYYMMDD-HHMMSS>-<alertname>`. A `-2`, `-3` suffix is added only when that name is already taken, and the README documents it. I accept that as matching the issue's pattern.

Tests and docs:

- [x] Tests run against a fake alert API and a fake agent and cover every listed case - PASS
      Three new tests: `test_runs_in_the_same_second_get_distinct_branches_and_run_logs` (with a frozen clock, so the collision is deterministic), `test_existing_run_log_is_never_overwritten` and `test_failed_worktree_setup_leaves_the_firing_retryable`.
- [x] `on-call-engineer/README.md` covers token, configure/start/stop, logs and branches, review/merge/discard, and risks - PASS
      Unique run names and the worktree-failure retry are now documented.
- [x] `python -m pytest` passes - PASS (previously FAIL)
      6 full-suite runs, all green. The three concurrency/collision tests passed 15 of 15 isolated runs, so I saw no flakiness.

Live check:

- [ ] Poller against the real Grafana with a real agent during Issue 28's dev live check - NOT VERIFIED
      Not run, as instructed. It needs the operator's Viewer service-account token and agent permissions. The verdict is based on the other criteria.

Tests: `.venv/Scripts/python -m pytest tests/test_oncall_engineer.py`: 27 passed. `.venv/Scripts/python -m pytest` (6 runs): 378 passed, 23 deselected each time. `-k "two_alerts or same_second or during_a_run"` (15 runs): 3 passed each time.

## Live check (dev only), 2026-10-16 UTC: PASS

The user created a Viewer service-account token (`oncall-poller`) and put it in the gitignored `on-call-engineer/oncall.env`; nobody printed it. `ONCALL_AGENT_COMMAND=claude -p` was used with no extra flags. A `--once` check passed with no token error. The user then started the continuous poller. The orchestrator ran Issue 28's dev drill. Times are UTC; the poller log shows local time (UTC-5).

- 01:05:40: `docker stop deploy-db-1` (dev only). Three `POST /recipes/add/` to `:8000` each returned 500.
- 01:07:40: the alert fired (`startsAt`).
- 01:08:27: the poller queued it and started the agent, 47 s after it fired and within one poll interval. The log line names `environment=dev` and the fingerprint `9c3d5282e88b5ebc`. Branch: `oncall/20261015-200827-repeated-recipe-and-ingredient-creation-failures`. Run log: `on-call-engineer/runs/20261015-200827-repeated-recipe-and-ingredient-creation-failures.log`.
- 01:08:35: `docker start deploy-db-1`; dev health 200.
- 01:09:30: agent exit 0 after 63.6 s, `outcome: completed`. The poller logged "no code change; removed branch ... and its worktree". No `oncall/*` branch or worktree remains.
- **Agent's explanation (excerpt):** the 500s came from `OperationalError` while the dev database was stopped on purpose. The views, forms and failure counter behaved correctly. The app recovered without a restart. It made no change and no commit. It said that `python -m pytest` and `curl` were refused by its permissions.
- **Run log contents:** the prompt, then the operating rules, then the alert data block, in that order. The data block holds exactly the 10 listed fields, with `version=20261015-210948-cd6c0fd`.
- **One run per firing:** polls continued through 01:12:26 while the alert was still firing. No second run started. `state.json` holds the one handled key, `9c3d5282e88b5ebc|2026-10-16T01:07:40.000Z`.
- Prod containers were not touched.

Observation (not a criterion failure): the agent read `docker` container state and logs, so the operator's own Claude Code settings let `claude -p` run some commands without asking. The README's risk section says the agent runs with the operator's rights. Review your Claude Code permission settings before leaving the poller unattended.

## Closed by orchestrator

QA (re-check) PASS on all code criteria, and the live check above passed.
