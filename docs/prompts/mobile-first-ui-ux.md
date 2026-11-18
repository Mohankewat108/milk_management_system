# DairyNexus — Production-grade mobile-first UI/UX implementation prompt

You are the senior product designer, accessibility specialist and frontend engineer responsible for the complete DairyNexus Django SaaS application. Your task is to audit and improve the entire product, not only one page.

## Product objective
Create a calm, simple, trustworthy dairy-management experience. Prioritise clarity, speed, predictable navigation and error prevention over decorative effects. The interface must work consistently for platform owners, dairy owners, branch managers, accountants, staff, farmers and customers, while respecting server-side permissions and tenant boundaries.

## Non-negotiable engineering rules
1. Inspect the existing Django templates, URL names, view context, static assets, CSS tokens, JavaScript and tests before editing. Never invent model fields, context variables, URL names or permissions.
2. Preserve existing business logic, CSRF protection, server-side validation, role checks, tenant isolation, audit trails, soft-delete semantics and workflow states. UI changes must not weaken authorization.
3. Do not introduce a second design system. Extend the existing design tokens and reusable components. Keep CSS maintainable and avoid repeated conflicting overrides.
4. Do not use fixed pixel widths for page content. Use fluid grids, minmax(0, 1fr), max-width constraints and content-aware wrapping.
5. Do not solve overflow by hiding important content. Tables may scroll inside their own labelled containers; forms, navigation, cards and page layouts must reflow.
6. Keep all date, currency and number formatting locale-aware. Do not change database storage formats or submit display-only localized values unless the backend explicitly supports them.
7. Do not replace semantic buttons, links, labels, forms or tables with clickable generic divs.
8. Respect reduced-motion preferences, visible keyboard focus, screen-reader labels, sufficient contrast and touch target sizes.
9. Avoid adding dependencies unless they are justified, maintained, licensed appropriately and tested.
10. Do not claim a page is tested or complete until the automated checks and viewport checks have actually run.

## Required responsive breakpoints
Validate at minimum:
- 320 × 640 (small phone)
- 360 × 800
- 375 × 812
- 390 × 844
- 430 × 932
- 600 × 900 (large phone / small tablet)
- 768 × 1024 (tablet)
- 1024 × 768 (small laptop)
- 1280 × 800 and 1440 × 900 (desktop)

The page must have no unintended horizontal scrolling at any viewport. The only allowed horizontal scrolling is inside deliberately labelled wide-data/table regions.

## Global application shell
- Make the header compact and usable on small screens. Keep brand, primary account actions, language and theme controls accessible without wrapping into an unusable multi-row bar.
- Convert the desktop sidebar into an accessible off-canvas drawer on tablet/mobile. Include a backdrop, close button behaviour, Escape handling, focus management, scroll locking and close-on-navigation.
- Ensure the drawer never covers the header, traps users behind an invisible overlay or remains open after a route transition.
- Use safe-area insets on notched devices.
- Make the footer wrap cleanly.
- Ensure the main content width is based on the available viewport, not the desktop sidebar width.

## Design system
- Use a restrained palette, consistent typography, spacing, border radii, shadows and states.
- Use clear page titles, one primary action per page, secondary actions grouped consistently, and destructive actions visually distinct and confirmed.
- Keep cards visually light and information-dense without excessive borders, gradients, oversized headings or large empty areas.
- Standardise loading, empty, error, success, warning, disabled and permission-denied states.
- Make focus, hover, active and selected states consistent in light and dark themes.
- Keep text readable at 200% zoom and avoid truncation of names, addresses, email addresses and translations.

## Page-by-page audit scope
Review and improve every user-facing page and shared component, including:
- Authentication, registration, password reset and account security
- Workspace selection, dashboard and platform administration
- Farmer/customer directories, create/edit forms, profile pages and trash/restore flows
- Milk collection creation, editing, list, approval and reversal flows
- Payments, expenses, approvals and finance forms
- Inventory items, stock movements and suppliers
- Branches, staff invitations, staff access and role management
- Milk pricing, quality settings and configuration
- Customer portal and public landing pages
- All dialogs, dropdowns, alerts, pagination, filters, tables and form validation

## Mobile interaction standards
- Minimum touch target: 44 × 44 CSS pixels where practical.
- Use one-column forms on narrow screens; group related fields with clear section headings.
- Inputs must be full-width, readable and never cause iOS zoom due to tiny font sizes.
- Keep labels visible above fields. Never rely only on placeholders.
- Place primary form actions at the end of the form and make them easy to reach.
- Keep destructive actions separated from normal actions.
- Filters should collapse into a compact, accessible section when the page has many controls.
- Cards should stack naturally; KPI cards should use two columns only when the content remains legible.
- Wide tables should scroll within their own container, preserve column headings and expose a clear scroll affordance.
- Do not shrink desktop content until it is unreadable. Reflow it.

## Accessibility and internationalisation
- Use semantic landmarks and heading hierarchy.
- Ensure all controls have labels and accessible names.
- Support keyboard-only navigation and Escape to dismiss overlays.
- Ensure focus is not lost when drawers or dialogs open/close.
- Test both light and dark themes.
- Test English, Nepali and Hindi strings, including longer translations and Devanagari numerals.
- Avoid hard-coded English UI strings where the project uses Django translation.
- Ensure BS date picker and date filters remain usable on small screens and do not open off-screen.

## Required validation and deliverables
1. Provide an inventory of every template/page and shared component reviewed.
2. Implement shared responsive primitives first, then page-specific fixes.
3. Add or update tests for navigation, template rendering, form behaviour and accessibility-sensitive interactions where feasible.
4. Run Django checks, the full test suite, formatting/lint checks and static asset collection/build checks available in this repository.
5. Test screenshots at the required viewport widths and inspect both themes.
6. Report each page as: fixed, verified, needs follow-up, or blocked. Do not mark untested pages verified.
7. Summarise files changed, commits, tests actually run, CI status and known limitations.

## Definition of done
A first-time user can complete the core workflows on a 320px-wide phone without page-level horizontal scrolling, clipped controls, unreadable text, hidden actions or accidental destructive operations. The same components remain consistent and efficient on desktop. Existing permissions, data integrity and business workflows remain unchanged.
