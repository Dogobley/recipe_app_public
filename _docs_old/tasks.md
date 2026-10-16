# Backlog

## 1. Set up the empty Django project
Goal: Create a runnable empty project with one passing automated test.
Description: Initialize a Python 3.13 and Django 5.2 project configured to use pytest and pytest-django, and add a basic smoke test. Include dependency management, environment-variable configuration, and brief commands for installing dependencies, running the server, and running the test suite.

## 2. Add the local PostgreSQL environment
Goal: Run the Django application and PostgreSQL together through Docker Compose.
Description: Add container definitions for the web application and database, including persistent database storage, health checks, and environment-based credentials. Document how to start the services, apply migrations, run tests, and stop the environment without requiring PostgreSQL on the host.

## 3. Create the Ingredient data model
Goal: Persist ingredients and their package pricing information.
Description: Add an Ingredient model containing name, brand, place of purchase, package weight, package weight unit, and package price. Enforce positive weight and price values, provide a useful display name, create the migration, register the model in Django Admin, and add model tests.

## 4. Create the Recipe data models
Goal: Persist recipes and the quantities of ingredients they use.
Description: Add a Recipe model with a name and positive weight per unit, plus an intermediate RecipeIngredient model linking an ingredient to a recipe with a positive quantity and unit. Define ordering and uniqueness rules, create migrations, register the models in Django Admin, and cover their constraints and relationships with tests.

## 5. Implement weight normalization
Goal: Convert all supported ingredient quantities to a consistent gram value.
Description: Create a small domain utility that converts grams and kilograms to grams using Decimal-safe arithmetic and rejects invalid quantities or unsupported units. Add focused tests for conversions, boundary values, decimal inputs, and error cases.

## 6. Implement ingredient cost calculation
Goal: Calculate the cost of any requested amount of an ingredient.
Description: Build a domain service that derives a proportional cost from an ingredient's package weight, package unit, package price, and requested quantity. Keep the logic independent of HTTP views and add tests covering grams, kilograms, fractional prices, invalid values, and the project's chosen rounding policy.

## 7. Implement recipe scaling and totals
Goal: Produce ingredient quantities, ingredient costs, total weight, total cost, and cost per unit for a requested unit count.
Description: Add a domain service that scales every RecipeIngredient for a positive whole-number unit count and returns a structured calculation result. Test single- and multi-ingredient recipes, multiple unit counts, mixed input units, decimal costs, aggregation, rounding, and invalid requests.

## 8. Build the shared application layout
Goal: Establish a consistent Bootstrap-based interface for all custom pages.
Description: Add a base Django template with Bootstrap 5, navigation links for ingredients, recipes, and the calculator, plus reusable areas for messages and form errors. Include minimal static CSS where needed and add a template-rendering smoke test.

## 9. Build the ingredient list and detail pages
Goal: Let the user browse saved ingredient pricing information.
Description: Create server-rendered list and detail views, URLs, and templates showing each ingredient's name, brand, purchase location, package size, and package price. Include empty-state behavior, navigation to relevant actions, efficient querying, and request tests for successful and missing records.

## 10. Build ingredient create and edit pages
Goal: Let the user add and update ingredients through validated forms.
Description: Create a Django ModelForm and server-rendered views for creating and editing Ingredient records. Display field errors clearly, preserve submitted data after validation failures, redirect after success, and test valid and invalid submissions.

## 11. Build ingredient deletion
Goal: Let the user safely delete an ingredient that is no longer needed.
Description: Add a confirmation page and a POST-only delete action, with explicit behavior when the ingredient is referenced by a recipe. Protect relational integrity, show a useful success or error message, and test confirmation, successful deletion, blocked deletion, and non-POST requests.

## 12. Build the recipe list and detail pages
Goal: Let the user browse recipes and inspect their ingredient quantities.
Description: Create server-rendered list and detail views, URLs, and templates showing recipe name, weight per unit, and all linked ingredients with their quantities and units. Include empty states, avoid unnecessary database queries, and test successful and missing records.

## 13. Build recipe creation
Goal: Let the user create a recipe and its ingredient rows in one submission.
Description: Use a Recipe ModelForm and inline formset to capture recipe fields and one or more RecipeIngredient rows on a single page. Add minimal vanilla JavaScript for inserting and removing formset rows, while preserving server-side validation, and test valid creation, duplicate ingredients, empty rows, and invalid quantities.

## 14. Build recipe editing
Goal: Let the user update recipe details and its ingredient rows together.
Description: Create an edit page using the recipe form and inline formset, supporting additions, changes, and removals in one atomic submission. Ensure an invalid row prevents partial saves and test each operation as well as rollback behavior.

## 15. Build recipe deletion
Goal: Let the user delete a recipe after explicit confirmation.
Description: Add a confirmation page and POST-only action that removes the recipe and its RecipeIngredient rows without deleting shared Ingredient records. Show a success message after deletion and test confirmation, cascading relationship cleanup, ingredient preservation, and non-POST requests.

## 16. Build the recipe calculator page
Goal: Let the user select a recipe and number of units and see a complete cost calculation.
Description: Create a validated form and server-rendered view that invokes the recipe-scaling service and displays cost per unit, weight per unit, adjusted ingredient weights and costs, total cost, and total weight. Handle empty recipe data and invalid unit counts clearly, and add request tests that verify the displayed results.

## 17. Define and apply display formatting
Goal: Present weights and currency consistently throughout the application.
Description: Establish the single currency symbol or label and explicit decimal-place rules for stored values, intermediate calculations, totals, and display-only rounding. Implement reusable template formatting, apply it to ingredient, recipe, and calculator pages, and test representative values without changing calculation precision.

## 18. Add end-to-end workflow coverage
Goal: Verify the complete ingredient-to-calculation workflow through the web interface.
Description: Add integration tests that create ingredients, assemble and edit a recipe, request multiple units, and verify the resulting weights and costs. Include regression scenarios for unit conversion, price changes, protected ingredient deletion, invalid formsets, and decimal rounding.

## 19. Prepare the production container configuration
Goal: Run the application in a production-oriented container using Gunicorn and PostgreSQL.
Description: Add a production command and configuration for Gunicorn, static-file collection and serving, secure environment-driven Django settings, startup migration handling, and container health checks. Document required variables and verify that the production Compose configuration starts successfully and serves a health endpoint.

## 20. Write the operator guide
Goal: Document how a single user installs, runs, backs up, restores, and updates the application.
Description: Create concise instructions for local and production startup, migrations, test execution, database backup and restore, dependency updates, and common troubleshooting. Ensure every documented command matches the final Docker Compose and Django configuration and can be followed from a clean checkout.
