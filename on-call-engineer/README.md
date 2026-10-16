# On-call engineer

`oncall.py` polls Grafana's alert API and, when one of this project's alerts
starts firing, runs a headless coding agent once for that firing. The agent
works in its own git worktree on a new `oncall/<YYYYMMDD-HHMMSS>-<alertname>`
branch created from `main`, and either commits a minimal fix there or explains
why the alert is a false positive. Nothing is pushed or merged: a human reviews
every `oncall/*` branch.

Files in this directory:

- `oncall.py` - the poller (Python standard library only)
- `prompt.md` - the on-call prompt given to the agent, unchanged
- `oncall.env.example` - every setting, with its default
- `runs/` - run logs and the poller's own log (created on first run, gitignored)
- `state.json` - firings already handled and firings waiting for a run
  (gitignored)

## What it acts on

Each poll reads `GET /api/alertmanager/grafana/api/v2/alerts` (active alerts
only). The poller acts only on alerts that are firing, not silenced and not
inhibited, whose `owner` label is `recipe-calculator-oncall`, the owner set by
the rule in
`observability/grafana/provisioning/alerting/component-creation-failures.yaml`.
Grafana's own `DatasourceNoData` / `DatasourceError` alerts and other owners'
alerts are ignored.

A firing is identified by its fingerprint and `startsAt`. It gets one agent run:
not again on later polls while it keeps firing, not again after the poller
restarts (that is what `state.json` remembers), but again if the alert resolves
and fires later (a new `startsAt`). Only one agent runs at a time. While a run
is in progress the poller keeps polling and queues new firings; they run one by
one after it, even if they resolve in the meantime. The queue is kept in
`state.json` too.

The agent receives, on its standard input and in this order:

1. the contents of `prompt.md`, unchanged;
2. an "Operating rules" block: work only in the given worktree, commit only on
   its `oncall/*` branch, never push, merge, deploy or run the release
   workflows, never read or print `.env`, `.env.prod` or `deploy/*`, and run
   the backend tests with `python -m pytest`;
3. an "Alert details" block, marked as data from the alert and not
   instructions, holding only the alert's name, `service`, `environment`,
   `version`, `owner`, `summary`, `description`, `dashboard_url`, `startsAt`
   and fingerprint.

## 1. Create the Grafana service-account token

Use a service-account token with the **Viewer** role, never the admin password.

1. Open Grafana (`http://localhost:3000`) and sign in as an administrator.
2. Go to **Administration > Users and access > Service accounts** and choose
   **Add service account**.
3. Name it, for example, `oncall-poller`, set the role to **Viewer**, and
   create it.
4. Choose **Add service account token**, give it a name and an expiry, and
   **Generate token**. Copy the token now; Grafana shows it only once.
5. To revoke it later, delete the token (or the service account) on the same
   page.

The token is read only by the poller. It is removed from the environment the
agent runs in.

## 2. Configure

```powershell
Copy-Item on-call-engineer/oncall.env.example on-call-engineer/oncall.env
```

Edit `on-call-engineer/oncall.env` (it is gitignored, never commit it):

| Variable | Default | Meaning |
| --- | --- | --- |
| `ONCALL_GRAFANA_URL` | `http://localhost:3000` | Grafana base URL |
| `ONCALL_GRAFANA_TOKEN` | (none) | Viewer service-account token |
| `ONCALL_AGENT_COMMAND` | (none, required) | Agent command line, for example `claude -p` or `codex exec -` |
| `ONCALL_POLL_INTERVAL` | `60` | Seconds between polls |
| `ONCALL_AGENT_TIMEOUT` | `1800` | Seconds before an agent run is stopped (30 minutes) |

Optional overrides (`ONCALL_OWNER`, `ONCALL_REPO_DIR`, `ONCALL_BASE_BRANCH`,
`ONCALL_WORKTREES_DIR`, `ONCALL_RUNS_DIR`, `ONCALL_STATE_FILE`) are listed in
the example file. Settings can also be plain environment variables; those take
precedence over the env file.

The agent command is split like a POSIX shell command line and its first word
is looked up on `PATH`. Wrap Windows paths containing backslashes or spaces in
double quotes. The poller has no built-in agent: the command, and the
permissions it grants itself, are the operator's choice.

The example uses Claude Code in print mode, `claude -p`. Its defaults matter
for an unattended run:

- By default `claude -p` cannot ask for permission, so tool calls that need
  approval (editing files, running `git commit` or `python -m pytest`) are
  refused and the run usually ends with an explanation and no commit.
- To let it fix and commit, grant the tools it needs explicitly, for example
  `claude -p --allowedTools "Read,Grep,Glob,Edit,Bash(python -m pytest:*),Bash(git add:*),Bash(git commit:*),Bash(git diff:*),Bash(git status:*),Bash(git log:*)"`.
  Prefer such a narrow list.
