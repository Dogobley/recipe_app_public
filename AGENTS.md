# Codex Repository Instructions

## Session startup

- Read `_docs/architecture.md` and `_docs/process.md` before planning or changing
  the project.
- Treat the documents in `_docs` as the project's persistent context across Codex
  sessions.
- Inspect the current worktree before editing. Preserve user changes and do not
  commit them unless the user explicitly asks for a commit.
- Ignore `_docs_old/` folder.

## Commands

- `python -m pip install -r requirements.txt` - install dependencies
- `python -m pytest` - run the whole test suite
- `python -m pytest tests/test_home.py` - run one test file
- `python -m pytest -m compose` - run the Docker Compose integration tests
  (needs Docker; excluded from the default run)
- `python -m playwright install chromium` - install the browser for `e2e/` once
- `python -m pytest e2e` - run the Playwright end-to-end tests against the
  Compose deployment (needs Docker; excluded from the default run)

## Rules

- Add dependencies only in `requirements.txt`, and ask the user before adding one.
- Check whether `.venv` is active before installing dependencies.
- Follow the architecture and scope defined in `_docs/architecture.md` unless the
  user's request explicitly changes them.
- Work on one GitHub issue at a time and follow `_docs/process.md`.

## Documents

- `_docs/process.md` - how work is organized
- Before writing tests, read `_docs/testing-guidelines.md`
- For anything touching the UI, read `_docs/design-system.md`

## Documentation maintenance

- When a user correction establishes a durable project rule, update the relevant
  document in `_docs` so future Codex sessions inherit it.
- Keep repository-wide agent instructions in this root `AGENTS.md`; use nested
  `AGENTS.md` files only for instructions that apply to a specific subtree.
- Keep documentation consistent with the implemented project and do not reference
  documents that do not exist.
