"""Fixtures that open a real browser against the isolated Compose deployment."""

import os

import pytest
from playwright.sync_api import sync_playwright

# Reuse the session fixture that builds, starts, and removes the Compose stack.
from tests.compose.conftest import stack  # noqa: F401


@pytest.fixture(scope="session")
def chromium():
    with sync_playwright() as playwright:
        # Set E2E_HEADED=1 to watch the browser drive the application.
        browser = playwright.chromium.launch(headless=os.environ.get("E2E_HEADED") != "1")
        yield browser
        browser.close()


@pytest.fixture
def page(chromium, stack):
    context = chromium.new_context(base_url=stack.base_url)
    # Bootstrap comes from a CDN; block it so the run never depends on the internet.
    context.route("**/cdn.jsdelivr.net/**", lambda route: route.abort())
    page = context.new_page()
    page.set_default_timeout(10_000)
    yield page
    context.close()
