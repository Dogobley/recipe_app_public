# Issue 34: Move the workflows off actions that target the deprecated Node.js 20

Status: closed (2026-10-23)

## Goal

The workflows use action versions that run on Node.js 24, so GitHub no longer
warns that `actions/checkout@v4` and `actions/setup-python@v5` target the
deprecated Node.js 20.

## Acceptance criteria

- [x] Every `actions/checkout` reference in `.github/workflows/` is
      `actions/checkout@v7`.
- [x] Every `actions/setup-python` reference in `.github/workflows/` is
      `actions/setup-python@v7`, with the same inputs as today
      (`python-version: "3.13"`, `cache: pip`,
      `cache-dependency-path: requirements.txt`).
- [x] No other action reference, input, trigger, condition or step changes.
- [x] A default-suite test fails if any workflow references `actions/checkout`
      or `actions/setup-python` at a major version below 7.
- [x] Every workflow still parses as YAML, and `python -m pytest` passes.
- [x] The README notes that the self-hosted runner must be version 2.327.1 or
      later, which Node.js 24 actions require.

## Live check (after the user pushes)

Not part of the QA gate. On GitHub, the CI jobs pass and show no Node.js 20
deprecation warning.

## Out of scope

- Pinning actions to commit SHAs.

## Constraints

- Change only `.github/workflows/`, `README.md` and tests under `tests/`.
- Add no dependencies. Follow `_docs/testing-guidelines.md`.

## Engineer comment

Moved every workflow step from `actions/checkout@v4` to `actions/checkout@v7`
(`build.yml`, `ci.yml` twice, `deploy-observability.yml`, `deploy.yml`) and from
`actions/setup-python@v5` to `actions/setup-python@v7` (`ci.yml` twice). Only
those seven `uses:` lines changed; the setup-python inputs (`python-version:
"3.13"`, `cache: pip`, `cache-dependency-path: requirements.txt`), the reusable
workflow references, triggers, conditions and steps are untouched. The README's
self-hosted runner paragraph now says the runner must be version 2.327.1 or
later, because older runners cannot run Node.js 24 actions.

Added tests to `tests/test_ci_workflows.py`: a version check that flags any
`actions/checkout` or `actions/setup-python` reference below major 7 (or with no
`vN` tag), with cases for v4, v5, v6, a branch ref and v7/v8; a scan of every
workflow file's text that fails on any such reference; an exact list of each
workflow's step actions, checked against every mention in the text; the
unchanged setup-python inputs; and the README runner note. Setting one
`setup-python` back to `@v5` made two of the new tests fail, as intended. The
loader fixture's `actions/checkout@v4` is sample input for the parser, not a copy
of a workflow, so it stays. Every workflow still parses with the test YAML
loader.

`python -m pytest tests/test_ci_workflows.py` passed (33 tests);
`python -m pytest` passed (457 passed, 1 skipped, 30 deselected). Compose and e2e
were not run because no runtime code changed. The Node.js 20 warning can only
be checked on GitHub after a push. Ready for QA; issue remains open.

## QA: PASS

- [x] Every `actions/checkout` reference in `.github/workflows/` is
      `actions/checkout@v7` - PASS
      All five `actions/checkout` steps (`build.yml`, `ci.yml` x2,
      `deploy-observability.yml`, `deploy.yml`) are `@v7`; grep finds no other
      mention.
- [x] Every `actions/setup-python` reference is `actions/setup-python@v7`, with
      the same inputs - PASS
      Both `ci.yml` steps are `@v7` with `python-version: "3.13"`, `cache: pip`,
      `cache-dependency-path: requirements.txt`, identical to HEAD.
- [x] No other action reference, input, trigger, condition or step changes - PASS
      Parsed every workflow at HEAD (`git show HEAD:<path>`) and in the working
      copy with PyYAML 6.0.3; after mapping `checkout@v4`/`setup-python@v5` to
      `@v7` the trees are identical (0 residual differences, 7 raw ones, all
      `uses:` values). `promote-to-production.yml` is listed as modified but has
      no content diff (same blob hash as HEAD). Only the allowed files changed.
- [x] A default-suite test fails on a major version below 7 - PASS
      In a scratch copy of the repo, `tests/test_ci_workflows.py` failed (2 tests)
      for each of: one `ci.yml` setup-python back to `@v5`, `build.yml` checkout
      `@v4`, quoted `"actions/checkout@v4"`, `deploy.yml` checkout `@v6`,
      `deploy-observability.yml` checkout `@main`, and a new `extra.yml` /
      `extra.yaml` workflow using `@v4` / `@v5`. Unmodified copy: 33 passed.
      The test is under `testpaths` and not marked `compose`.
- [x] Every workflow still parses as YAML, and `python -m pytest` passes - PASS
      All five workflows load with PyYAML and with the test loader.
- [x] The README notes the self-hosted runner must be 2.327.1 or later - PASS
      The self-hosted runner paragraph in the CI/CD section says so and gives
      the Node.js 24 reason.

Tests: `python -m pytest` (`.venv`, Python 3.12), 457 passed, 1 skipped,
30 deselected, 0 failed. `python -m pytest tests/test_ci_workflows.py` in a
scratch copy: 33 passed unmodified, failures as listed above for each old version.
Compose and e2e not run (no runtime code changed).

## Closed by orchestrator

QA PASS on all acceptance criteria. Live check on GitHub follows the push.
