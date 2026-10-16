"""Unit tests for domain weight normalization."""

from decimal import Decimal

import pytest

from calculator.services.weights import InvalidWeightError, normalize_weight


@pytest.mark.parametrize(
    ("quantity", "expected"),
    [
        (1, Decimal("1")),
        (Decimal("12.375"), Decimal("12.375")),
        (Decimal("0.0000000000000000000001"), Decimal("0.0000000000000000000001")),
        ("0.100", Decimal("0.100")),
    ],
)
def test_normalize_weight_returns_gram_quantities_unchanged(
    quantity: Decimal | int | str, expected: Decimal
) -> None:
    assert normalize_weight(quantity, "g") == expected
    assert isinstance(normalize_weight(quantity, "g"), Decimal)


@pytest.mark.parametrize(
    ("quantity", "expected"),
    [
        (1, Decimal("1000")),
        (Decimal("1.2345"), Decimal("1234.5000")),
        (Decimal("0.0000000000000000000001"), Decimal("0.0000000000000000001000")),
    ],
)
def test_normalize_weight_converts_kilograms_to_grams_without_rounding(
    quantity: Decimal | int, expected: Decimal
) -> None:
    assert normalize_weight(quantity, "kg") == expected


@pytest.mark.parametrize("quantity", [Decimal("0"), 0, Decimal("-0.001"), "-2"])
def test_normalize_weight_rejects_non_positive_quantities(quantity: Decimal | int | str) -> None:
    with pytest.raises(InvalidWeightError, match="positive"):
        normalize_weight(quantity, "g")


@pytest.mark.parametrize(
    "unit", ["", " ", "grams", "lb", "G", "KG", "Kg", None, [], {}]
)
def test_normalize_weight_rejects_blank_unknown_and_differently_cased_units(unit: object) -> None:
    with pytest.raises(InvalidWeightError, match="exactly 'g' or 'kg'"):
        normalize_weight(Decimal("1"), unit)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "quantity",
    ["", "   ", "not-a-number", Decimal("NaN"), Decimal("Infinity"), None, True, 0.1],
)
def test_normalize_weight_rejects_invalid_decimal_quantities(quantity: object) -> None:
    with pytest.raises(InvalidWeightError):
        normalize_weight(quantity, "g")  # type: ignore[arg-type]
