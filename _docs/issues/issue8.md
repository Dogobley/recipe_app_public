# Issue 8: Build the shared application layout

Status: closed

## Goal

Establish a consistent Bootstrap-based interface for all custom pages.

## Acceptance criteria

- [x] Every custom page can extend one base template that supplies the HTML document structure, page title hook, header, main-content area, and footer.
- [x] The shared navigation visibly links to ingredient browsing, recipe browsing, and the recipe calculator.
- [x] The current navigation destination is identifiable visually and through accessible markup.
- [x] Django messages render in a shared, visible area with styling appropriate to their message level.
- [x] Forms can render field-specific errors and non-field errors in a consistent, accessible style.
- [x] The layout remains usable at narrow mobile and desktop viewport widths using Bootstrap 5.
- [x] Bootstrap assets load without introducing a frontend build step; any project CSS is served through Django static files.
- [x] A template smoke test renders the base layout and verifies its navigation, message area, and content extension point.

## Out of scope

- Ingredient page content belongs to [Issues 9](issue9.md), [10](issue10.md), and [11](issue11.md).
- Recipe page content belongs to [Issues 12](issue12.md), [13](issue13.md), [14](issue14.md), and [15](issue15.md).
- Calculator content belongs to [Issue 16](issue16.md).
- Domain-specific currency and weight formatting belongs to [Issue 17](issue17.md).

## Constraints

- Complete [Issue 1](issue1.md) first and use its Django template and static-file configuration.
- Use Django templates, Bootstrap 5, minimal local CSS, and only minimal vanilla JavaScript.
- Keep the application server-rendered; do not add an SPA framework or frontend build service.
- Ensure navigation and feedback do not rely on color alone and use semantic HTML.

## Engineer comment

Implemented the shared responsive Bootstrap 5 shell with document/title/content
blocks, header navigation, main landmark, footer, Bootstrap CDN assets, and a
Django-served local stylesheet. Navigation is visibly underlined when active and
uses `aria-current="page"`; messages have shared level-appropriate alerts and
the reusable form-error partial exposes non-field and field errors accessibly.
Added template smoke coverage for the base layout, navigation state, messages,
content extension, and form-error markup. `python -m pytest tests/test_smoke.py`
passed (4 tests) and `python -m pytest` passed (154 tests). Ready for QA; issue
remains open.

### Follow-up

Moved the local stylesheet into `calculator/static/calculator/site.css`, Django's
app-local static-files location, and added a regression test using the Django
staticfiles finder. `python manage.py findstatic calculator/site.css` located
the stylesheet and `python manage.py collectstatic --noinput` copied 128 static
files. The focused smoke suite passed (5 tests) and the full suite passed (155
tests). Ready for QA; issue remains open.
