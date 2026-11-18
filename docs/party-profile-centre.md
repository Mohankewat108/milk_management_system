# Customer and Farmer Profile Centre

This feature adds organization-scoped detail pages and date-filtered performance views for customers and farmers.

## Metrics policy
- Confirmed milk quantity/value includes approved collections only.
- Submitted, draft, rejected and reversed collections remain visible in history/status counts but are not included in confirmed totals.
- Completed incoming customer payments and completed outgoing farmer payments are displayed separately.
- No outstanding account balance is claimed: the current finance schema records payments and collections but does not yet provide a reconciled party ledger.
- Skipped deliveries, returns, advances, bonuses and penalties are not displayed as numeric values unless corresponding records exist in the current schema.

## Authorization
Profile lookups filter by the active organization and accessible branch IDs before resolving the requested UUID. Directory search and detail views follow the same scope. Finance figures are limited to owner, admin and accountant roles.
