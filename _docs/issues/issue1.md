# Issue 1: Set up the empty Django project

Status: closed

## Goal

Create a runnable empty project with one passing automated test.

## Acceptance criteria

- [x] A clean Python 3.13 environment can install every declared dependency from `requirements.txt`.
- [x] The installed Django version is in the 5.2 LTS release series.
- [x] `python manage.py check` completes without errors using documented development environment variables.
- [x] `python manage.py runserver` starts the project and the root URL returns a successful HTTP response.
- [x] `python -m pytest` discovers and passes at least one Django smoke test.
- [x] No secret values are committed; a tracked example environment file lists every required setting.
- [x] The README documents dependency installation, environment setup, starting the server, and running tests from a clean checkout.

## Out of scope

- PostgreSQL and Docker Compose setup belongs to [Issue 2](issue2.md).
- Application data models belong to [Issues 3](issue3.md) and [4](issue4.md).
- Shared page styling and navigation belong to [Issue 8](issue8.md).
- Production serving and deployment settings belong to [Issue 19](issue19.md).

## Constraints

- Use Python 3.13, Django 5.2 LTS, pytest, and pytest-django as defined by the [application architecture](../architecture.md).
- Declare dependencies only in `requirements.txt`; do not add a second dependency-management system.
- Create the conventional Django project and one application package without adding an API, frontend build system, or business features.
- Keep configuration environment-based so later local and production setups can supply different values.
