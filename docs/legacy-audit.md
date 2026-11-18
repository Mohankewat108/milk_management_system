# Legacy audit — PHP Milk Management System

## Scope inspected

The original `main` branch was inspected before the Django replacement was created. The repository contains a small PHP/PDO application organised around:

- `dashboard/index.php` and `dashboard/insert_milk.php` — dashboard totals and new milk records.
- `customer/` — customer creation, customer directory, daily milk reports, edit/update/delete operations.
- `setting/milk_quality_parameters.php` and `setting/insert_milk.php` — SNF, FAT and Lactose rate configuration.
- `milk/` — a secondary listing/demo area and a duplicate database connection script.
- `README.md` — project overview and legacy database expectations.

The README says the legacy data model has four main tables: `customer`, `daily_milk`, `staff` and `milk_setting`. It also says `milk_total_price` is a MySQL generated column. **The referenced `milk.sql` dump is not present in this repository**, so the exact DDL, indexes, constraints, data types, generated-column expression and existing data volume could not be verified.

## Verified risks in the PHP source

1. **Hard-coded database credentials.** `milk_dbconnection.php` contains local host/database/user/password values in tracked source. The replacement uses environment-based configuration and does not copy those credentials.
2. **No authentication on the inspected legacy pages.** The PHP pages directly perform customer, collection and pricing operations. The README lists login as a future improvement rather than an existing feature.
3. **GET-based destructive action.** `customer/delete_customer_daily_report.php` reads `milk_id` from the query string and deletes the matching `daily_milk` record. The Django replacement uses POST for approval/status operations and does not implement hard-delete for collection history.
4. **Client-submitted pricing.** The dashboard calculates the milk rate in JavaScript and sends `milk_rate` with the POST. The legacy insert handler saves that posted rate. A client can alter POST data, so the old server does not independently establish the authoritative rate.
5. **Configuration updates lack role checks.** The PHP settings page accepts a posted update without verifying an authenticated owner or authorised role.
6. **Historical pricing is not versioned in the inspected UI.** Updating the singleton `milk_setting` values does not provide an auditable effective-dated pricing history.
7. **Output escaping is inconsistent.** Some legacy pages use `htmlspecialchars`, while other pages print user-controlled values directly.
8. **Schema and generated formula are unverified.** Although the README describes a generated total-price column, the missing SQL dump prevents reliable reconstruction of its exact expression or type semantics.

## Replacement assumptions and compatibility decisions

- The original README describes the pricing calculation as the weighted sum of measured SNF, FAT and Lactose values. DairyNexus implements the explicitly provided formula:
  `(SNF × SNF rate) + (FAT × FAT rate) + (Lactose × Lactose rate)`.
- The pricing service and financial amount fields use Python `Decimal`, not binary floating-point arithmetic.
- Each saved collection stores the selected pricing configuration and a JSON pricing/quality snapshot. Later changes to current configuration therefore do not rewrite historical rates.
- Quality limits are organisation/branch-configurable and effective-dated. No undocumented acceptable SNF/FAT/Lactose ranges are invented. When no approved profile exists, the record captures that no profile was configured.
- Customer and Farmer are separate domain entities. A farmer supplies milk; a customer is a milk buyer/customer.
- Shared-database multi-tenancy is used initially. Every business record has an organisation relationship and web access is checked against the authenticated user's membership, with an additional branch assignment check for scoped staff.
- The migration branch is additive. The legacy PHP files and original `main` branch are left intact.

## Data migration blocker

A safe import needs the actual legacy schema and a database export. Before importing production data:

1. Export the live MySQL database from the actual environment.
2. Supply the `milk.sql` schema/data dump, including generated-column definition and representative data.
3. Map existing customer/staff identifiers to Django UUID records.
4. Validate all dates, decimal precision, deleted/soft-deleted flags and orphan relationships.
5. Reconcile record counts and total litres/amounts before cutover.

No live legacy records have been migrated or modified by this branch.
