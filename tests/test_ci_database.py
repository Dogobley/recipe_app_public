"""Proof that a CI test run used the database the CI workflow configured.

The **tests** job in `.github/workflows/ci.yml` sets
`CI_EXPECTED_DATABASE_VENDOR=postgresql` next to the `DJANGO_DB_*` variables
that point Django at its PostgreSQL service. If those variables were lost and
the suite silently fell back to SQLite, this test fails the run. Without the
variable (a plain local run) there is nothing to prove, so the test is skipped.
"""

import os

import pytest
from django.db import connection


EXPECTED_VENDOR = os.environ.get("CI_EXPECTED_DATABASE_VENDOR", "").strip()


@pytest.mark.skipif(not EXPECTED_VENDOR, reason="CI_EXPECTED_DATABASE_VENDOR is not set (set by the CI tests job)")
@pytest.mark.django_db
def test_test_suite_runs_against_the_database_vendor_ci_expects() -> None:
    assert connection.vendor == EXPECTED_VENDOR

    # A real round trip through the test database, not just the configured engine.
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
    if EXPECTED_VENDOR == "postgresql":
        # pytest-django's own test database on the server, never the configured one.
        assert connection.settings_dict["NAME"].startswith("test_")
