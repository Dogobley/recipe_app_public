"""Browser journey through the Compose deployment: cost, adjust, and re-cost recipes.

Run with `python -m pytest e2e`; it needs Docker and Playwright's Chromium.

Ingredient prices are a fixed snapshot of MercadoLibre Colombia listings taken
on 2026-10-13, so the expected results stay deterministic and offline.
"""

from decimal import Decimal

from playwright.sync_api import Page, expect


MERCADOLIBRE = "MercadoLibre Colombia"
UNITS = 10
# The application only reports costs, so the sale price is derived here:
# 50% income per unit means selling each unit at cost plus half its cost.
INCOME_OVER_COST = Decimal("0.50")


def open_section(page: Page, name: str) -> None:
    page.get_by_role("navigation").get_by_role("link", name=name, exact=True).click()


def add_ingredient(page: Page, name: str, brand: str, weight: str, unit: str, price: str) -> None:
    open_section(page, "Ingredients")
    page.get_by_role("link", name="Add ingredient").first.click()
    page.get_by_label("Name").fill(name)
    page.get_by_label("Brand").fill(brand)
    page.get_by_label("Purchase location").fill(MERCADOLIBRE)
    page.get_by_label("Package weight").fill(weight)
    page.get_by_label("Package unit").select_option(unit)
    page.get_by_label("Package price").fill(price)
    page.get_by_role("button", name="Add ingredient").click()
    expect(page.get_by_role("status")).to_contain_text("Ingredient added successfully.")


def update_ingredient_price(page: Page, name: str, price: str) -> None:
    open_section(page, "Ingredients")
    page.get_by_role("link", name=name, exact=True).click()
    page.get_by_role("link", name="Edit ingredient").click()
    page.get_by_label("Package price").fill(price)
    page.get_by_role("button", name="Save ingredient").click()
    expect(page.get_by_role("status")).to_contain_text("Ingredient updated successfully.")


def fill_last_ingredient_row(page: Page, ingredient: str, quantity: str, unit: str) -> None:
    row = page.locator(".recipe-ingredient-row").last
    row.locator('select[name$="-ingredient"]').select_option(label=ingredient)
    row.locator('input[name$="-quantity"]').fill(quantity)
    row.locator('select[name$="-quantity_unit"]').select_option(unit)


def add_recipe(page: Page, name: str, weight_per_unit: str, rows: list[tuple[str, str, str]]) -> None:
    open_section(page, "Recipes")
    page.get_by_role("link", name="Add recipe").first.click()
    page.get_by_label("Name").fill(name)
    page.get_by_label("Weight per unit (g)").fill(weight_per_unit)
    for index, row in enumerate(rows):
        if index:
            page.get_by_role("button", name="Add ingredient row").click()
        fill_last_ingredient_row(page, *row)
    page.get_by_role("button", name="Add recipe").click()
    expect(page.get_by_role("status")).to_contain_text("Recipe added successfully.")


def open_recipe_editor(page: Page, name: str) -> None:
    open_section(page, "Recipes")
    page.get_by_role("link", name=name, exact=True).click()
    page.get_by_role("link", name="Edit recipe").click()


def save_recipe(page: Page) -> None:
    page.get_by_role("button", name="Save recipe").click()
    expect(page.get_by_role("status")).to_contain_text("Recipe updated successfully.")


def recipe_composition(page: Page) -> dict[str, str]:
    """Return the ingredient quantities shown on the recipe detail page."""
    return {
        row.locator("th").inner_text(): row.locator("td").inner_text()
        for row in page.locator("tbody tr").all()
    }


def calculate(page: Page, recipe: str, units: int) -> None:
    open_section(page, "Calculator")
    page.get_by_label("Recipe").select_option(label=recipe)
    page.get_by_label("Units").fill(str(units))
    page.get_by_role("button", name="Calculate").click()
    expect(page.get_by_role("heading", name=f"Calculation for {recipe}")).to_be_visible()


def visible_summary(page: Page) -> dict[str, str]:
    """Return the calculation summary exactly as the page displays it."""
    result = page.get_by_role("region", name="Calculation for")
    terms = result.locator("dt").all_inner_texts()
    values = result.locator("dd").all_inner_texts()
    return dict(zip(terms, values, strict=True))


def visible_ingredients(page: Page) -> dict[str, tuple[str, str]]:
    """Return each displayed ingredient row as (adjusted quantity, cost)."""
    rows = page.get_by_role("region", name="Calculation for").locator("tbody tr").all()
    return {
        row.locator("th").inner_text(): (row.locator("td").nth(0).inner_text(), row.locator("td").nth(1).inner_text())
        for row in rows
    }


