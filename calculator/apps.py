"""Application configuration for the recipe cost calculator."""

from django.apps import AppConfig


class CalculatorConfig(AppConfig):
    """Configure the calculator application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "calculator"
