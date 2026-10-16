# Issue 14: Build recipe editing

Status: closed

## Goal

Let the user update recipe details and its ingredient rows together.

## Acceptance criteria

- [x] The edit page is pre-populated with the recipe's saved name, weight per unit, and all ingredient rows.
- [x] A valid submission can change recipe fields and existing ingredient quantities or units and redirects to the detail page with a success message.
- [x] A valid submission can add a new ingredient row to the recipe.
- [x] A valid submission can mark an existing ingredient row for deletion without deleting the shared ingredient record.
- [x] The browser controls can add and mark rows for removal while maintaining valid formset management data.
- [x] Duplicate active ingredients, no remaining active ingredient rows, unsupported units, and invalid recipe or quantity values display clear field or formset errors.
- [x] Blank extra rows are ignored.
- [x] If any submitted value or row is invalid, no recipe field, ingredient-row addition, edit, or deletion is persisted.
- [x] An unknown recipe identifier returns HTTP 404 without changing data.
- [x] Request, formset, and transaction tests verify pre-population, each edit operation, combined operations, validation, full rollback, messages, redirects, and missing records.

## Out of scope

- Creating a new recipe belongs to [Issue 13](issue13.md).
- Creating or editing Ingredient records from this page belongs to [Issue 10](issue10.md).
- Recipe deletion belongs to [Issue 15](issue15.md).

## Constraints

- Complete [Issues 4](issue4.md), [12](issue12.md), and [13](issue13.md) first and reuse the creation form and formset where practical.
- Save all recipe and formset changes in one database transaction.
- Keep server-side validation authoritative and use JavaScript only for formset convenience.
- Protect POST submissions with CSRF and use POST/Redirect/GET after success.
- Never delete shared Ingredient records when removing recipe rows.
