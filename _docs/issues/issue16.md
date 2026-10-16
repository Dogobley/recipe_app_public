# Issue 16: Build the recipe calculator page

Status: closed

## Goal

Let the user select a recipe and number of units and see a complete cost calculation.

## Acceptance criteria

- [x] The calculator page displays a recipe selector and a required units field.
- [x] The recipe selector lists every saved recipe in model ordering and handles an empty recipe catalog with a clear message and link to create one.
- [x] The units field accepts positive whole numbers and rejects zero, negatives, fractions, booleans, blank input, and non-numeric input with a field-specific message.
- [x] A valid submission displays the selected recipe, requested unit count, cost per unit, weight per unit, each ingredient's adjusted quantity and cost, total cost, and total weight.
- [x] Ingredient rows appear in their deterministic model ordering.
- [x] A valid recipe containing no ingredients produces a clear no-ingredients result with zero ingredient total cost and weight rather than a server error.
- [x] Invalid submissions preserve the selected recipe and entered units and do not invoke or display a stale calculation.
- [x] An identifier for a recipe that does not exist or is no longer selectable is rejected with a form error rather than a server error.
- [x] Calculations are read-only and create, update, or delete no database records.
- [x] Request tests verify initial, empty-catalog, valid, invalid, missing-recipe, empty-recipe, ordering, displayed-result, and read-only behavior.

## Out of scope

- Calculation formulas and scaling behavior belong to [Issues 6](issue6.md) and [7](issue7.md).
- Creating or editing recipes belongs to [Issues 13](issue13.md) and [14](issue14.md).
- Final currency and weight formatting belongs to [Issue 17](issue17.md).

## Constraints

- Complete [Issues 7](issue7.md), [8](issue8.md), and [12](issue12.md) first.
- Use a Django form, server-rendered view, and the existing recipe-scaling domain service; do not duplicate calculation logic in the view or template.
- Keep authoritative validation on the server and protect any POST submission with CSRF.
- Do not persist calculation results or add client-side calculation logic.
