"""Checks that the README's description of the application matches the code.

The worked example is rebuilt here and run through the real calculation service
and display formatting, every page the Features section names must resolve, and
every link in the Project map must point at something in the repository.
"""

import re
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import pytest
from django.urls import Resolver404, resolve, reverse

from calculator.models import Ingredient, Recipe, RecipeIngredient
from calculator.services.costs import calculate_ingredient_cost
from calculator.services.recipes import calculate_recipe
from calculator.templatetags.presentation import format_currency, format_weight


PROJECT_ROOT = Path(__file__).resolve().parents[1]
README = PROJECT_ROOT / "README.md"
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def read_readme() -> str:
    return README.read_text(encoding="utf-8")


def section(document: str, heading: str, level: int = 2) -> str:
    """Return the body of a heading up to the next heading of the same or a higher level."""
    marker = "#" * level
    start = document.index(f"\n{marker} {heading}\n")
    following = re.compile(rf"^#{{1,{level}}} ", re.MULTILINE)
    end = following.search(document, start + 1 + len(marker) + 1 + len(heading))
    return document[start : end.start() if end else None]


def tables(text: str) -> list[list[list[str]]]:
    """Return every Markdown table in `text` as rows of stripped cells, without the header rule."""
    found, current = [], []
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                current.append(cells)
        elif current:
            found.append(current)
            current = []
    if current:
        found.append(current)
    return found


