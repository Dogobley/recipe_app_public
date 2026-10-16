# Issue 13: Build recipe creation

Status: closed

## Goal

Let the user create a recipe and its ingredient rows in one submission.

## Acceptance criteria

- [x] The create page displays recipe name and positive weight-per-unit fields together with at least one ingredient row.
- [x] Each ingredient row lets the user select an existing ingredient and enter a positive quantity in `g` or `kg`.
- [x] The user can add and remove unsaved ingredient rows in the browser, and formset management data remains correct after those actions.
- [x] Submitting a valid recipe with one or more ingredient rows saves the recipe and all rows once, shows a success message, and redirects to its detail page.
- [x] Blank recipe fields, non-positive weight, missing ingredients, unsupported units, and non-positive or non-numeric quantities show errors beside the relevant field or row.
- [x] Selecting the same ingredient in multiple active rows shows a clear formset error and saves nothing.
- [x] A completely blank extra row is ignored, while submitting no completed ingredient rows shows a clear error and saves nothing.
- [x] Deleting a newly added browser row does not submit or save that row.
- [x] Any invalid recipe or ingredient row prevents both the recipe and every ingredient row from being persisted.
- [x] Request, form, and formset tests verify valid creation, row addition/removal contract, blank rows, duplicate ingredients, invalid fields, atomicity, messages, and redirect behavior.

## Out of scope

- Creating ingredients from within the recipe page belongs to [Issue 10](issue10.md).
- Editing an existing recipe belongs to [Issue 14](issue14.md).
- Calculating recipe costs belongs to [Issue 16](issue16.md).

## Constraints

- Complete [Issues 4](issue4.md), [8](issue8.md), and [12](issue12.md) first.
- Use a Django `ModelForm` and inline formset, saving the recipe and its ingredient rows in one database transaction.
- Keep server validation authoritative; JavaScript may only add or mark formset rows for deletion.
- Protect POST submissions with CSRF and use POST/Redirect/GET after success.
- Do not permit creation of an ingredient implicitly from free text.

## Engineer comment

Implemented recipe creation with a `RecipeForm`, an inline ingredient formset,
and one atomic save transaction. The responsive server-rendered form includes an
initial ingredient row, accessible field and formset errors, and progressive
JavaScript controls that add rows or mark rows for deletion while updating
`TOTAL_FORMS`. Server-side validation requires at least one active row, rejects
duplicate ingredients and invalid values, ignores blank extra rows, and leaves
no partial recipe data after an invalid submission. Added request and formset
coverage in `tests/test_recipe_creation.py`.

Verification: `python -m pytest tests/test_recipe_creation.py
tests/test_recipe_pages.py` passed (19 tests); `python -m pytest` passed (208
tests). Ready for independent QA; issue remains pending.
