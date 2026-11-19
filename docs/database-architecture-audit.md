# DairyNexus database architecture and integrity audit

**Audit scope:** Django model declarations, migration history, domain services, query and transaction patterns, and the repository's configured PostgreSQL CI workflow.
**State captured:** `b34d57d` on `feature/party-trash-staff-management`.
**Status:** Findings below were recorded before implementation changes for Phase 2.

## Executive summary

DairyNexus is a modular Django monolith with UUID primary keys and a shared-schema tenant model. PostgreSQL is required for production; development and local tests can use SQLite. The core financial and inventory workflows use `Decimal`, atomic services, and row locks. Migration history is additive and includes no data-reset migrations.

The principal integrity gap is that ordinary foreign keys do not enforce that related rows belong to the same organization. Service methods check several such relationships, but direct ORM, admin, bulk, and import writes can bypass those checks. This affects branches, parties, pricing, supplier/item links, ledger periods/accounts, and organization-owned movement records. Current check constraints cover some positive amounts and ranges, but not all fields that control balances or lifecycle consistency.

Other high-value concerns:

1. Journal balance and several same-tenant rules are enforced in service/model `clean()` paths rather than by database constraints. Django does not call `full_clean()` on `save()`.
2. Payment and collection creation have no caller-provided idempotency key. Random references prevent reference collisions, not duplicate business submissions.
3. Inventory services lock the item row, but stock movement rows can be created or changed outside those services; the model has no balance/quantity constraints.
4. The accounting-period overlap check does not serialize on a stable parent row. Pricing writes do lock the organization for rate schedules, but quality-profile creation does not and its version/overlap checks can race.
5. Trash views iterate every deleted row without pagination. Most operational lists and exports are paginated or streamed; large report and dashboard aggregations warrant query-plan and volume testing.

No schema edits or migrations had been made when this report was created.

## Application and model inventory

`UUIDModel` supplies UUID primary keys. `TimeStampedModel` supplies indexed `created_at` and mutable `updated_at`. Except for Django's custom user manager, models use Django's default manager and queryset; the project does not define tenant-scoping managers. Tenant scoping is therefore application/service responsibility, not an ORM-wide policy.

