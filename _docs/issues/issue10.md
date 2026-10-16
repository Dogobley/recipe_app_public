# Issue 10: Build ingredient create and edit pages

Status: closed

## Goal

Let the user add and update ingredients through validated forms.

## Acceptance criteria

- [x] The create page displays fields for name, brand, purchase location, package weight, package unit, and package price.
- [x] Submitting valid values creates one ingredient, shows a success message, and redirects to its detail page using POST/Redirect/GET.
- [x] The edit page is pre-populated with the selected ingredient's current values.
- [x] Submitting valid edits updates that ingredient without creating another, shows a success message, and redirects to its detail page.
- [x] Required fields, unsupported units, non-numeric values, and zero or negative package weights and prices display field-specific errors.
- [x] An invalid submission creates or updates nothing and re-renders the form with all valid submitted values preserved.
- [x] An unknown ingredient identifier on the edit URL returns HTTP 404.
- [x] GET displays forms, POST performs writes, and unsupported HTTP methods are rejected.
- [x] Request and form tests verify every success, validation, preservation, redirect, method, and missing-record behavior above.

## Out of scope

- Ingredient list and detail presentation belongs to [Issue 9](issue9.md).
- Ingredient deletion belongs to [Issue 11](issue11.md).
- Recipe forms belong to [Issues 13](issue13.md) and [14](issue14.md).
- Final currency and weight formatting belongs to [Issue 17](issue17.md).

## Constraints

- Complete [Issues 3](issue3.md), [8](issue8.md), and [9](issue9.md) first and reuse their model, layout, and detail route.
- Use one Django `ModelForm` for both create and edit flows.
- Keep authoritative validation on the server and rely on model constraints as the persistence backstop.
- Protect all POST submissions with Django CSRF handling.
- Do not add bulk import, inline recipe assignment, or client-side-only validation.
