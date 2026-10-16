# Issue 19: Prepare the production container configuration

Status: closed

## Goal

Run the application in a production-oriented container using Gunicorn and PostgreSQL.

## Acceptance criteria

- [x] The production Compose configuration builds the application image and starts Django through Gunicorn rather than `runserver`.
- [x] Startup applies pending migrations before Gunicorn begins accepting traffic and fails visibly if migration fails.
- [x] Static assets are collected during deployment and are served successfully by the production web service without a separate frontend service.
- [x] A lightweight health endpoint returns HTTP 200 only when the Django application can serve requests and access PostgreSQL.
- [x] The web and database container health checks use their real service health and Compose reports both healthy after startup.
- [x] `DEBUG` is disabled in production and secret key, allowed hosts, CSRF trusted origins, database credentials, and other deployment-specific values come from environment variables.
- [x] Startup fails with a useful error when a required production variable is missing; no production secret or usable default credential is committed.
- [x] The container runs as a non-root user and exposes only the documented application port.
- [x] Graceful container shutdown allows Gunicorn to stop without corrupting in-flight startup or migration work.
- [x] Deployment documentation lists every required variable and exact build, start, migration-status, log, health-check, and stop command.
- [x] An automated or documented smoke check starts the production configuration, reaches the health endpoint, loads a page with its static assets, and reports success.

## Out of scope

- Database backup, restore, and application update procedures belong to [Issue 20](issue20.md).
- General product workflow regression coverage belongs to [Issue 18](issue18.md).

## Constraints

- Complete [Issues 2](issue2.md) and [18](issue18.md) first and extend the existing image and Compose configuration.
- Use Gunicorn, PostgreSQL, and Docker Compose as defined by the [application architecture](../architecture.md).
- Keep the deployment to the `web` and `db` services; do not introduce a reverse proxy or frontend build service.
- Keep configuration environment-based and ensure logs are emitted to container stdout or stderr.
- Any new dependency must be added only to `requirements.txt` after the repository-required user approval.
