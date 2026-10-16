# Issue 3: Create the Ingredient data model

Status: closed

## Goal

Persist ingredients and their package pricing information.

## Acceptance criteria

- [x] `Ingredient` stores required name, brand, place of purchase, package weight, package weight unit, and package price values.
- [x] Package weight units are limited to `g` and `kg`.
- [x] Package weight and package price reject zero and negative values through model validation and database constraints.
- [x] Package weight and price use decimal fields and preserve valid fractional values.
- [x] Ingredient querysets are ordered by name and then primary key by default.
- [x] An ingredient's displayed string is its name.
- [x] The model is registered in Django Admin with its pricing and package information inspectable.
- [x] A migration creates the model and its constraints and applies successfully to an empty test database.
- [x] Automated model tests demonstrate all fields, supported units, validation rules, database constraints, ordering, and string representation above.

## Out of scope

- Recipe relationships and protected deletion behavior belong to [Issue 4](issue4.md).
- Weight normalization belongs to [Issue 5](issue5.md).
- Cost calculation belongs to [Issue 6](issue6.md).
- Ingredient browsing and write workflows belong to [Issues 9](issue9.md), [10](issue10.md), and [11](issue11.md).
- Display-only currency and weight formatting belongs to [Issue 17](issue17.md).

## Constraints

- Complete [Issue 1](issue1.md) before adding the model and migration.
- Keep changes within the Django application's models, admin registration, migrations, and focused model tests.
- Use Django ORM fields, validators, and database constraints consistent with the [application architecture](../architecture.md).
- Use decimal rather than binary floating-point fields for weights and prices.
- Do not add inventory quantities, multiple currencies, or price-history fields.