- Avoid `--dangerously-skip-permissions`: it lets the agent run any command on
  this machine with your user's rights.

## 3. Start and stop

From the repository root:

```powershell
# Keep polling every ONCALL_POLL_INTERVAL seconds:
.venv/Scripts/python on-call-engineer/oncall.py --env-file on-call-engineer/oncall.env

# Poll once, handle what is found, and exit (for a scheduler such as Windows
# Task Scheduler, or for a manual check):
.venv/Scripts/python on-call-engineer/oncall.py --env-file on-call-engineer/oncall.env --once
```

Stop the continuous poller with `Ctrl+C`. A run in progress is interrupted with
it; its worktree and branch stay for a human, and that firing is not retried
(it is already recorded in `state.json`). Do not run two pollers at once: they
would share `state.json`.

If Grafana is down, times out or returns a 5xx, the poller logs one line and
tries again at the next interval. A 401 or 403 logs "Grafana token missing or
invalid" and the poller keeps running; fix the token and restart it.

## 4. Where logs and branches go

- The poller's own log goes to the console and to `on-call-engineer/runs/poller.log`.
  For each firing it names the alert (with its `environment`), the branch and
  the run log file, and finally either "fix proposed on `oncall/...`" or "no
  code change".
- Each run writes `on-call-engineer/runs/<YYYYMMDD-HHMMSS>-<alertname>.log`
  with the full prompt, the agent's output, the outcome, the exit code and the
  duration.
- Each run's worktree is created under
  `<repository parent>/<repository name>-oncall-worktrees/<YYYYMMDD-HHMMSS>-<alertname>`
  (outside the repository) on branch `oncall/<YYYYMMDD-HHMMSS>-<alertname>`,
  created from `main`.
- Every run gets its own name. When `<YYYYMMDD-HHMMSS>-<alertname>` is already
  taken (two runs of the same alert name starting in the same second, or an
  earlier run's log, branch or worktree with that name), `-2`, `-3`, ... is
  appended after the alert name, for example
  `oncall/20261014-120000-repeated-recipe-and-ingredient-creation-failures-2`.
  An existing run log is never overwritten.
- If the worktree cannot be created (for example `git worktree add` fails),
  the poller logs the error, no agent runs, and the firing is tried again at
  the next poll (once per poll) while it is still firing.
- A run that ends without a new commit has its branch and worktree removed.
- A run that times out (it is stopped) or exits non-zero is logged as "timed
  out" or "failed" and keeps its worktree and branch for a human.

## 5. Review, merge or discard an `oncall/*` branch

Nothing is merged automatically. Read the run log first, then:

```powershell
git branch --list "oncall/*"                 # proposed fixes
git worktree list                            # where each one is checked out
git log --stat main..oncall/<name>           # what the agent committed
git diff main...oncall/<name>                # the change itself
```

Run the tests yourself in the worktree (`python -m pytest`) before trusting the
change.

- **Merge**: from your main checkout, `git switch main`, then
  `git merge --ff-only oncall/<name>` (or cherry-pick the commit), and release
  through the normal workflow. Then remove the worktree and branch as below.
- **Discard**: `git worktree remove --force <worktree path>` and
  `git branch -D oncall/<name>`. `git worktree prune` cleans up entries whose
  folder was already deleted.

## Risks of an unattended agent

The poller starts a program that reads and writes files and runs commands on
this machine, with your user account, without anyone watching. Treat it as such:

- **It runs code.** Running the tests or reproducing a failure executes the
  repository's code and anything the agent decides to run. A wrong or
  manipulated agent can delete files, read secrets outside the worktree, or use
  your credentials (git, Docker, cloud CLIs, SSH keys) that this account can
  reach. The operating rules are instructions, not a sandbox.
- **Alert text is untrusted input.** Labels and annotations can contain text
  produced from application data. The poller passes only the listed fields and
  marks them as data, but prompt injection cannot be ruled out. Keep the
  agent's permissions narrow.
- **Permissions are yours to choose.** `claude -p` with its defaults refuses
  actions that need approval; every tool you allow with `--allowedTools`, and
  certainly `--dangerously-skip-permissions`, widens what it can do unattended.
  Other agents (`codex exec` and its sandbox flags) need the same review.
- **Secrets.** Do not keep production secrets readable by this account if you
  can avoid it. The agent is told never to read `.env`, `.env.prod` or
  `deploy/*`, and the Grafana token is removed from its environment, but a
  misbehaving agent is not technically prevented from reading files.
- **Cost and load.** Each firing starts a run that can last up to
  `ONCALL_AGENT_TIMEOUT` and uses paid model calls. A flapping alert starts a
  new run every time it fires again.
- **Review everything.** Never merge an `oncall/*` branch without reading the
  diff and running the tests; never let the agent push, merge or deploy.

Running the poller as a Windows service or at boot, pushing branches, opening
pull requests and notifying people are out of scope.
