"""Integration tests that exercise the real Compose deployment over HTTP.

Run them with `python -m pytest -m compose`; they need a running Docker daemon.
"""

import re
import time
from uuid import uuid4

import pytest

from tests.compose.conftest import run_compose, valid_environment, write_env_file


pytestmark = pytest.mark.compose


def unique(name: str) -> str:
    """Name records uniquely so tests do not depend on execution order."""
    return f"{name} {uuid4().hex[:8]}"


def created_pk(response) -> str:
    match = re.search(r"/(\d+)/$", response.url)
    assert match, f"Expected a redirect to a detail page, got {response.url}"
    return match.group(1)


def create_ingredient(browser, name: str, **overrides: str) -> str:
    data = {
        "name": name,
        "brand": "Mill House",
        "place_of_purchase": "Market",
        "package_weight": "1.250",
        "package_weight_unit": "kg",
        "package_price": "10.01",
        **overrides,
    }
    response = browser.submit("/ingredients/add/", data)
    assert response.status == 200
    assert "Ingredient added successfully." in response.text
    return created_pk(response)


def create_recipe(browser, name: str, flour_pk: str, cocoa_pk: str) -> str:
    response = browser.submit(
        "/recipes/add/",
        {
            "name": name,
            "weight_per_unit": "137.500",
            "ingredients-TOTAL_FORMS": "2",
            "ingredients-INITIAL_FORMS": "0",
            "ingredients-MIN_NUM_FORMS": "0",
            "ingredients-MAX_NUM_FORMS": "1000",
            "ingredients-0-ingredient": cocoa_pk,
            "ingredients-0-quantity": "12.500",
            "ingredients-0-quantity_unit": "g",
            "ingredients-1-ingredient": flour_pk,
            "ingredients-1-quantity": "0.125",
            "ingredients-1-quantity_unit": "kg",
        },
    )
    assert response.status == 200
    assert "Recipe added successfully." in response.text
    return created_pk(response)


def create_workflow_recipe(browser) -> tuple[str, str, str]:
    flour_pk = create_ingredient(browser, unique("Flour"))
    cocoa_pk = create_ingredient(
        browser,
        unique("Cocoa"),
        package_weight="250.000",
        package_weight_unit="g",
        package_price="1.01",
    )
    return flour_pk, cocoa_pk, create_recipe(browser, unique("Fractional cake"), flour_pk, cocoa_pk)


# Startup and container contract


def test_both_services_start_and_report_healthy(stack) -> None:
    services = stack.services()

    assert services["db"]["Health"] == "healthy"
    assert services["web"]["Health"] == "healthy"


def test_only_the_web_port_is_published_to_the_host(stack) -> None:
    services = stack.services()

    assert all(port["PublishedPort"] == 0 for port in services["db"]["Publishers"] or [])
    assert any(
        port["TargetPort"] == 8000 and port["PublishedPort"] > 0 for port in services["web"]["Publishers"]
    )


def test_startup_applies_every_migration(stack) -> None:
    result = stack.compose("exec", "-T", "web", "python", "manage.py", "migrate", "--check", check=False)

    assert result.returncode == 0, result.stdout + result.stderr


def test_web_container_runs_gunicorn_as_a_non_root_user(stack) -> None:
    user_id = stack.compose("exec", "-T", "web", "id", "-u").stdout.strip()
    main_process = stack.compose("exec", "-T", "web", "cat", "/proc/1/cmdline").stdout

    assert user_id != "0"
    assert "gunicorn" in main_process


# Documented smoke check


def test_health_endpoint_confirms_database_connectivity(browser) -> None:
    response = browser.get("/health/")

    assert response.status == 200
    assert response.text == "OK"


def test_home_page_renders_the_application_shell(browser) -> None:
    response = browser.get("/")

    assert response.status == 200
    assert 'href="/ingredients/"' in response.text
    assert 'href="/recipes/"' in response.text
    assert 'href="/calculator/"' in response.text


def test_collected_stylesheet_is_served_by_the_web_container(browser) -> None:
    response = browser.get("/static/calculator/site.css")

    assert response.status == 200
    assert response.headers["Content-Type"].startswith("text/css")


# Production hardening


def test_unknown_url_returns_a_generic_404_without_debug_details(browser) -> None:
    response = browser.get("/no-such-page/")

    assert response.status == 404
    assert "DEBUG = True" not in response.text
    assert "URLconf" not in response.text


def test_request_for_a_host_outside_allowed_hosts_is_rejected(browser) -> None:
    response = browser.get("/", headers={"Host": "attacker.example"})

    assert response.status == 400


def test_post_without_a_csrf_token_is_rejected_and_saves_nothing(browser) -> None:
    name = unique("Forged ingredient")

    response = browser.request(
        "/ingredients/add/",
        {
            "name": name,
            "brand": "None",
            "place_of_purchase": "None",
            "package_weight": "1",
            "package_weight_unit": "kg",
            "package_price": "1.00",
        },
    )

    assert response.status == 403
    assert name not in browser.get("/ingredients/").text


# User workflows against PostgreSQL