| App | Models and relationships | Integrity declarations and notable behavior |
|---|---|---|
| `accounts` | `User` extends `AbstractUser`; unique email, profile photo and contact/preferences. Django auth adds group and permission many-to-many relations. | Django's `UserManager`; UUID primary key. No custom save/delete or signal found. |
| `organizations` | `Organization.owner -> User`; `Branch.organization -> Organization`, optional `manager -> User`; `Membership.user -> User`, `organization -> Organization`; `BranchAssignment.membership -> Membership`, `branch -> Branch`; `StaffInvitation.organization`, `invited_by -> User`, and M2M `branches -> Branch`. | Unique organization slug, branch `(organization, code)`, membership `(user, organization)`, and assignment `(membership, branch)`. Indexes include organization status/created, branch organization/active, membership user/status and organization/role/status, invitation organization/email/created and token/email/expiry indexes. Branch soft deletion is fields only; no custom manager. |
| `parties` | `Customer` and `Farmer` each belong to an organization, optionally a branch, optional one-to-one user profile, and optional deleted-by user. | Unique `(organization, code)` per party type; organization/name and organization/active indexes. `deleted_at`/`deleted_by` fields; no model-level soft-delete manager. |
| `pricing` | `PricingConfiguration` and `QualityConfiguration` belong to an organization, optionally a branch, and reference creator; price config also references approver. | Unique `(organization, version)` per table; effective-date and non-negative/range checks. Pricing indexes organization/date range and organization/branch/approval. Pricing has soft-delete fields; versions and non-overlap are primarily service/view enforced. |
| `collections` | `MilkCollection` references organization, branch, optional farmer or customer, recorder/tester users, and pricing configuration. | Unique `(organization, reference)`; positive quantity, exactly-one-party, non-negative SNF/FAT/lactose/lactometer checks. Indexes organization/collected-at, organization/branch/status, customer/collected-at. Historical rate and quality snapshot are JSON. |
| `finance` | `Payment` and `Expense` reference organization, branch, recorder; payment optionally references farmer/customer, expense optionally references approver/deleter. `Account` belongs to organization and may have a self-parent. `AccountingPeriod` belongs to organization. `JournalEntry` references organization, branch, period, creator/poster, and optional one-to-one reversal. `JournalLine` references entry/account. `LedgerConfiguration` is one-to-one with organization and references ten control accounts. | Payments and expenses have organization/reference uniqueness and positive amount checks; payment exactly-one-party check. Account code is unique per organization; periods unique by organization/code and date order checked. Journals unique by organization/reference and conditional organization/idempotency key; lines unique by entry/line number, nonnegative and one-sided debit/credit. Posted entry/line `save()`/`delete()` reject mutation; direct queryset/bulk operations bypass those overrides. Ledger config `clean()` checks account tenant, but direct `save()` skips it. Indexes support common tenant/date/status/source reads. No currency-aware ledger conversion: journals are expressed in organization base currency. |
| `inventory` | `Supplier` belongs to organization. `InventoryItem` belongs to organization and branch, optionally a supplier. `StockMovement` belongs to organization and references item and creator. | Supplier and item codes unique per organization. Item indexes organization/branch/active and organization/current-stock. Movement indexes organization/created and item/created. Stock values and movement deltas are Decimal; no DB checks currently prevent negative starting stock, reorder levels, price, zero/incorrectly signed movement, or item/organization mismatch. |
| `platform_admin` | `SubscriptionPlan`; `Subscription` references organization and plan; `FarmOwnerInvitation` references organization, user, inviter. | Plan name/code unique. Subscription indexes organization/status and status/end date. Invitation token unique; indexes organization/email/created and expiry/acceptance/revocation. No model-specific save/delete or signals. |
| `audit` | `AuditEvent` optionally references organization and actor; target is represented as type/id strings. | Action indexed; composite organization/created and actor/created indexes. No FK to target by design; no custom manager or model immutability enforcement. |
| `data_exports` | `ExportJob`, `SavedExportTemplate`, `ScheduledExport`, `ImportBatch` reference organization and requesting/creating/uploading user. Export jobs/templates/schedules/import batches store filters, recipients, or errors as JSON; exports use private file storage. | Export job indexes organization/created, organization/status, status/created; template unique organization/name; schedule due index; import organization/created. Choices and JSON shape validation are largely application-level. |
| `core` | Abstract `UUIDModel` and `TimeStampedModel`; no concrete domain rows. | Shared identifiers/timestamps described above. |

### Relationship and tenant-integrity boundary

Foreign keys enforce existence and delete behavior (`CASCADE`, `PROTECT`, or `SET_NULL`), not tenant equality. Important candidate mismatches include:

- branch assignments and invitation branch M2M can connect a membership/invitation to another organization's branch;
- party, branch, and pricing references on a collection can cross organization boundaries;
- branch and party references on payments/expenses, and branch/supplier on inventory items, can cross organizations;
- stock movement organization can differ from its item's organization;
- journal branch, accounting period, and account can belong to another organization; the ledger configuration's accounts are tenant-checked only by `clean()`;
- pricing and quality configurations can point to branches from another organization.

Existing service checks prevent some of these cases through normal workflows, but model `.save()` does not call `.full_clean()`, and bulk/queryset writes bypass instance hooks. These are database-integrity gaps for direct writes and future features.

## Monetary, quantity, and lifecycle review

- Monetary, rate, stock, and milk-measurement values use `DecimalField`; no `FloatField` or float arithmetic was found in the Django domain model/application scan.
- Collections store litres and SNF/FAT/lactose at three decimal places; milk temperature has two; rates four; money two. Payment/expense/journal amounts have two decimals; stock quantities have three.
- Collection creation computes the milk rate and total with `Decimal`, `ROUND_HALF_UP`, and saves a pricing snapshot. Editing preserves the saved rate snapshot rather than applying a new price.
- Payments use the organization currency at creation; journal entries describe amounts in base currency. There is no FX conversion/accounting path.
- Payment direction/party matching and collection exactly-one party are enforced by service plus one database check for party count. Payment direction itself is not a DB check.
- Expense/payment totals are not independently recalculated by the database. Journal balancing is validated in `post_journal_entry`; no database aggregate constraint guarantees that direct posted entries balance.
- Inventory current stock and the stock-movement ledger are updated atomically under `select_for_update` in the service. They are not protected against direct writes that bypass the service.

