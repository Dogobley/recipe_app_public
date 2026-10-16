# Issue 2: Add the local PostgreSQL environment

Status: closed

## Goal

Run the Django application and PostgreSQL together through Docker Compose.

## Acceptance criteria

- [x] `docker compose up --build` starts a Django `web` service and a PostgreSQL `db` service from a clean checkout after the documented environment setup.
- [x] The web container waits for a healthy database and connects using environment-provided credentials rather than hard-coded secrets.
- [x] PostgreSQL data survives stopping and starting the Compose project through a named volume.
- [x] Both services expose health checks, and Compose reports them healthy after startup.
- [x] The application is reachable from the host at the documented URL.
- [x] Documented container commands successfully apply migrations and run the pytest suite without PostgreSQL installed on the host.
- [x] The README documents how to configure, build, start, inspect, and stop the local environment.
- [x] A tracked example environment file contains every required variable and no real credentials.

## Out of scope

- Creating application tables beyond Django defaults belongs to [Issues 3](issue3.md) and [4](issue4.md).
- Production Gunicorn, static-file, and hardened settings belong to [Issue 19](issue19.md).
- Backup, restore, upgrade, and troubleshooting procedures belong to [Issue 20](issue20.md).

## Constraints

- Complete [Issue 1](issue1.md) first and extend its project rather than creating a second application setup.
- Use Docker Compose with only the Django web application and PostgreSQL as required runtime services.
- Use PostgreSQL and psycopg 3, consistent with the [application architecture](../architecture.md).
- Keep credentials and connection values in environment variables; commit examples only.
- Do not require a host PostgreSQL installation.