def test_complete_workflow_calculates_a_scaled_recipe_cost(browser) -> None:
    _, _, recipe_pk = create_workflow_recipe(browser)

    response = browser.submit("/calculator/", {"recipe": recipe_pk, "units": "3"})

    assert response.status == 200
    for visible_value in ("COP $1.05", "137.5 g", "37.5 g", "COP $0.15", "0.375 kg", "COP $3.00", "COP $3.15", "412.5 g"):
        assert visible_value in response.text


def test_ingredient_price_edit_changes_later_calculations(browser) -> None:
    flour_pk, _, recipe_pk = create_workflow_recipe(browser)

    edit = browser.submit(
        f"/ingredients/{flour_pk}/edit/",
        {
            "name": unique("Flour"),
            "brand": "Mill House",
            "place_of_purchase": "Market",
            "package_weight": "1.250",
            "package_weight_unit": "kg",
            "package_price": "20.02",
        },
    )
    response = browser.submit("/calculator/", {"recipe": recipe_pk, "units": "3"})

    assert "Ingredient updated successfully." in edit.text
    assert "COP $6.01" in response.text
    assert "COP $6.16" in response.text


def test_invalid_ingredient_is_rejected_with_the_form_redisplayed(browser) -> None:
    name = unique("Weightless ingredient")

    response = browser.submit(
        "/ingredients/add/",
        {
            "name": name,
            "brand": "Mill House",
            "place_of_purchase": "Market",
            "package_weight": "0",
            "package_weight_unit": "kg",
            "package_price": "10.01",
        },
    )

    assert response.status == 200
    assert response.url.endswith("/ingredients/add/")
    assert "Ingredient added successfully." not in response.text
    assert name not in browser.get("/ingredients/").text


def test_ingredient_used_by_a_recipe_cannot_be_deleted(browser) -> None:
    flour_pk, _, recipe_pk = create_workflow_recipe(browser)

    response = browser.submit(f"/ingredients/{flour_pk}/delete/", {})

    assert response.status == 200
    assert "cannot be deleted because it is used by a recipe" in response.text
    assert browser.get(f"/ingredients/{flour_pk}/").status == 200
    calculation = browser.submit("/calculator/", {"recipe": recipe_pk, "units": "3"})
    assert "COP $3.15" in calculation.text


def test_deleting_a_recipe_keeps_its_ingredients(browser) -> None:
    flour_pk, cocoa_pk, recipe_pk = create_workflow_recipe(browser)

    response = browser.submit(f"/recipes/{recipe_pk}/delete/", {})

    assert response.status == 200
    assert "deleted successfully." in response.text
    assert browser.get(f"/recipes/{recipe_pk}/").status == 404
    assert browser.get(f"/ingredients/{flour_pk}/").status == 200
    assert browser.get(f"/ingredients/{cocoa_pk}/").status == 200


# Operations: outages, shutdown, and persistence. Each test restores the stack.


def test_health_endpoint_reports_a_database_outage_and_recovers(stack) -> None:
    try:
        stack.compose("stop", "db")
        outage = stack.browser().get("/health/")
    finally:
        stack.up()

    assert outage.status == 500
    assert outage.text == "Database unavailable."
    assert stack.browser().get("/health/").status == 200


def test_web_container_stops_gracefully_within_the_grace_period(stack) -> None:
    try:
        started = time.monotonic()
        stack.compose("stop", "web")
        elapsed = time.monotonic() - started
        stopped = stack.services()["web"]
    finally:
        stack.up()

    assert stopped["State"] == "exited"
    # Exit code 137 would mean Docker had to SIGKILL the process.
    assert stopped["ExitCode"] == 0
    assert elapsed < 35


def test_saved_data_survives_removing_and_recreating_the_containers(stack) -> None:
    name = unique("Persistent sugar")
    ingredient_pk = create_ingredient(stack.browser(), name)

    stack.compose("down")
    stack.up()

    response = stack.browser().get(f"/ingredients/{ingredient_pk}/")
    assert response.status == 200
    assert name in response.text


# Misconfiguration fails fast


@pytest.mark.parametrize("missing", ["DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "POSTGRES_PASSWORD"])
def test_compose_refuses_a_missing_required_variable(tmp_path, missing) -> None:
    environment = valid_environment()
    del environment[missing]
    env_file = write_env_file(tmp_path / "incomplete.env", environment)

    result = run_compose(env_file, "config", "--quiet")

    assert result.returncode != 0
    assert f"Set {missing}" in result.stderr


@pytest.mark.parametrize(
    ("variable", "value", "message"),
    [
        ("DJANGO_SECRET_KEY", "replace-with-a-long-random-secret", "must not use an example placeholder"),
        ("DJANGO_DEBUG", "true", "DJANGO_DEBUG must be false"),
    ],
)
def test_web_container_refuses_unsafe_production_settings(stack, variable, value, message) -> None:
    result = stack.compose(
        "run", "--rm", "--no-deps", "-T", "-e", f"{variable}={value}", "web", "python", "manage.py", "check",
        check=False,
    )

    assert result.returncode != 0
    assert message in result.stderr
