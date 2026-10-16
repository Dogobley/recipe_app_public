# Issue 9: Build the ingredient list and detail pages

Status: closed

## Goal

Let the user browse saved ingredient pricing information.

## Acceptance criteria

- [x] The ingredient list URL returns a server-rendered page showing every saved ingredient in model ordering.
- [x] Each list entry shows the ingredient name, brand, purchase location, package weight with unit, and package price.
- [x] Each list entry links to that ingredient's detail page, and the page offers a visible create-ingredient action.
- [x] With no ingredients, the list shows a clear empty-state message and a create-ingredient action instead of an empty table.
- [x] The ingredient detail URL shows the selected ingredient's complete saved pricing and package information.
- [x] The detail page provides visible actions to return to the list, edit the ingredient, and request deletion.
- [x] An unknown ingredient identifier returns HTTP 404.
- [x] Request tests verify populated and empty lists, displayed fields and links, detail output, ordering, query count, and missing records.

## Out of scope

- Creating and editing ingredients belongs to [Issue 10](issue10.md).
- Deleting ingredients belongs to [Issue 11](issue11.md).
- Recipe usage of ingredients belongs to [Issues 12](issue12.md), [13](issue13.md), and [14](issue14.md).
- Final currency and weight formatting belongs to [Issue 17](issue17.md).

## Constraints

- Complete [Issues 3](issue3.md) and [8](issue8.md) first and reuse their model and base template.
- Use Django views, URLs, and server-rendered templates; do not add an API or client-side data fetching.
- Fetch the list in a constant number of database queries and the detail record in one query.
- Keep this issue read-only: no list filtering, searching, pagination, or write handling.

## Engineer comment

Implemented read-only ingredient list and detail views, routes, and responsive
server-rendered templates using the shared application layout. The list follows
the model ordering, has a distinct empty state, and shows all saved package and
pricing fields. The detail view returns 404 for unknown identifiers and exposes
the requested list, edit, and delete actions. Added request tests for populated
and empty lists, fields, links, ordering, bounded query counts, detail output,
and missing records. `python -m pytest tests/test_ingredient_pages.py` passed
(4 tests); `python -m pytest` passed (159 tests). Ready for QA; issue remains
open.
