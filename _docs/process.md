# Development Process

- Work from one issue at a time from `_docs/issues/`.
- Read the issue's acceptance criteria before starting and verify them again before
  closing the issue.
- Inspect the worktree before making changes and preserve unrelated user work.
- Make focused commits at useful checkpoints when the user has asked Codex to
  commit the work.
- Record durable corrections to project workflow or architecture in the relevant
  file under `_docs` so later Codex sessions receive the same context.
- Before writing or changing tests, read `_docs/testing-guidelines.md` and follow
  its test organization, database, and assertion conventions.
- Before changing templates, styles, navigation, forms, or other user-facing UI,
  read `_docs/design-system.md` and preserve its accessibility and responsive
  design rules.

## Roles

- PM - grooms a task before anyone implements it, follows _docs/team/pm.md
- Engineer - implements one groomed task, follows _docs/team/software-engineer.md
- QA - checks the result against the acceptance criteria, follows _docs/team/qa-engineer.md


# Orchestrator

The main session is the orchestrator. It launches the PM, the engineer
and QA as subagents. It does not groom, implement or test itself.

## Lifecycle

1. Pick the next open issue from the backlog
2. PM grooms it
3. Engineer implements it
4. QA verifies it
5. On FAIL, back to step 3 with the QA comment as input
6. On PASS, close the issue
7. Repeat until the backlog is empty

## Rules

- Skip step 2
- The engineer does not close the issue
- QA does not fix the code, only outputs PASS or FAIL
- The orchestrator closes the issue only after QA outputs PASS