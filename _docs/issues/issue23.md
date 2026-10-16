# Issue 23: Warn when production telemetry has no OTLP endpoint

Status: closed

## Goal

When a production deployment starts without an OTLP endpoint, the operator can see in the logs that spans and metrics are only written to the console, instead of finding out from an empty Grafana dashboard ([Issue 22](issue22.md)).

## Acceptance criteria

- [ ] When `DJANGO_ENV=production`, `OTEL_SDK_DISABLED` is not true, and `OTEL_EXPORTER_OTLP_ENDPOINT` is empty, `docker compose logs web` shows one warning at startup. The warning says telemetry is going to the console and names `OTEL_EXPORTER_OTLP_ENDPOINT`.
- [ ] Each gunicorn worker logs the warning at most once at startup, and never again per request.
- [ ] No warning is logged when the endpoint is set, when `OTEL_SDK_DISABLED=true`, or when `DJANGO_ENV` is not `production`.
- [ ] The application still starts and serves requests without an endpoint. A missing endpoint never stops startup.
- [ ] `python -m pytest` passes.

## Out of scope

- Making the endpoint required in production. Without an observability stack, an operator must still be able to run the app.

## Constraints

- Keep the change inside `config/telemetry.py` and its tests (`tests/test_telemetry.py`, `tests/test_metrics.py`).
- Use the standard `logging` module so the warning lands on container stderr with the other logs.
- Read `_docs/testing-guidelines.md` before writing tests.
- Do not add dependencies.

## Engineer comment

Implemented in `config/telemetry.py`: new `warn_if_console_only()` logs one `logging` warning (logger `config.telemetry`) when `DJANGO_ENV=production`, `OTEL_SDK_DISABLED` is not true, and `OTEL_EXPORTER_OTLP_ENDPOINT` is empty/blank. The message says telemetry is going to the console only and names `OTEL_EXPORTER_OTLP_ENDPOINT`. It is called from `setup_telemetry()` (run once per process from `wsgi.py`/`asgi.py`) only when no exporter is injected, and a module flag (`_warned`) keeps it to one emission per process; nothing logs per request. It only logs, so startup is never blocked.

Tests added in `tests/test_telemetry.py`: warns once and names the variable; blank endpoint warns; no repeat on later setup calls or requests; no warning with endpoint set, with `OTEL_SDK_DISABLED=true`, or outside production; app still starts and serves `/` (200) without an endpoint. `tests/test_metrics.py` unchanged.

Results: `.venv/Scripts/python -m pytest` -> 310 passed, 23 deselected.

Not verified: per-gunicorn-worker behavior (the "at most once per worker" guarantee relies on the per-process flag; with `--preload` it would log once in the master instead) and the actual `docker compose logs web` output. Both need a running Compose stack. Status left open for QA.

## QA: PASS

- [x] Production, SDK not disabled, endpoint empty: one warning naming `OTEL_EXPORTER_OTLP_ENDPOINT` and saying telemetry goes to the console - PASS (code). Ran a script with `DJANGO_ENV=production` and no endpoint, calling `setup_telemetry()` twice plus `warn_if_console_only()`: one `WARNING:config.telemetry` line with the expected text. A blank endpoint (whitespace) also warns. The `docker compose logs web` output itself is NOT VERIFIABLE (live); no handler is configured, so Python's last-resort handler prints WARNING to stderr and it would appear.
- [x] At most once per gunicorn worker, never per request - PASS. `docker-entrypoint.sh` runs gunicorn without `--preload`, so each worker imports `config/wsgi.py` and runs `setup_telemetry()` once, and the `_warned` flag stops repeats. Nothing in the request path logs it. With `GUNICORN_WORKERS=2` (default), expect one line per worker (2 lines), which is consistent with this criterion. Live worker output NOT VERIFIABLE (live).
- [x] No warning with endpoint set, `OTEL_SDK_DISABLED=true`, or non-production - PASS. Exercised all three by script: no warning output, `_warned` stayed False.
- [x] App starts and serves without an endpoint - PASS. The function only logs and never raises. Covered by a test that serves `/` with 200.
- [x] `python -m pytest` passes - PASS

Tests: `.venv/Scripts/python -m pytest -q`, 310 passed, 0 failed, 23 deselected (compose/e2e not run, no live stack started).

Notes: change stays within `config/telemetry.py` and `tests/test_telemetry.py` for this issue (other modified files in the worktree belong to other issues). No code was changed by QA.
