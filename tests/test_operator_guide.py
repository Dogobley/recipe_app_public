from pathlib import Path


def test_operator_guide_is_discoverable_and_covers_operational_workflows():
    """Keep the documented operator path discoverable as deployment files evolve."""
    repository_root = Path(__file__).resolve().parents[1]
    readme = (repository_root / "README.md").read_text(encoding="utf-8")
    guide = (repository_root / "docs" / "operator-guide.md").read_text(
        encoding="utf-8"
    )

    assert "docs/operator-guide.md" in readme
    for required_text in (
        "docker compose up --build --detach",
        "docker compose exec -T web python manage.py showmigrations",
        "pg_dump",
        "psql -v ON_ERROR_STOP=1",
        "Restore",
        "Update and rollback",
        "requirements.txt",
        "Troubleshooting",
        "POSTGRES_PASSWORD",
        "DJANGO_SECRET_KEY",
    ):
        assert required_text in guide
