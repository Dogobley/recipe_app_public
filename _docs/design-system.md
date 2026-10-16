# Design System

## Principles

The interface is a practical, server-rendered tool for one user. Favor clarity,
consistency, accessibility, and efficient data entry over decoration. Every page
must remain usable at narrow mobile and desktop widths.

Bootstrap 5 is the shared UI foundation. Use its layout, spacing, typography,
form, table, alert, and utility patterns before adding local CSS. Keep local CSS
small and serve it through Django static files. Do not add a frontend framework,
package manager, or build step.

## Shared page structure

All custom pages extend one base template that provides:

- The HTML document structure and a page-title block.
- A header and shared navigation linking to ingredients, recipes, and the recipe
  calculator.
- One main-content landmark and a footer.
- A consistent area for Django messages.
- Blocks for page-specific content and the minimal scripts a page needs.

The current navigation destination must be conveyed with accessible markup, such
as `aria-current="page"`, as well as a visible style. Navigation and feedback
must never rely on color alone.

## Content and layout

- Use semantic headings in order, with one clear page heading.
- Keep primary actions easy to find and label controls with specific verbs such
  as "Add ingredient", "Save recipe", or "Calculate".
- Use Bootstrap's responsive grid and spacing utilities. Do not depend on fixed
  page widths or horizontal scrolling for primary actions.
- Wrap wide data tables in a responsive container and provide meaningful column
  headings.
- Keep ingredient, recipe, and calculator pages visually consistent by reusing
  templates or components for repeated navigation, forms, messages, and actions.

## Forms and feedback

- Every control has a visible label associated with it; placeholder text is not
  a substitute for a label.
- Mark required fields in text or accessible markup, not by color alone.
- Render field errors next to their controls and non-field errors in a clear
  summary or shared form-error area. Connect errors to controls where practical
  and preserve the user's submitted values.
- Use appropriate input types, help text, and unit labels for weights, prices,
  and unit counts.
- Destructive actions require a confirmation page and a POST submission with
  CSRF protection. Distinguish destructive actions through both wording and
  styling.
- Render Django messages in the shared message area using an appropriate alert
  role and message-level styling.

## Dynamic recipe rows

Vanilla JavaScript may add or remove recipe ingredient formset rows as a
progressive enhancement. Server-side forms remain authoritative. Row controls
must have accessible names, Django management-form data must stay correct, and
the form must still show useful validation errors after submission.

## Display conventions

- Display money with the `COP $` prefix and exactly two decimal places.
- Round displayed money with `ROUND_HALF_UP` without changing stored or domain
  values.
- Display weights with their explicit `g` or `kg` unit, up to three decimal
  places, and no insignificant trailing zeros.
- Never display negative zero or silently turn invalid or missing numbers into
  zero.
- Apply these rules through shared presentation helpers rather than duplicating
  formatting in individual pages.

## Accessibility and verification

- Prefer semantic HTML and native controls; add ARIA only when native semantics
  are insufficient.
- Ensure keyboard users can reach and operate navigation, forms, dynamic row
  controls, confirmations, and primary actions.
- Maintain readable focus indicators and sufficient text/background contrast.
- Test shared layout structure, navigation state, messages, form errors, and
  reusable number formatting. Follow `_docs/testing-guidelines.md` for test
  scope and assertion style.