def sale_price_for_target_income(page: Page) -> Decimal:
    """Derive the unit sale price from the cost per unit shown on screen."""
    cost_per_unit = Decimal(visible_summary(page)["Cost per unit"].removeprefix("COP $"))
    return cost_per_unit * (1 + INCOME_OVER_COST)


def test_baker_costs_adjusts_and_recosts_recipes_for_ten_units(page: Page) -> None:
    # 1. Create a recipe using MercadoLibre Colombia prices.
    page.goto("/")
    add_ingredient(page, "Harina de trigo", "Panadería", "1", "kg", "10900")
    add_ingredient(page, "Azúcar blanca", "Riopaila", "1", "kg", "6900")
    add_ingredient(page, "Cocoa en polvo", "Cocoa", "250", "g", "14900")
    add_recipe(
        page,
        "Brownie",
        "80",
        [
            ("Harina de trigo", "30", "g"),
            ("Azúcar blanca", "0.04", "kg"),
            ("Cocoa en polvo", "15", "g"),
        ],
    )
    assert recipe_composition(page) == {
        "Azúcar blanca": "0.04 kg",
        "Cocoa en polvo": "15 g",
        "Harina de trigo": "30 g",
    }

    # 2. Produce 10 units to get 50% income per unit.
    calculate(page, "Brownie", UNITS)

    # 3. Validate visible calculations.
    assert visible_summary(page) == {
        "Requested units": "10",
        "Cost per unit": "COP $1497.00",
        "Weight per unit": "80 g",
        "Total cost": "COP $14970.00",
        "Total weight": "850 g",
    }
    assert visible_ingredients(page) == {
        "Azúcar blanca": ("0.4 kg", "COP $2760.00"),
        "Cocoa en polvo": ("150 g", "COP $8940.00"),
        "Harina de trigo": ("300 g", "COP $3270.00"),
    }
    assert sale_price_for_target_income(page) == Decimal("2245.50")

    # 4. Adjust the recipe: remove one ingredient and reprice another.
    open_recipe_editor(page, "Brownie")
    cocoa_row = page.locator(".recipe-ingredient-row").filter(
        has=page.locator('select[name$="-ingredient"] option:checked', has_text="Cocoa en polvo")
    )
    cocoa_row.get_by_role("button", name="Remove row").click()
    expect(cocoa_row).to_be_hidden()
    save_recipe(page)
    assert recipe_composition(page) == {"Azúcar blanca": "0.04 kg", "Harina de trigo": "30 g"}
    update_ingredient_price(page, "Azúcar blanca", "5900")

    # 5. Validate visible calculations.
    calculate(page, "Brownie", UNITS)
    assert visible_summary(page) == {
        "Requested units": "10",
        "Cost per unit": "COP $563.00",
        "Weight per unit": "80 g",
        "Total cost": "COP $5630.00",
        "Total weight": "700 g",
    }
    assert visible_ingredients(page) == {
        "Azúcar blanca": ("0.4 kg", "COP $2360.00"),
        "Harina de trigo": ("300 g", "COP $3270.00"),
    }
    assert sale_price_for_target_income(page) == Decimal("844.50")

    # 6. Add another ingredient to the recipe.
    add_ingredient(page, "Harina integral", "Integral", "1", "kg", "12000")
    open_recipe_editor(page, "Brownie")
    page.get_by_role("button", name="Add ingredient row").click()
    fill_last_ingredient_row(page, "Harina integral", "20", "g")
    save_recipe(page)
    calculate(page, "Brownie", UNITS)
    assert visible_summary(page) == {
        "Requested units": "10",
        "Cost per unit": "COP $803.00",
        "Weight per unit": "80 g",
        "Total cost": "COP $8030.00",
        "Total weight": "900 g",
    }
    assert visible_ingredients(page) == {
        "Azúcar blanca": ("0.4 kg", "COP $2360.00"),
        "Harina de trigo": ("300 g", "COP $3270.00"),
        "Harina integral": ("200 g", "COP $2400.00"),
    }
    assert sale_price_for_target_income(page) == Decimal("1204.50")

    # 7. Cost a new recipe that shares the existing ingredients.
    add_recipe(
        page,
        "Galleta integral",
        "25",
        [("Harina integral", "15", "g"), ("Azúcar blanca", "8", "g")],
    )
    calculate(page, "Galleta integral", UNITS)
    assert visible_summary(page) == {
        "Requested units": "10",
        "Cost per unit": "COP $227.20",
        "Weight per unit": "25 g",
        "Total cost": "COP $2272.00",
        "Total weight": "230 g",
    }
    assert visible_ingredients(page) == {
        "Azúcar blanca": ("80 g", "COP $472.00"),
        "Harina integral": ("150 g", "COP $1800.00"),
    }
    assert sale_price_for_target_income(page) == Decimal("340.80")
