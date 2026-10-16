# Issue 12: Build the recipe list and detail pages

Status: closed

## Goal

Let the user browse recipes and inspect their ingredient quantities.

## Acceptance criteria

- [x] The recipe list URL returns a server-rendered page showing every saved recipe in model ordering.
- [x] Each list entry shows the recipe name and weight per unit in grams and links to its detail page.
- [x] The list page offers a visible create-recipe action.
- [x] With no recipes, the list shows a clear empty-state message and create-recipe action.
- [x] The detail page shows the recipe name, weight per unit, and every linked ingredient with its stored quantity and unit in deterministic order.
- [x] A recipe with no ingredients shows a clear ingredient empty state rather than an empty table.
- [x] The detail page provides visible actions to return to the list, edit, delete, and calculate the recipe.
- [x] An unknown recipe identifier returns HTTP 404.
- [x] Request tests verify populated and empty lists, recipe and ingredient empty states, displayed values and links, ordering, bounded query count, and missing records.

## Out of scope

- Recipe creation, editing, and deletion belong to [Issues 13](issue13.md), [14](issue14.md), and [15](issue15.md).
- Performing and displaying calculations belongs to [Issue 16](issue16.md).
- Final currency and weight formatting belongs to [Issue 17](issue17.md).

## Constraints

- Complete [Issues 4](issue4.md) and [8](issue8.md) first and reuse their models and base template.
- Use Django views, URLs, and server-rendered templates without an API or client-side data fetching.
- Prefetch recipe ingredient rows and their ingredients so detail-page query count does not grow with ingredient count.
- Keep this issue read-only: no filtering, searching, pagination, or write handling.
