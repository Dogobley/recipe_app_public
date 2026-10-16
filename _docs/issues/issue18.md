# Issue 18: Add end-to-end workflow coverage

Status: closed

## Goal

Verify the complete ingredient-to-calculation workflow through the web interface.

## Acceptance criteria

- [x] An integration test creates ingredients through the web interface, creates a recipe using them, requests multiple units, and verifies every displayed scaled quantity, ingredient cost, total weight, total cost, and cost per unit.
- [x] The primary workflow includes both `g` and `kg` inputs and fractional decimal values with expected formatted results.
- [x] An integration test edits a recipe's fields and ingredient rows and verifies the next calculation uses the updated composition.
- [x] An integration test edits an ingredient package price and verifies a later calculation uses the new price without changing recipe composition.
- [x] An integration test verifies deletion of a referenced ingredient is blocked and that the recipe remains calculable afterward.
- [x] Invalid recipe creation and edit formsets are rejected with visible errors and leave all related database records unchanged.
- [x] A decimal-rounding regression case verifies displayed rounding without loss of precision in the underlying domain result.
- [x] Tests exercise real Django URLs, forms, views, templates, ORM persistence, and PostgreSQL constraints rather than replacing the domain services with mocks.
- [x] The full `python -m pytest` suite passes with the new integration scenarios.

## Out of scope

- Production container smoke coverage belongs to [Issue 19](issue19.md).
- Operator-command verification belongs to [Issue 20](issue20.md).
- New feature behavior remains in its owning issue among [Issues 1–17](issue1.md); this issue only integrates behavior already accepted there.

## Constraints

- Complete [Issues 1–17](issue1.md) before this cross-feature verification work.
- Use pytest, pytest-django, Django's test client, and the configured PostgreSQL test database.
- Keep fixtures or factories focused, readable, and deterministic.
- Assert both user-visible responses and critical persisted state at workflow boundaries.
- Do not depend on test execution order or external network services.
