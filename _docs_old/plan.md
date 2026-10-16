# Project Scope: Cost & Ingredients Calculator for Confectionery

## Purpose
Single-user web tool to calculate cost per unit and ingredient quantities for a requested number of units (e.g., cookies, candies).

## Core Features

### Ingredients
- Save ingredients with name, brand, place of purchase, package weight (kg/g), and package price.
- Cost is proportional to amount used, based on package weight and price.
- Edit/delete ingredients.

### Recipes
- Save recipes with name and list of ingredients (each with weight/quantity in kg or g).
- Define weight per unit (e.g., 50 g per cookie).
- Edit/delete recipes.

### Calculation
- Input desired number of units.
- Output:
  - Cost per unit
  - Weight per unit
  - Ingredient list with adjusted weights and adjusted costs
  - Total cost and total weight for requested units
- Only ingredient costs (no overhead, labor, packaging).

## Data Persistence
- PostgreSQL database.

## Tech Stack
- Backend: Python / Django
- Frontend: Django templates (server-rendered, no separate SPA)
- Deployment: Docker Compose
- Single user, no authentication/login
- Single currency

## Not Included (for now)
- Inventory/stock tracking
- Multiple currencies
- Overhead costs
- Export/print functionality
- Preparation steps or categories