## Transactions, concurrency, and duplicate handling

- `transaction.atomic` is used in organization registration, collection creation/approval, finance writes and posting, inventory movement/adjustment, pricing writes, invitation acceptance, imports/exports, and trash actions.
- `select_for_update` is used for collection and payment/expense transitions, inventory item balances, journal reversal, accounting periods, invitations, and trash records. SQLite does not provide equivalent row-lock coverage; PostgreSQL CI is the meaningful concurrency target.
- Payment completion and collection approval lock their rows and validate the prior state. Ledger idempotency is backed by a conditional unique constraint on `(organization, idempotency_key)`.
- Stock changes serialize on an item row and prohibit negative result balances in the service. Direct stock/movement operations are not similarly serialized.
- Collection, payment, and expense references are random UUID-derived strings. They avoid a shared counter race, but are not request idempotency. Replayed submissions can create separate business rows with different references.
- Accounting-period overlap is checked by querying overlapping rows under `select_for_update`; locking only matching rows does not serialize the first concurrent creation when no overlap exists. Quality schedule version and overlap checks similarly have no stable tenant lock. Pricing schedule writes already lock the organization before checking.
- Export jobs use a row lock during worker processing; retries after terminal status return the current job. Worker task claims and schedule due-row claims are not fully locked as a batch, so duplicate workers may race on claiming due rows; the queued-state check helps for individual export processing.
- No custom model signals or `signals.py` were found. No custom domain model managers/querysets or `save()`/`delete()` hooks were found outside the journal models and ledger configuration `clean()`.

## Query and migration review

- Most operational directories use pagination. Collection, finance, inventory, and export rendering paths generally use `select_related`; export rows use `.iterator(chunk_size=1000)`. Party detail/report views use database aggregation.
- Trash listing iterates all deleted records for each registered model and sorts them in Python; this is unbounded and can become memory/latency intensive.
- The main indexes are tenant-first for common operational lookups. A further index should be justified with production-shaped `EXPLAIN (ANALYZE, BUFFERS)` rather than added speculatively.
- Migration history is additive across organizations, parties, pricing, collections, finance, inventory, exports, audit, accounts, and platform administration. Existing history includes indexes, constraints, soft-delete fields, ledger tables, invitations, and storage changes. No destructive reset migration was found.
- Production settings require PostgreSQL. CI uses PostgreSQL 16 and Redis; local test settings default to in-memory SQLite unless `DATABASE_URL` is set.

## Findings and proposed implementation order

1. **High — cross-tenant foreign-key integrity is not universally database-enforced.** Add database-backed same-organization invariants for the highest-risk operational and accounting relations. Validate migration preconditions and existing rows before adding constraints; no production data cleanup should be automatic.
2. **High — journal and inventory invariants can be bypassed with direct writes.** Add appropriate non-negative/positive checks and strengthen service/model validation; assess database triggers or normalized constraints for aggregate/tenant facts that cannot be represented by ordinary `CHECK`.
3. **Medium — duplicate collection/payment submissions have no idempotency token.** Introduce explicit optional idempotency keys at service/API boundaries, scoped by organization and protected by a unique constraint, without changing financial calculations.
4. **Medium — accounting period and quality schedule creation can race.** Lock a stable organization row before overlap/version checks and keep the checks and insert in the same transaction. Add PostgreSQL concurrency tests.
5. **Medium — trash listing is unpaginated.** Paginate at the database layer or otherwise bound each tenant's trash scan.
6. **Verification caveat entering Phase 2:** the previous Phase 1 commit's pushed CI run failed in its new export-view tests with PostgreSQL connection-closed errors; local SQLite tests passed. Reproduce/fix that PostgreSQL-only failure before reporting Phase 2 verification as complete.

## Migration and rollback policy

No schema migration is proposed by this report alone. Any implementation that changes schema should ship as a new additive migration. Before introducing a constraint, run a read-only preflight for violating rows and report them; do not silently alter/delete existing financial or tenant data. Rollback should remove only the newly added constraint/index/column in reverse dependency order. A trigger-based PostgreSQL invariant, if selected, must include a matching reverse `RunSQL` operation and be tested against PostgreSQL CI.
