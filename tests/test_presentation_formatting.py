"""Template-focused tests for shared money and weight presentation."""

from decimal import Decimal

import pytest
from django.template import Context, Template

from calculator.templatetags.presentation import format_currency, format_weight


def render(template_source: str, **context: object) -> str:
    """Render a small template using the production presentation filters."""
    return Template(template_source).render(Context(context))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("5"), "COP $5.00"),
        (Decimal("5.500"), "COP $5.50"),
        (Decimal("1.005"), "COP $1.01"),
        (Decimal("9.995"), "COP $10.00"),
        (Decimal("0.004"), "COP $0.00"),
        (Decimal("-0.004"), "COP $0.00"),
    ],
)
def test_currency_template_filter_formats_money_with_half_up_rounding(
    value: Decimal, expected: str
) -> None:
    assert render("{% load presentation %}{{ value|currency }}", value=value) == expected


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (Decimal("5.000"), "g", "5 g"),
        (Decimal("0.250"), "kg", "0.25 kg"),
        (Decimal("1.2345"), "g", "1.235 g"),
        (Decimal("0.0004"), "kg", "0 kg"),
        (Decimal("-0.0004"), "g", "0 g"),
    ],
)
def test_weight_template_filter_keeps_units_and_removes_insignificant_zeros(
    value: Decimal, unit: str, expected: str
) -> None:
    assert render("{% load presentation %}{{ value|weight:unit }}", value=value, unit=unit) == expected


@pytest.mark.parametrize(
    ("formatter", "value", "unit"),
    [
        (format_currency, None, None),
        (format_currency, "not-a-number", None),
        (format_currency, Decimal("NaN"), None),
        (format_weight, None, "g"),
        (format_weight, "not-a-number", "kg"),
        (format_weight, Decimal("1"), "oz"),
    ],
)
def test_invalid_or_missing_presentation_values_are_not_rendered_as_zero(
    formatter: object, value: object, unit: str | None
) -> None:
    if unit is None:
        rendered = formatter(value)  # type: ignore[operator]
    else:
        rendered = formatter(value, unit)  # type: ignore[operator]
    assert rendered == "—"


def test_presentation_rounding_does_not_mutate_the_source_decimal() -> None:
    money = Decimal("1.005")
    weight = Decimal("1.2345")

    assert format_currency(money) == "COP $1.01"
    assert format_weight(weight, "g") == "1.235 g"
    assert money == Decimal("1.005")
    assert weight == Decimal("1.2345")
