#!/bin/sh
set -eu

# Forward a stop signal to the active startup task. A migration interrupted by
# SIGTERM is rolled back by PostgreSQL; Gunicorn is later `exec`ed as PID 1.
child_pid=""
stop_startup() {
    trap - TERM INT
    if [ -n "$child_pid" ]; then
        kill -TERM "$child_pid" 2>/dev/null || true
        wait "$child_pid" || true
    fi
    exit 143
}
trap stop_startup TERM INT

run_startup_task() {
    "$@" &
    child_pid=$!
    wait "$child_pid"
    child_pid=""
}

# Do not start Gunicorn if either deployment preparation step fails.
run_startup_task python manage.py migrate --noinput
run_startup_task python manage.py collectstatic --noinput
trap - TERM INT

# `exec` makes Gunicorn PID 1 so it receives Compose's stop signal directly.
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-30}" \
    --access-logfile - \
    --error-logfile -
