# Issue 17: Define and apply display formatting

Status: closed

## Goal

Present weights and currency consistently throughout the application.

## Acceptance criteria

- [x] Every user-facing monetary value is prefixed with `COP $` and displayed with exactly two decimal places.
- [x] Monetary display rounds to the nearest cent using `ROUND_HALF_UP`, including values exactly halfway between two cents.
- [x] User-facing gram and kilogram values display up to three decimal places, remove insignificant trailing zeros, and retain their explicit unit label.
- [x] The same reusable formatting implementation is used on ingredient, recipe, and calculator pages rather than page-specific formatting.
- [x] Negative zero is never displayed for either money or weight.
- [x] Formatting does not alter stored values, domain-service results, subsequent totals, or other intermediate precision.
- [x] Invalid or missing numeric values are not silently rendered as zero.
- [x] Template-focused tests cover whole values, trailing zeros, fractional values, half-cent rounding, values that round across a whole-number boundary, very small values, and negative-zero prevention.
- [x] Existing page tests verify that formatted values appear consistently on every page that displays money or weight.

## Out of scope

- Changing model field precision belongs to [Issues 3](issue3.md) and [4](issue4.md).
- Changing calculation formulas belongs to [Issues 6](issue6.md) and [7](issue7.md).

## Constraints

- Complete [Issues 9](issue9.md), [12](issue12.md), and [16](issue16.md) before applying formatting across their pages.
- Use `Decimal` and explicit decimal rounding; never convert values through binary floating point.
- Round only in reusable presentation-layer code, consistent with the [application architecture](../architecture.md).
- Keep the application single-currency and do not introduce locale-detection or currency-conversion dependencies.