def slug(heading: str) -> str:
    """GitHub's anchor for a heading: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def anchors(document: str) -> set[str]:
    return {slug(match) for match in re.findall(r"^#{1,6} (.+)$", document, flags=re.MULTILINE)}


def words(text: str) -> str:
    return " ".join(text.split())


# Opening and section order


def test_readme_intro_states_audience_and_problem_without_saying_in_progress() -> None:
    readme = read_readme()
    intro = words(readme.split("\n## Quick start\n", 1)[0])

    assert "in-progress" not in intro.lower()
    assert "small confectionery producer" in intro
    assert "what does one unit of a recipe cost, and what does a batch of N units cost?" in intro
    assert "package" in intro and "spreadsheet" in intro and "unit-conversion" in intro


def test_readme_puts_features_after_quick_start_then_expected_behaviour_and_ends_with_project_map() -> None:
    headings = re.findall(r"^## (.+)$", read_readme(), flags=re.MULTILINE)

    assert headings[:3] == ["Quick start", "Features", "Expected behaviour"]
    assert headings[-1] == "Project map"


def test_direct_python_setup_says_to_create_the_virtual_environment_once() -> None:
    setup = words(section(read_readme(), "Direct Python setup"))

    assert setup.count("Create and activate a virtual environment, then install dependencies:") == 1
    assert setup.lower().count("create and activate a virtual environment") == 1


# Features


FEATURE_URL_NAMES = {
    "ingredient-list", "ingredient-create", "ingredient-detail", "ingredient-edit", "ingredient-delete",
    "recipe-list", "recipe-create", "recipe-detail", "recipe-edit", "recipe-delete",
    "recipe-calculator", "health",
}


def test_every_page_named_in_features_resolves_and_every_feature_page_is_named() -> None:
    features = section(read_readme(), "Features")
    paths = re.findall(r"`(/[^`]*)`", features)

    resolved = set()
    for documented in paths:
        path = documented.replace("<id>", "1").split("?", 1)[0]
        try:
            resolved.add(resolve(path).url_name)
        except Resolver404:
            pytest.fail(f"README Features names {documented}, which no URL pattern serves")

    assert FEATURE_URL_NAMES <= resolved


# Worked example


@dataclass(frozen=True)
class ExampleIngredient:
    name: str
    package_weight: Decimal
    package_weight_unit: str
    package_price: Decimal
    quantity: Decimal
    quantity_unit: str


EXAMPLE_RECIPE = "Chocolate truffles"
EXAMPLE_WEIGHT_PER_UNIT = Decimal("19.5")
EXAMPLE_UNITS = 24
EXAMPLE_INGREDIENTS = (
    ExampleIngredient("Cocoa powder", Decimal("250"), "g", Decimal("13500"), Decimal("1.5"), "g"),
    ExampleIngredient("Dark chocolate 53%", Decimal("1"), "kg", Decimal("46900"), Decimal("12"), "g"),
    ExampleIngredient("Heavy cream", Decimal("900"), "g", Decimal("17900"), Decimal("6"), "g"),
)


def short_decimal(value: Decimal, places: int) -> str:
    """Write `value` exactly when it fits in `places` decimals, else cut it there and add an ellipsis."""
    quantum = Decimal(1).scaleb(-places)
    cut = value.quantize(quantum, rounding=ROUND_DOWN)
    text = f"{cut.normalize():f}"
    return text if cut == value else f"{cut:f}…"


def create_example() -> Recipe:
    recipe = Recipe.objects.create(name=EXAMPLE_RECIPE, weight_per_unit=EXAMPLE_WEIGHT_PER_UNIT)
    for item in EXAMPLE_INGREDIENTS:
        ingredient = Ingredient.objects.create(
            name=item.name,
            brand="Example brand",
            place_of_purchase="Example shop",
            package_weight=item.package_weight,
            package_weight_unit=item.package_weight_unit,
            package_price=item.package_price,
        )
        RecipeIngredient.objects.create(
            recipe=recipe, ingredient=ingredient, quantity=item.quantity, quantity_unit=item.quantity_unit
        )
    return recipe


def test_worked_example_uses_a_kilogram_package_used_in_grams_for_several_units() -> None:
    assert len(EXAMPLE_INGREDIENTS) >= 2
    assert any(item.package_weight_unit == "kg" and item.quantity_unit == "g" for item in EXAMPLE_INGREDIENTS)
    assert EXAMPLE_UNITS > 1


@pytest.mark.django_db
def test_worked_example_figures_match_the_calculation_service_and_display_formatting(client) -> None:
    example = section(read_readme(), "Worked example", level=3)
    inputs, ingredient_rows, results = tables(example)
    recipe = create_example()

    calculation = calculate_recipe(recipe, EXAMPLE_UNITS)

    assert f"**{EXAMPLE_RECIPE}**" in example
    assert f"weight per unit of `{format_weight(EXAMPLE_WEIGHT_PER_UNIT, 'g')}`" in example
    assert f"Calculating **{EXAMPLE_UNITS}** units" in example
    assert inputs == [["Ingredient", "Package weight", "Package price", "Quantity per unit"]] + [
        [
            item.name,
            format_weight(item.package_weight, item.package_weight_unit),
            format_currency(item.package_price),
            format_weight(item.quantity, item.quantity_unit),
        ]
        for item in EXAMPLE_INGREDIENTS
    ]
    assert ingredient_rows == [["Ingredient", "Adjusted quantity", "Cost"]] + [
        [row.ingredient.name, format_weight(row.scaled_quantity, row.unit), format_currency(row.ingredient_cost)]
        for row in calculation.ingredient_results
    ]
    assert results == [
        ["Result", "Value"],
        ["Requested units", str(EXAMPLE_UNITS)],
        ["Cost per unit", format_currency(calculation.cost_per_unit)],
        ["Weight per unit", format_weight(calculation.weight_per_unit, "g")],
        ["Total cost", format_currency(calculation.total_ingredient_cost)],
        ["Total weight", format_weight(calculation.total_normalized_weight, "g")],
    ]

    # The prose around the tables: each cost per gram, the exact cost per unit,
    # and the total a reader would get by multiplying the rounded cost per unit.
    prose = words(example)
    for item in EXAMPLE_INGREDIENTS:
        grams = item.package_weight * (1000 if item.package_weight_unit == "kg" else 1)
        cost_per_gram = calculate_ingredient_cost(
            item.package_price, item.package_weight, item.package_weight_unit, "1", "g"
        ).cost_per_gram
        assert f"{item.package_price} / {grams} = {short_decimal(cost_per_gram, 3)}" in prose
    rounded_cost_per_unit = Decimal(format_currency(calculation.cost_per_unit).removeprefix("COP $"))
    assert f"The exact cost per unit is COP ${short_decimal(calculation.cost_per_unit, 4)}" in prose
    assert (
        f"is COP ${calculation.total_ingredient_cost:.2f} and not {EXAMPLE_UNITS} × "
        f"{format_currency(calculation.cost_per_unit)} = COP ${rounded_cost_per_unit * EXAMPLE_UNITS}"
    ) in prose

    # The calculator page shows the same figures.
    page = client.post(reverse("recipe-calculator"), {"recipe": recipe.pk, "units": EXAMPLE_UNITS})
    content = page.content.decode()
    assert page.status_code == 200
    for figure in [cell for row in ingredient_rows[1:] + results[1:] for cell in row[1:]]:
        assert figure in content, figure


# Project map


PROJECT_MAP_TOPICS = [
    "Problem description",
    "Product specification and task tracker",
    "Agent team",
    "Context management",
    "Application",
    "Testing",
    "Containerization",
    "Deployment",
    "CI/CD",
    "Observability",
    "Alerting",
    "On-call agent",
]


def project_map_rows() -> dict[str, list[str]]:
    (table,) = tables(section(read_readme(), "Project map"))
    assert table[0] == ["Topic", "Where", "How to check"]
    return {row[0]: row for row in table[1:]}


def test_project_map_has_one_row_per_topic_in_order_each_with_a_link_and_a_check() -> None:
    rows = project_map_rows()

    assert list(rows) == PROJECT_MAP_TOPICS
    for topic, (_, where, check) in rows.items():
        assert LINK.search(where), topic
        assert check, topic


def test_every_project_map_link_points_into_the_repository() -> None:
    readme = read_readme()
    targets = [target for row in project_map_rows().values() for target in LINK.findall(" ".join(row))]

    assert targets
    for target in targets:
        assert not re.match(r"^[a-z]+:", target), f"{target} is not a repository path"
        path, _, fragment = target.partition("#")
        if not path:
            assert fragment in anchors(readme), f"README has no heading for #{fragment}"
            continue
        file = PROJECT_ROOT / path
        assert file.exists(), f"{target} does not exist"
        if fragment:
            assert fragment in anchors(file.read_text(encoding="utf-8")), f"{path} has no heading for #{fragment}"


def test_project_map_marks_unfinished_work_as_open_or_planned() -> None:
    rows = project_map_rows()
    deployment = words(" ".join(rows["Deployment"]))
    observability = words(" ".join(rows["Observability"]))

    assert "[Issue 33](_docs/issues/issue33.md)" in deployment
    assert "Status: open" in (PROJECT_ROOT / "_docs" / "issues" / "issue33.md").read_text(encoding="utf-8")
    assert "logs correlated by trace ID are planned and not built yet" in observability


def test_project_map_deployment_row_says_which_jobs_are_skipped_without_a_runner() -> None:
    deployment = words(" ".join(project_map_rows()["Deployment"]))
    gated = [
        (PROJECT_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        for name in ("build.yml", "deploy-observability.yml")
    ]
    manual = [
        (PROJECT_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        for name in ("deploy.yml", "promote-to-production.yml")
    ]

    assert "the jobs gated by `SELF_HOSTED_RUNNER`" in deployment and "show as skipped" in deployment
    assert "**Build and push**" in deployment and "**Deploy observability**" in deployment
    assert all("if: vars.SELF_HOSTED_RUNNER == 'true'" in workflow for workflow in gated)
    assert "not gated, so a run would wait for a runner" in deployment
    assert all("SELF_HOSTED_RUNNER" not in workflow for workflow in manual)


def test_project_map_observability_row_does_not_put_traces_on_the_dashboard() -> None:
    observability = words(" ".join(project_map_rows()["Observability"]))
    dashboard = (
        PROJECT_ROOT / "observability" / "grafana" / "provisioning" / "dashboards" / "recipe-business-metrics.json"
    ).read_text(encoding="utf-8")

    assert "Traces go to Tempo and are viewed in Grafana **Explore**" in observability
    assert "metrics go to Prometheus and are shown on the provisioned business-metrics dashboard" in observability
    assert "tempo" not in dashboard.lower()


ISSUES_DIR = PROJECT_ROOT / "_docs" / "issues"
WITH_ENGINEER_AND_QA = {22, 23, 24, 26, 27, 28, 29, 30, 31, 34}
WITH_CLOSING_COMMENT = {24, 25, 26, 27, 28, 29, 30, 31, 34}


def test_project_map_task_tracker_row_matches_the_issue_files() -> None:
    tracker = words(" ".join(project_map_rows()["Product specification and task tracker"]))
    issues = {
        int(match.group(1)): path.read_text(encoding="utf-8")
        for path in ISSUES_DIR.glob("issue*.md")
        if (match := re.fullmatch(r"issue(\d+)\.md", path.name))
    }

    assert "Every `issueN.md` has a status line and acceptance criteria." in tracker
    assert "Issues 22 to 31 and 34 also carry an Engineer comment and a QA verdict" in tracker
    assert "Issue 25, a live check, records live runs instead of a QA verdict" in tracker
    assert "Issues 24 to 31 and 34 include the orchestrator's closing comment" in tracker
    for number, text in issues.items():
        assert re.search(r"^Status: ", text, re.MULTILINE), number
        assert "\n## Acceptance criteria\n" in text, number
    for number in WITH_ENGINEER_AND_QA:
        assert "\n## Engineer comment" in issues[number] and "\n## QA" in issues[number], number
    assert "\n## Engineer comment" in issues[25] and "\n## Live run" in issues[25]
    for number in WITH_CLOSING_COMMENT:
        assert "\n## Closed by orchestrator" in issues[number], number
