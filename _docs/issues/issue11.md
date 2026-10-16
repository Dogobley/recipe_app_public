# Issue 11: Build ingredient deletion

Status: closed

## Goal

Let the user safely delete an ingredient that is no longer needed.

## Acceptance criteria

- [x] The delete-confirmation URL displays the ingredient name and explains that deletion is permanent.
- [x] The confirmation page provides a cancel action that returns to the ingredient detail page without changing data.
- [x] Confirming with POST deletes an unreferenced ingredient, shows a success message, and redirects to the ingredient list.
- [x] Attempting to delete an ingredient used by a recipe leaves all records intact, shows a useful error naming the blocked ingredient, and returns the user to a relevant ingredient page.
- [x] A GET request never deletes an ingredient, and unsupported methods on the delete action are rejected.
- [x] CSRF protection applies to the confirmation submission.
- [x] An unknown ingredient identifier returns HTTP 404 without changing data.
- [x] Request tests verify confirmation, cancellation destination, successful deletion, protected deletion, messages, method handling, CSRF behavior, redirects, and missing records.

## Out of scope

- Creating and editing ingredients belongs to [Issue 10](issue10.md).
- Deleting recipes belongs to [Issue 15](issue15.md).

## Constraints

- Complete [Issues 4](issue4.md), [8](issue8.md), and [9](issue9.md) first and preserve the model's protected relationship behavior.
- Perform deletion only on POST after an explicit server-rendered confirmation page.
- Handle the database protection error as an expected user-facing outcome rather than a server error.
- Never cascade ingredient deletion into recipes or recipe ingredient rows.
