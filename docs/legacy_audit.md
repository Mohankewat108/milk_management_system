# Legacy Audit and DairyNexus Implementation Plan

## Evidence inspected

- Repository inventory: 20 source, markup, stylesheet, and image files.
- PHP entry pages and workflows inspected: dashboard, customer creation/list/detail, milk collection, milk report/edit/delete, milk quality settings, staff/milk list, and database connection.
- README feature and installation claims inspected.
- The missing `milk.sql` and no migrations/schema dump are present. MySQL table definitions could not be inspected.

## Existing PHP workflows

1. Dashboard reads today's milk totals and average rate, lists the latest five collections, loads customer/staff lists, and embeds SNF/FAT/Lacto settings in JavaScript.
2. A customer is inserted from a form into the `customer` table.
3. A collection is inserted into `daily_milk` with customer, staff, litres, date, quality values, and submitted rate.
4. Collections can be listed, filtered by customer/date, edited, or deleted with GET or POST endpoints.
5. Milk quality settings update `milk_setting.setting_id = 1` only.

## Legacy database assumptions

The PHP assumes MySQL tables named `customer`, `daily_milk`, `staff`, and `milk_setting`.

The README says `milk_total_price` is a generated MySQL column. The SQL definition was not included, so the formula and precision cannot be verified.

The database credentials are hardcoded in `milk_dbconnection.php` and the duplicate connection file under `milk/` as `root` / `root`, and target host `localhost`, database `milk`.

## Observed pricing behavior

The dashboard calculates the submitted milk rate in browser JavaScript as:

`rate = (snf * snf_rate) + (fat * fat_rate) + (lacto * lacto_rate)`

Total amount is expected in MySQL and README to be derived from litres and rate. The DairyNexus implementation now calculates using historical branch pricing and stores both the rate and total amount.

## Security findings

- No authentication or role model exists.
- No tenant or organisation concept exists.
- Destructive milk deletion is implemented as a GET link.
- Customer and collection identifiers are accepted directly from query or POST values.
- No CSRF protection, session expiry, password model, or server-side authorization is present.
- Several output locations use little or no escaping.
- Database credentials are committed to source.
- Historical edits overwrite collection values without an audit trail or correction reason.
- Browser-side datalists are not server-side validity checks.

## Migration risks

The missing SQL dump prevents verified table/column mapping and data migration.
Customer and staff foreign-key semantics, soft-delete fields, generated-column formulas, and current MySQL data types are unknown.
Legacy records should be migrated through a reviewed script with organisation assignment and Decimal conversion rather than a direct import.

## Implementation phases

1. Foundation: Django settings, custom UUID user, SQLite/PostgreSQL support, base templates, static assets, and health-ready configuration. **Current focus**
2. Authentication and tenancy: registration, login, organisations, memberships, branches, and tenant-isolated querysets.
3. Platform administration: organisation search and status management.
4. Dairy operations: customer and milk collection workflows with server-side pricing and audit logs.
5. Finance, inventory, farmer/staff management, customer portal, exports, and demo data.
6. Security QA, cross-tenant tests, deployment, Docker, CI, and operational documentation.

This audit is evidence-based. The untracked or missing SQL schema is not treated as inspected.

## Implementation progress recorded after the audit

- **IMPLEMENTED:** Django foundation, custom UUID user, organisation and membership models, branch model, tenant-scoped customer/farmer/staff/milk collection/payment/expense/inventory/support models, registration/login/logout, platform organisation status controls, branch/pricing/farmer/staff/customer/payment/expense workflows, customer portal, CSV collection export, demo data command, Docker/Compose, and CI.
- **VERIFIED:** Django system check, 6 Django tests, demo seed command, live `/health/` endpoint, and live login-page response.
- **BLOCKED:** Verified MySQL `milk.sql` import and legacy data migration cannot proceed because the SQL dump is absent.
- **NOT YET IMPLEMENTED:** A complete PDF/Excel report suite, Celery/Redis runtime integration, full subscription/billing management, complete notification delivery, production backup automation, and two-factor authentication.
