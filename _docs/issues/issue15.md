# Issue 15: Build recipe deletion

Status: closed

## Goal

Let the user delete a recipe after explicit confirmation.

## Acceptance criteria

- [x] The delete-confirmation URL displays the recipe name and explains that its recipe ingredient rows will also be removed.
- [x] The confirmation page provides a cancel action that returns to the recipe detail page without changing data.
- [x] Confirming with POST deletes the recipe and all of its `RecipeIngredient` rows.
- [x] Ingredients referenced by the deleted recipe remain available, including ingredients shared with another recipe.
- [x] Successful deletion shows a message and redirects to the recipe list.
- [x] A GET request never deletes a recipe, and unsupported methods on the delete action are rejected.
- [x] CSRF protection applies to the confirmation submission.
- [x] An unknown recipe identifier returns HTTP 404 without changing data.
- [x] Request tests verify confirmation, cancellation destination, cascade cleanup, ingredient preservation, messages, redirects, method handling, CSRF behavior, and missing records.

## Out of scope

- Ingredient deletion belongs to [Issue 11](issue11.md).

## Constraints

- Complete [Issues 4](issue4.md), [8](issue8.md), and [12](issue12.md) first.
- Perform deletion only on POST after an explicit server-rendered confirmation page.
- Rely on the model relationship's cascade for recipe ingredient rows and never cascade to Ingredient records.
- Use the shared Django messages area for confirmation feedback.
