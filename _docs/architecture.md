# Application Architecture

## Overview

This project uses a conventional Django monolith. Django owns the HTTP endpoints, business rules, database access, form validation, and HTML rendering; there is no separate frontend application or public API.

The application is intended for one user, uses one currency, and calculates recipe costs from ingredient prices and weights. Authentication, inventory, labor, packaging, overhead, and multiple currencies are outside the current scope.

## Technology Stack

- Python 3.13
- Django 5.2 LTS
- PostgreSQL
- psycopg 3 PostgreSQL driver
- Django templates, forms, and formsets
- Bootstrap 5
- Minimal vanilla JavaScript
- pytest and pytest-django
- Gunicorn
- OpenTelemetry (request tracing and application metrics for the Django backend)
- Docker Compose

## System Context

```text
Browser
  |
  | HTTP request / server-rendered HTML response
  v
Django application
  |-- Views and forms
  |-- Domain calculation services
  |-- Django ORM
  |-- Templates and static assets
  |
  v
PostgreSQL
```

The browser receives complete HTML pages from Django. Vanilla JavaScript is limited to interface conveniences such as adding or removing recipe ingredient formset rows; calculations and validation remain authoritative on the server.

## Application Structure

The codebase should separate web concerns from business calculations:

```text
project configuration
  |-- settings, root URLs, WSGI/ASGI
  |
application
  |-- models and database constraints
  |-- forms and formsets
  |-- views and application flow
  |-- services for conversions and calculations
  |-- templates and static assets
  |-- tests
```

### Presentation layer

Django views accept requests, coordinate forms or services, and render templates. Templates display data and reusable UI components but do not perform cost calculations. Bootstrap supplies the layout and styling, with a small amount of local CSS where necessary.

### Validation layer

Django forms and formsets validate user input before it reaches the domain services. Model fields, model validation, and PostgreSQL constraints protect persistent data from invalid values such as zero or negative weights and prices.

### Domain layer

Plain Python services implement weight conversion, proportional ingredient cost, recipe scaling, totals, and rounding rules. These services must not depend on requests, views, or templates so they can be tested directly and reused from any future interface.

### Persistence layer

Django models and the ORM provide access to PostgreSQL. Views should fetch related recipe and ingredient records efficiently, while migrations define all schema changes.

## Data Model

### Ingredient

An ingredient stores:

- Name
- Brand
- Place of purchase
- Package weight
- Package weight unit (`g` or `kg`)
- Package price

Package weight and package price must be greater than zero. Deleting an ingredient referenced by a recipe should be blocked to prevent an existing recipe from becoming incomplete.

### Recipe

A recipe stores:

- Name
- Weight per unit in grams

Weight per unit must be greater than zero.

### RecipeIngredient

This intermediate entity connects a recipe to an ingredient and stores:

- Recipe
- Ingredient
- Quantity used
- Quantity unit (`g` or `kg`)

Quantity must be greater than zero, and the same ingredient should appear at most once in a recipe. Deleting a recipe deletes its RecipeIngredient rows but never deletes shared Ingredient records.

## Calculation Model

Grams are the canonical internal weight unit. User-entered kilograms are converted to grams before costs or totals are calculated.

For an ingredient:

```text
cost per gram = package price / package weight in grams
ingredient cost = requested weight in grams * cost per gram
```

For a requested number of units, each recipe ingredient quantity and cost is multiplied by that unit count. The result contains:

- Cost per unit
- Weight per unit
- Adjusted weight and cost for every ingredient
- Total ingredient cost
- Total weight

All money and weight calculations use `Decimal`, never binary floating-point values. Intermediate calculations retain full configured precision; rounding for display happens only at the presentation boundary according to one shared currency-formatting rule.

## Main Request Flows

### Ingredient management

1. The user opens an ingredient list or form.
2. Django validates submitted ingredient data.
3. The ORM creates, updates, or safely deletes the record.
4. Django redirects after a successful write and displays a status message.

### Recipe management

1. The user submits a recipe form and its ingredient formset.
2. Django validates the recipe and all ingredient rows.
3. The recipe and its rows are saved together in a database transaction.
4. If any row is invalid, no partial recipe changes are saved.

### Recipe calculation

