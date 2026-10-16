"""Forms for ingredient and recipe data entry."""

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from calculator.models import Ingredient, Recipe, RecipeIngredient


class IngredientForm(forms.ModelForm):
    """Validate the package details needed to save an ingredient."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            widget.attrs["class"] = (
                "form-select" if isinstance(widget, forms.Select) else "form-control"
            )

    class Meta:
        model = Ingredient
        fields = [
            "name",
            "brand",
            "place_of_purchase",
            "package_weight",
            "package_weight_unit",
            "package_price",
        ]
        labels = {
            "place_of_purchase": "Purchase location",
            "package_weight": "Package weight",
            "package_weight_unit": "Package unit",
            "package_price": "Package price",
        }
        widgets = {
            "package_weight": forms.NumberInput(
                attrs={"min": "0.001", "step": "0.001"}
            ),
            "package_price": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }


class RecipeForm(forms.ModelForm):
    """Validate the top-level fields for a recipe."""

    class Meta:
        model = Recipe
        fields = ["name", "weight_per_unit"]
        labels = {"weight_per_unit": "Weight per unit (g)"}
        widgets = {
            "weight_per_unit": forms.NumberInput(
                attrs={"class": "form-control", "min": "0.001", "step": "0.001"}
            ),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class RecipeCalculatorForm(forms.Form):
    """Validate the recipe and whole-unit request for a calculation."""

    recipe = forms.ModelChoiceField(
        queryset=Recipe.objects.none(),
        empty_label="Select a recipe",
        error_messages={"required": "Select a recipe.", "invalid_choice": "Select a valid recipe."},
    )
    units = forms.IntegerField(
        min_value=1,
        error_messages={
            "required": "Enter a positive whole number.",
            "invalid": "Enter a positive whole number.",
            "min_value": "Enter a positive whole number.",
        },
        widget=forms.NumberInput(attrs={"min": "1", "step": "1"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["recipe"].queryset = Recipe.objects.all()
        self.fields["recipe"].widget.attrs["class"] = "form-select"
        self.fields["units"].widget.attrs["class"] = "form-control"


class RecipeIngredientForm(forms.ModelForm):
    """Validate a single ingredient quantity used by a recipe."""

    class Meta:
        model = RecipeIngredient
        fields = ["ingredient", "quantity", "quantity_unit"]
        labels = {"quantity_unit": "Unit"}
        widgets = {
            "quantity": forms.NumberInput(
                attrs={"class": "form-control", "min": "0.001", "step": "0.001"}
            ),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["ingredient"].queryset = Ingredient.objects.order_by("name", "pk")
        self.fields["quantity_unit"].choices = [
            ("", "Select a unit"),
            *RecipeIngredient.QuantityUnit.choices,
        ]
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class", "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            )


class BaseRecipeIngredientFormSet(BaseInlineFormSet):
    """Require one unique, completed ingredient row for every recipe."""

    def clean(self) -> None:
        super().clean()
        active_input_exists = any(
            any(
                form.data.get(form.add_prefix(field), "")
                for field in ("ingredient", "quantity", "quantity_unit")
            )
            and not form.data.get(form.add_prefix("DELETE"), "")
            for form in self.forms
        )
        if not active_input_exists:
            raise forms.ValidationError("Add at least one ingredient to the recipe.")
        if any(self.errors):
            return

        ingredients = set()
        completed_rows = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            ingredient = form.cleaned_data.get("ingredient")
            if ingredient is None:
                continue
            completed_rows += 1
            if ingredient.pk in ingredients:
                raise forms.ValidationError(
                    "Each ingredient may only be used once in a recipe."
                )
            ingredients.add(ingredient.pk)

        if not completed_rows:
            raise forms.ValidationError("Add at least one ingredient to the recipe.")

    def validate_unique(self) -> None:
        """Use the clearer formset-level duplicate validation above."""
        return


RecipeIngredientFormSet = inlineformset_factory(
    Recipe,
    RecipeIngredient,
    form=RecipeIngredientForm,
    formset=BaseRecipeIngredientFormSet,
    extra=1,
    can_delete=True,
)
