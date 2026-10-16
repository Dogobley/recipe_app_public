"""Unit tests for the ingredient cost domain service."""

from decimal import Decimal, localcontext

import pytest

from calculator.services.costs import (
    InvalidPackagePriceError,
    calculate_ingredient_cost,
)
from calculator.services.weights import InvalidWeightError


def test_calculate_ingredient_cost_returns_package_cost_per_gram_and_exact_request_cost() -> None:
    result = calculate_ingredient_cost(
        package_price=Decimal("12.00"),
        package_weight=Decimal("600"),
        package_weight_unit="g",
        requested_quantity=Decimal("600"),
        requested_quantity_unit="g",
    )

    assert result.cost_per_gram == Decimal("0.02")
    assert result.requested_cost == Decimal("12.00")


def test_calculate_ingredient_cost_calculates_a_proportional_requested_amount() -> None:
    result = calculate_ingredient_cost(
        package_price=Decimal("7.50"),
        package_weight=Decimal("500"),
        package_weight_unit="g",
        requested_quantity=Decimal("125"),
        requested_quantity_unit="g",
    )

    assert result.cost_per_gram == Decimal("0.015")
    assert result.requested_cost == Decimal("1.875")


@pytest.mark.parametrize(
    ("package_weight", "package_unit", "requested_quantity", "requested_unit"),
    [
        (Decimal("1"), "kg", Decimal("250"), "g"),
        (Decimal("1000"), "g", Decimal("0.250"), "kg"),
    ],
)
def test_calculate_ingredient_cost_normalizes_package_and_requested_units_independently(
    package_weight: Decimal,
    package_unit: str,
    requested_quantity: Decimal,
    requested_unit: str,
) -> None:
    result = calculate_ingredient_cost(
        package_price=Decimal("8.40"),
        package_weight=package_weight,
        package_weight_unit=package_unit,
        requested_quantity=requested_quantity,
        requested_quantity_unit=requested_unit,
    )

    assert result.cost_per_gram == Decimal("0.0084")
    assert result.requested_cost == Decimal("2.1000")


def test_calculate_ingredient_cost_preserves_fractional_inputs_and_decimal_precision() -> None:
    with localcontext() as context:
        context.prec = 40
        result = calculate_ingredient_cost(
            package_price=Decimal("10.123456789"),
            package_weight=Decimal("3"),
            package_weight_unit="g",
            requested_quantity=Decimal("0.123456789"),
            requested_quantity_unit="g",
        )

        expected_cost_per_gram = Decimal("10.123456789") / Decimal("3")
        expected_requested_cost = Decimal("0.123456789") * expected_cost_per_gram

    assert result.cost_per_gram == expected_cost_per_gram
    assert result.requested_cost == expected_requested_cost
    assert result.requested_cost.as_tuple().exponent < Decimal("0.01").as_tuple().exponent


@pytest.mark.parametrize("package_price", [Decimal("0"), 0, Decimal("-0.01"), "-2"])
def test_calculate_ingredient_cost_rejects_zero_or_negative_package_prices(
    package_price: Decimal | int | str,
) -> None:
    with pytest.raises(InvalidPackagePriceError, match="positive"):
        calculate_ingredient_cost(package_price, Decimal("1"), "g", Decimal("1"), "g")


@pytest.mark.parametrize(
    "package_price",
    ["", "   ", "not-a-number", Decimal("NaN"), Decimal("Infinity"), None, True, 0.1],
)
def test_calculate_ingredient_cost_rejects_invalid_package_price_inputs(package_price: object) -> None:
    with pytest.raises(InvalidPackagePriceError):
        calculate_ingredient_cost(package_price, Decimal("1"), "g", Decimal("1"), "g")  # type: ignore[arg-type]


@pytest.mark.parametrize("quantity", [Decimal("0"), 0, Decimal("-0.001"), "-2"])
def test_calculate_ingredient_cost_rejects_non_positive_package_weights(
    quantity: Decimal | int | str,
) -> None:
    with pytest.raises(InvalidWeightError, match="positive"):
        calculate_ingredient_cost(Decimal("1"), quantity, "g", Decimal("1"), "g")


@pytest.mark.parametrize("quantity", [Decimal("0"), 0, Decimal("-0.001"), "-2"])
def test_calculate_ingredient_cost_rejects_non_positive_requested_quantities(
    quantity: Decimal | int | str,
) -> None:
    with pytest.raises(InvalidWeightError, match="positive"):
        calculate_ingredient_cost(Decimal("1"), Decimal("1"), "g", quantity, "g")


@pytest.mark.parametrize(
    "unit", ["", " ", "grams", "lb", "G", "KG", "Kg", None, [], {}]
)
def test_calculate_ingredient_cost_rejects_invalid_package_weight_units(unit: object) -> None:
    with pytest.raises(InvalidWeightError, match="exactly 'g' or 'kg'"):
        calculate_ingredient_cost(Decimal("1"), Decimal("1"), unit, Decimal("1"), "g")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "unit", ["", " ", "grams", "lb", "G", "KG", "Kg", None, [], {}]
)
def test_calculate_ingredient_cost_rejects_invalid_requested_weight_units(unit: object) -> None:
    with pytest.raises(InvalidWeightError, match="exactly 'g' or 'kg'"):
        calculate_ingredient_cost(Decimal("1"), Decimal("1"), "g", Decimal("1"), unit)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "quantity",
    ["", "   ", "not-a-number", Decimal("NaN"), Decimal("Infinity"), None, True, 0.1],
)
def test_calculate_ingredient_cost_rejects_invalid_package_weight_inputs(quantity: object) -> None:
    with pytest.raises(InvalidWeightError):
        calculate_ingredient_cost(Decimal("1"), quantity, "g", Decimal("1"), "g")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "quantity",
    ["", "   ", "not-a-number", Decimal("NaN"), Decimal("Infinity"), None, True, 0.1],
)
def test_calculate_ingredient_cost_rejects_invalid_requested_quantity_inputs(quantity: object) -> None:
    with pytest.raises(InvalidWeightError):
        calculate_ingredient_cost(Decimal("1"), Decimal("1"), "g", quantity, "g")  # type: ignore[arg-type]
