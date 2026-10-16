# Testing Guidelines

## Purpose

Tests provide executable evidence that an issue's acceptance criteria are met.
Write tests as part of the issue that introduces or changes behavior, and keep
them focused on observable outcomes rather than implementation details.

## Test stack and commands

- Use pytest and pytest-django.
- Run the full suite with `python -m pytest`.
- Run a focused file with `python -m pytest path/to/test_file.py` while
  developing, then run the full suite before considering the work complete.
- Use the configured PostgreSQL test database for behavior that touches the ORM
  or database constraints. Do not substitute SQLite.
- Tests must not depend on external network services or execution order.

## Test organization

- Put tests under `tests/` and group them by the behavior or application area
  they cover.
- Give tests names that state the scenario and expected result.
- Keep fixtures and helpers small, explicit, deterministic, and local unless
  multiple test modules genuinely share them.
- Prefer the smallest test level that proves the behavior, while retaining
  integration coverage for important user workflows.

## What to test

- Domain services: conversion, proportional cost, scaling, totals, precision,
  rounding boundaries, and invalid inputs.
- Models: relationships, validation, deletion behavior, uniqueness, and database
  constraints.
- Forms and formsets: valid submissions, field and non-field errors, and atomic
  rejection of invalid multi-record writes.
- Views and templates: status codes, redirects, HTTP methods, messages,
  accessibility-relevant markup, and user-visible formatted results.
- Workflows: real URLs, forms, views, templates, ORM persistence, and PostgreSQL
  constraints through Django's test client. Do not mock domain services in these
  integration tests.

Every acceptance criterion should have direct test evidence unless it cannot be
automated reasonably. Document any manual verification and why automation was
not appropriate.

## Compose integration tests

- Tests under `tests/compose/` build `compose.yaml` and drive the running
  containers over HTTP. They carry the `compose` marker and are deselected by
  default, so `python -m pytest` never needs Docker.
- Run them with `python -m pytest -m compose`. They need a running Docker daemon
  and take about a minute after the first image build.
- The stack runs under its own Compose project name, generated environment file,
  and a free loopback port, so it never touches a real deployment's containers,
  `.env`, or `postgres_data` volume. It is removed with its volume afterwards.
- Use only the standard library for HTTP; reach the application through real
  URLs and forms, never through the ORM or Django's test client.
- A test that stops or recreates a service must restore the stack before it
  finishes, and records must use unique names, so tests stay order-independent.
- Put deployment behavior here (startup, health, static delivery, hardening,
  persistence, shutdown, misconfiguration). Keep business-rule detail in the
  faster test-client suites.

## Browser end-to-end tests

- Tests under `e2e/` drive Chromium with Playwright against the same isolated
  Compose stack, reusing the `stack` fixture from `tests/compose/conftest.py`.
- Run them with `python -m pytest e2e`. `e2e/` is outside `testpaths`, so the
  default `python -m pytest` never collects them. Set `E2E_HEADED=1` to watch.
- Install the browser once with `python -m playwright install chromium`.
- Act through visible controls (navigation links, labels, buttons) and assert the
  text the page displays. A journey may be one long test when its steps build on
  each other.
- Keep runs offline and deterministic: the Bootstrap CDN is blocked in the
  browser, and market prices are fixed snapshots recorded in the test, never
  fetched live.
- The application reports costs only. Figures it does not display, such as a
  sale price for a target income, are derived in the test from visible values.

## Assertions and data

- Assert externally visible behavior and critical persisted state, not private
  implementation structure.
- Use `Decimal` values for money and weights; never route expected values through
  binary floating point.
- Assert transaction boundaries when a write spans a recipe and its ingredient
  rows: invalid input must leave no partial changes.
- Include boundary and regression cases named by the issue, especially zero,
  negative values, unit conversion, duplicate relationships, decimal rounding,
  and protected deletion.
- For rendered pages, assert semantic content and stable attributes or roles.
  Avoid brittle assertions against an entire HTML document or Bootstrap's exact
  generated class sequence.

## Completion standard

Before handing implementation to QA:

1. Re-read the issue acceptance criteria.
2. Run the focused tests for the changed area.
3. Run `python -m pytest` and report the command and result.
4. Keep the issue open for independent QA; implementation does not determine its
   own PASS or FAIL verdict.
