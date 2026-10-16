from django.conf import settings
from django.contrib.messages import constants as message_constants
from django.contrib.messages.storage.fallback import FallbackStorage
from django import forms
from django.template import Context, Template
from django.test import Client, RequestFactory
from django.contrib.staticfiles import finders


class _ExampleForm(forms.Form):
    name = forms.CharField()

    def clean(self):
        raise forms.ValidationError("Form-level error.")

    def clean_name(self):
        raise forms.ValidationError("Name error.")


def test_django_settings_load() -> None:
    """The project can initialize Django using its configured settings module."""
    assert settings.ROOT_URLCONF == "config.urls"


def test_root_url_renders_shared_base_layout() -> None:
    """The application shell exposes its primary landmarks and navigation."""
    response = Client().get("/")

    assert response.status_code == 200
    assert b"<main" in response.content
    assert b"<footer" in response.content
    assert b'href="/ingredients/"' in response.content
    assert b'href="/recipes/"' in response.content
    assert b'href="/calculator/"' in response.content
    assert b"{% block content %}" not in response.content


def test_base_layout_marks_current_navigation_and_renders_messages() -> None:
    """The base template conveys the active destination and shared feedback."""
    request = RequestFactory().get("/recipes/")
    request.session = {}
    messages = FallbackStorage(request)
    messages.add(message_constants.SUCCESS, "Recipe saved.")
    request._messages = messages

    response = Template('{% extends "base.html" %}{% block content %}<h1>Content</h1>{% endblock %}').render(
        Context({"request": request, "messages": messages})
    )

    assert 'href="/recipes/" aria-current="page"' in response
    assert 'class="nav-link active"' in response
    assert 'aria-label="Notifications"' in response
    assert "Recipe saved." in response
    assert 'role="status"' in response


def test_shared_form_error_partial_renders_field_and_non_field_errors() -> None:
    """The reusable form-error partial exposes accessible error feedback."""
    rendered = Template(
        "{% include 'includes/form_errors.html' with form=form field=form.name %}"
    ).render(Context({"form": _ExampleForm({"name": "bad"})}))

    assert "Please correct the errors below." in rendered
    assert "Form-level error." in rendered
    assert "Name error." in rendered
    assert 'id="id_name-errors"' in rendered


def test_project_stylesheet_is_discoverable_by_django_staticfiles() -> None:
    """The base layout's local stylesheet can be collected for deployment."""
    stylesheet = finders.find("calculator/site.css")

    assert stylesheet is not None
