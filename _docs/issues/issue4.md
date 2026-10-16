# Issue 4: Create the Recipe data models

Status: closed

## Goal

Persist each recipe and the quantity of every ingredient it uses, with database-level protection against invalid or duplicate rows.

## Acceptance criteria

- [x] `Recipe` stores a required name and a weight per unit in grams; the weight per unit rejects zero and negative values through model validation and a database constraint.
- [x] Recipe querysets are ordered by name by default, and a recipe's displayed string is its name.
- [x] `RecipeIngredient` links one recipe to one `Ingredient` and stores a required quantity plus a unit limited to `g` or `kg`.
- [x] A recipe can contain several different ingredients, and an ingredient can be used by several recipes.
- [x] A recipe cannot contain the same ingredient more than once; duplicate pairs are rejected by both model validation and a database uniqueness constraint.
- [x] Recipe ingredient quantities reject zero and negative values through model validation and a database constraint.
- [x] Recipe ingredient querysets have a deterministic default ordering by ingredient name and then primary key.
- [x] Deleting a recipe also deletes its `RecipeIngredient` rows and leaves all linked `Ingredient` records intact.
- [x] Deleting an ingredient used by at least one recipe is blocked and leaves the recipe and its ingredient rows intact.
- [x] Both models are registered in Django Admin, where recipe ingredient records have a readable representation that identifies the recipe and ingredient.
- [x] A migration creates both models and all specified database constraints, and it applies successfully to an empty test database.
- [x] Automated model tests demonstrate every relationship, validation rule, database constraint, deletion behavior, ordering rule, and string representation above.

## Out of scope

- Weight conversion belongs to [Issue 5](issue5.md).
- Ingredient cost calculation belongs to [Issue 6](issue6.md).
- Recipe scaling and total calculations belong to [Issue 7](issue7.md).
- Recipe browsing belongs to [Issue 12](issue12.md), creation to [Issue 13](issue13.md), editing to [Issue 14](issue14.md), and deletion to [Issue 15](issue15.md).
- Calculator pages belong to [Issue 16](issue16.md).
- Currency and weight display formatting belongs to [Issue 17](issue17.md).

## Constraints

- Complete [Issue 3](issue3.md) first; these relationships use its `Ingredient` model rather than defining another ingredient entity.
- Keep changes within the Django application's models, admin registration, migrations, and focused model tests.
- Use Django ORM relationships and database constraints consistent with the [application architecture](../architecture.md).
- Store weights and quantities with decimal fields suitable for `Decimal` arithmetic; do not use binary floating-point fields.
- Store recipe weight per unit canonically in grams. Preserve `g` or `kg` on each recipe ingredient quantity for later normalization.

## Engineer comment

Implemented `Recipe` and `RecipeIngredient` with decimal fields, model and database validation, ordering, relationships, deletion behavior, admin registrations, migration `0002_recipe_recipeingredient`, and focused model coverage. `python -m pytest tests/test_recipe_models.py` passed (19 tests) and `python -m pytest` passed (41 tests) in the host test environment. PostgreSQL Compose verification remains for QA: the shared volume was initialized with credentials different from the local placeholder configuration, so an isolated test project was started without modifying that shared data; its health check was interrupted before the suite could run.
