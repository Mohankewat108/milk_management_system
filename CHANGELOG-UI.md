# UI redesign changelog

Branch: `ui/industry-redesign`

## Design system
- `static/css/app.css` — Replaced conflicting green-centric styling with a reusable dairy operations design system: cool blue/white foundations, teal accent, semantic status palettes, type/spacing/radius/shadow tokens, reusable responsive components, keyboard focus states, reduced-motion handling and print styles.
- `templates/base.html` — Reworked the shared shell with skip navigation, accessible primary navigation, consistent brand treatment, status context, live message region, responsive page frame and footer. Existing routes, authentication conditions, blocks and message variables remain intact.
- `customer/customer.css` — Replaced old purple global body/table styling with token-aligned legacy component styles scoped to existing customer-specific classes.
- `dashboard/dashboard.css` — Removed global body/main/heading/table rules that could interfere with Django layouts. Retained legacy dashboard class hooks with consistent components and responsive behaviour.
- `milk/style.css` — Removed global body and table overrides; introduced opt-in legacy `.milk-page` scoping so unrelated app pages are not affected.

## Template polish
- `templates/accounts/login.html` — Improved login guidance and added an accessible alert role to form-level errors; form fields and Django bindings preserved.

## Audit and scope decision
34 HTML templates and 4 CSS stylesheets were inventoried. All templates already extend a shared base layout; the three legacy CSS files contained global styles that conflicted with the modern Django stylesheet.
The remaining 33 HTML templates were not rewritten individually in this first visual-system pass. They inherit the shared shell and updated component styles. Their template tags, URL names, form fields and context variable names are preserved. Further page-specific markup changes require rendered-page regression checks.