# Issue 5: Implement weight normalization

Status: closed

## Goal

Convert all supported ingredient quantities to a consistent gram value.

## Acceptance criteria

- [x] The domain utility returns an unchanged gram value when given a positive quantity in `g`.
- [x] The utility returns exactly 1,000 times the input when given a positive quantity in `kg`.
- [x] Integer, fractional, and very small positive decimal quantities are returned as `Decimal` values without binary floating-point artifacts.
- [x] Zero and negative quantities are rejected with a documented domain error.
- [x] Blank, unknown, and differently cased unit values are rejected rather than guessed or silently converted.
- [x] Input values that cannot be represented as valid decimal quantities are rejected with a documented error.
- [x] Focused unit tests cover both supported units, decimal boundaries, and every rejection case above without accessing HTTP or the database.

## Out of scope

- Ingredient and recipe persistence belongs to [Issues 3](issue3.md) and [4](issue4.md).
- Applying package prices to normalized weights belongs to [Issue 6](issue6.md).
- Scaling complete recipes belongs to [Issue 7](issue7.md).
- Formatting weights for display belongs to [Issue 17](issue17.md).

## Constraints

- Keep the utility in the domain service layer and independent of Django requests, forms, templates, and ORM models.
- Use `Decimal` for all arithmetic and grams as the canonical result unit.
- Support only the `g` and `kg` unit values defined by the [application architecture](../architecture.md).
- Do not round valid conversion results.

## Engineer comment

Implemented the Django-independent `normalize_weight` domain utility and its documented `InvalidWeightError`. It preserves valid gram `Decimal` values, converts kilograms exactly with `Decimal("1000")`, and rejects invalid quantities and non-exact units. Added focused unit coverage for supported units, decimal boundaries, and every rejection case. `python -m pytest tests/test_weight_normalization.py` passed (27 tests); `python -m pytest` passed (68 tests). Ready for QA.
