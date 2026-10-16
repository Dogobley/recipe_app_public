"""Root URL configuration."""

from django.contrib import admin
from django.conf import settings
from django.db import DatabaseError, connection
from django.http import HttpResponse, HttpResponseServerError
from django.urls import include, path, re_path
from django.views.static import serve
from django.shortcuts import render

from calculator import views


def home(request):
    """Render the shared application shell."""
    return render(request, "home.html")


def health(request):
    """Report readiness only after the application can query its database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return HttpResponseServerError("Database unavailable.", content_type="text/plain")
    return HttpResponse("OK", content_type="text/plain")


urlpatterns = [
    path("", home, name="home"),
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("ingredients/", include("calculator.urls")),
    path("recipes/", views.recipe_list, name="recipe-list"),
    path("recipes/add/", views.recipe_create, name="recipe-create"),
    path("recipes/<int:pk>/edit/", views.recipe_edit, name="recipe-edit"),
    path("recipes/<int:pk>/delete/", views.recipe_delete, name="recipe-delete"),
    path("recipes/<int:pk>/", views.recipe_detail, name="recipe-detail"),
    path("calculator/", views.recipe_calculator, name="recipe-calculator"),
    # The web container owns static delivery; no separate frontend service is
    # required for this deliberately small deployment.
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
]
