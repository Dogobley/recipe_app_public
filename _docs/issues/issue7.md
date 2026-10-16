# Issue 7: Implement recipe scaling and totals

Status: closed

## Goal

Produce ingredient quantities, ingredient costs, total weight, total cost, and cost per unit for a requested unit count.

## Acceptance criteria

- [x] Given a recipe and a positive whole-number unit count, the service returns one result row for every recipe ingredient.
- [x] Each result row identifies the ingredient and contains its scaled quantity, unit, normalized gram weight, and proportional cost.
- [x] The result contains the recipe's cost per unit and weight per unit plus total ingredient cost and total normalized weight for the requested count.
- [x] A count of one preserves each stored recipe quantity and produces the unscaled totals.
- [x] Counts greater than one multiply each quantity, ingredient cost, and total by exactly that count.
- [x] Mixed `g` and `kg` ingredient quantities aggregate correctly in grams.
- [x] All returned numeric values use `Decimal` and retain full configured precision without display rounding.
- [x] Zero, negative, fractional, boolean, blank, and otherwise invalid unit counts are rejected with a documented domain error.
- [x] A recipe with no ingredient rows returns a documented empty result with zero ingredient total cost and weight rather than failing.
- [x] Focused tests cover single- and multi-ingredient recipes, one and many units, mixed units, decimal prices, empty recipes, aggregation, precision, and all invalid counts.

## Out of scope

- Editing recipe composition belongs to [Issues 13](issue13.md) and [14](issue14.md).
- Rendering or validating the calculator web page belongs to [Issue 16](issue16.md).
- Currency and weight display rounding belongs to [Issue 17](issue17.md).
- End-to-end browser workflow coverage belongs to [Issue 18](issue18.md).

## Constraints

- Complete [Issues 4](issue4.md), [5](issue5.md), and [6](issue6.md) first and reuse their models and calculation services.
- Keep the service independent of HTTP requests, forms, and templates.
- Use grams for aggregate weight and `Decimal` for all weights and costs.
- Do not persist calculation results, inventory movements, or historical costs.

## Engineer comment

Implemented `calculate_recipe` with documented `InvalidUnitCountError` in the
domain service layer.  It returns one unrounded `RecipeIngredientResult` per
persisted recipe ingredient, preserves the scaled stored unit, normalizes every
row and aggregate to grams, and returns cost/weight per unit plus ingredient
totals. Empty recipes produce empty rows and zero ingredient totals without any
writes. Added focused coverage for one and many units, multiple ingredients,
mixed units, decimal precision, aggregation, empty recipes, and invalid unit
counts. `python -m pytest tests/test_recipe_calculations.py` passed (21 tests)
and `python -m pytest` passed (152 tests). Ready for QA; issue remains open.
