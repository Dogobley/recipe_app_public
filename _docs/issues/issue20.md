# Issue 20: Write the operator guide

Status: closed

## Goal

Document how a single user installs, runs, backs up, restores, and updates the application.

## Acceptance criteria

- [x] One discoverable operator guide states its prerequisites and takes a user from a clean checkout to a healthy local environment using copyable commands.
- [x] The guide separately documents production configuration, build, startup, health verification, logs, and shutdown.
- [x] Every required environment variable is described without exposing real credentials, and the guide explains how to generate secret values.
- [x] The guide documents how to inspect, apply, and verify database migrations, including what to do when a migration fails.
- [x] The guide provides a backup command that creates a timestampable PostgreSQL dump outside the database container and explains what data it contains.
- [x] The restore procedure warns that it replaces database state, identifies the exact target database, and includes verification steps after restoration.
- [x] The update procedure covers obtaining a new application version, rebuilding images, backing up before migration, applying migrations, checking health, and rolling back to the prior application version when health verification fails.
- [x] Dependency-update instructions use `requirements.txt` and include rebuilding plus running the complete test suite.
- [x] Troubleshooting covers unhealthy database and web containers, connection errors, migration failures, missing static assets, occupied host ports, and where to inspect logs.
- [x] Every documented command is executed successfully against the final project configuration, or is explicitly marked as an environment-specific example with its assumptions.
- [x] Documentation links to the relevant project files and does not reference commands, services, variables, or documents that do not exist.

## Out of scope

- Changing the container or application behavior belongs to [Issue 19](issue19.md) or the issue that owns the affected feature.

## Constraints

- Complete [Issues 18](issue18.md) and [19](issue19.md) first so every command documents verified final behavior.
- Keep operational documentation in the repository and make it discoverable from the README.
- Use the actual Docker Compose service names, environment variables, paths, and commands present in the project.
- Mark destructive restore and rollback steps clearly and require a backup plus explicit target verification before execution.
- Do not include real secrets, machine-specific absolute paths, or undocumented third-party services.