1. The user selects a recipe and enters a positive whole number of units.
2. The view loads the recipe and related ingredients.
3. The domain service normalizes weights, scales quantities, and calculates costs.
4. The view renders the complete result in a server-generated HTML page.

Calculations are read-only and do not create inventory movements or historical cost records.

## URL and Page Design

The initial interface consists of:

- Ingredient list, detail, create, edit, and delete-confirmation pages
- Recipe list, detail, create, edit, and delete-confirmation pages
- Recipe calculator form and result page

State-changing operations use POST requests and Django CSRF protection. Create and update actions follow POST/Redirect/GET so browser refreshes do not repeat submissions.

## Error Handling

- Invalid user input is returned on the same form with field-specific messages.
- Missing records return HTTP 404 responses.
- Unsupported units and invalid calculation inputs are rejected explicitly.
- Attempts to delete referenced ingredients display a useful error instead of silently altering recipes.
- Unexpected errors are logged by Django and use generic production error pages.

## Testing Strategy

pytest and pytest-django cover the system at several levels:

- Unit tests for weight conversion, proportional cost, scaling, totals, and rounding
- Model tests for relationships, validation, and database constraints
- Form and formset tests for accepted and rejected input
- View tests for responses, redirects, permissions implied by HTTP methods, and displayed results
- Integration tests for the complete ingredient-to-recipe-to-calculation workflow

The test suite uses a PostgreSQL test database so database behavior matches production. Without the `DJANGO_DB_*` variables a local run falls back to SQLite; CI always runs it against PostgreSQL.

## Deployment

Docker Compose runs two primary services:

- `web`: Django served by Gunicorn
- `db`: PostgreSQL with a persistent volume

Two environments run from the same `compose.yaml` on one host: dev (`.env`, Compose project named after the deploy folder, port 8000) and production (`.env.prod`, project `recipe-cost-calculator-prod`, port 8001). They are separate Compose projects with their own containers, network and database volume, and differ only in their env files; `.env.prod.example` is the production template. There is one branch, `main`. Each image is built once and tagged `YYYYMMDD-HHMMSS-shortsha`; every deployment checks out the commit named by that tag and uses its `compose.yaml`, and promotion to production retags the release dev is running instead of rebuilding.

Continuous integration runs on GitHub-hosted `ubuntu-latest` runners with no secrets: the **CI** workflow (`.github/workflows/ci.yml`) runs `python -m pytest` against a PostgreSQL 17 service container (**tests**) and `python -m pytest -m compose` plus `python -m pytest e2e` (**integration**). It runs on every pull request and has no push trigger; on a push to `main`, **Build and push** (`build.yml`) calls it as its first job, so the tests run once per push and the image build and dev deploy on the self-hosted runner start only after they pass. The automatically triggered self-hosted jobs (the build and dev deploy, and **Deploy observability**) run only when the repository variable `SELF_HOSTED_RUNNER` is `true`; on a repository without the runner they are skipped. The manual Deploy and Promote dev to production workflows are not gated.

For local evaluation, the same `compose.yaml` also starts from a fresh clone with the tracked, public `quickstart.env` (`docker compose --env-file quickstart.env up --build --detach`): Compose project `recipe-cost-calculator-quickstart`, port 8080, with its own containers, network and database volume. It is not a deployment environment; dev and production never read it.

Configuration and secrets come from environment variables. Container startup applies the expected deployment checks, static assets are collected for production, and the application exposes a lightweight health endpoint suitable for container health checks.

The backend is instrumented with OpenTelemetry. Each request span and emitted
metric identifies the deployment through the standard `service.name`,
`deployment.environment`, and `service.version` resource attributes. Spans and
metrics are exported to an OTLP endpoint when one is configured and otherwise
written to the container's standard output. Business metrics track recipes
created, recipe views, and the average recipe cost.

Redis, background workers, a reverse proxy, and a separate frontend build service are not required for the initial scope. They should only be introduced when a concrete operational requirement justifies them.

## Architectural Constraints

- Keep the application as one deployable Django monolith.
- Keep authoritative validation and calculations on the server.
- Keep domain services independent of HTTP and template code.
- Store monetary values with decimal database fields.
- Normalize weights to grams for calculations.
- Use database transactions for multi-record recipe writes.
- Avoid adding an API, SPA framework, or asynchronous processing without a new requirement.
