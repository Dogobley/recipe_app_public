# Issue 6: Implement ingredient cost calculation

Status: closed

## Goal

Calculate the cost of any requested amount of an ingredient.

## Acceptance criteria

- [x] The service calculates cost per gram as package price divided by normalized package weight.
- [x] The service calculates requested cost as requested weight in grams multiplied by cost per gram.
- [x] Package and requested quantities can independently use `g` or `kg`, with equivalent weights producing equal costs.
- [x] Fractional package prices and requested quantities retain full configured `Decimal` precision in the returned result.
- [x] The service does not apply display rounding to intermediate values or its final domain result.
- [x] Zero or negative package weights, package prices, and requested quantities are rejected with documented domain errors.
- [x] Unsupported units and invalid decimal inputs are rejected rather than coerced.
- [x] Focused unit tests cover exact-package, proportional, mixed-unit, fractional, precision, and every rejection case above.

## Out of scope

- Weight normalization itself belongs to [Issue 5](issue5.md).
- Scaling and aggregating an entire recipe belongs to [Issue 7](issue7.md).
- HTTP forms and calculator results belong to [Issue 16](issue16.md).
- Currency display and rounding rules belong to [Issue 17](issue17.md).

## Constraints

- Complete [Issues 3](issue3.md) and [5](issue5.md) first and reuse their field conventions and normalization utility.
- Keep calculation code in the domain service layer, independent of requests, templates, and view logic.
- Use `Decimal` throughout; never convert through binary floating-point values.
- Follow the formulas and presentation-boundary rounding rule in the [application architecture](../architecture.md).

## Engineer comment

Implemented the Django-independent `calculate_ingredient_cost` service. It
returns unrounded `cost_per_gram` and `requested_cost` `Decimal` values,
normalizes each input weight through `normalize_weight`, and rejects invalid
prices with `InvalidPackagePriceError` while preserving the normalizer's
documented weight errors. Added focused unit coverage for exact, proportional,
mixed-unit, fractional/precision, and all invalid price, quantity, and unit
cases. `python -m pytest tests/test_ingredient_costs.py` passed (57 tests);
`python -m pytest` passed (125 tests). Ready for QA.

## Engineer follow-up

Addressed QA's unsupported-unit regression: unhashable values such as `[]` and
`{}` now raise the documented `InvalidWeightError` rather than a raw
`TypeError`, both directly and through the cost service. `python -m pytest
tests/test_weight_normalization.py tests/test_ingredient_costs.py` passed (90
tests); `python -m pytest` passed (131 tests). Ready for QA recheck.
