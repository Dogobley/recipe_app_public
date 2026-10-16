"""URLs owned by the calculator application."""

from django.urls import path

from calculator import views


urlpatterns = [
    path("", views.ingredient_list, name="ingredient-list"),
    path("add/", views.ingredient_create, name="ingredient-create"),
    path("<int:pk>/edit/", views.ingredient_edit, name="ingredient-edit"),
    path("<int:pk>/delete/", views.ingredient_delete, name="ingredient-delete"),
    path("<int:pk>/", views.ingredient_detail, name="ingredient-detail"),
]
