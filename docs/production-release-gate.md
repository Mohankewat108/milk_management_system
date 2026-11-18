# Production release gate

## Release decision

**Current status: NOT APPROVED FOR PRODUCTION.** The codebase is a development foundation. A green unit-test run is not a production-readiness certificate.

This document is an explicit release gate. Every item marked BLOCKER must be evidenced and signed off before real dairy businesses or personal/financial data are onboarded.

## P0 — mandatory before any production data

- [ ] Generate, review and commit initial migrations for every installed app. Confirm the custom UUID user model is created in the first migration. Run migrations against an empty PostgreSQL database and a restored staging copy.
- [ ] Add automated checks that fail if model changes are missing migrations. CI must validate committed migrations rather than silently generating and discarding them.
- [ ] Obtain the actual legacy MySQL dump and schema. Map every table, key, generated column, timestamp, decimal precision and status. Build a repeatable import with row counts, financial reconciliation, duplicate handling and rollback. The old `milk.sql` is not in this repository.
- [ ] Complete tenant/branch authorization tests for every view, form, mutation, export, admin action, background task and future API. Test cross-tenant object IDs and branch boundary bypasses.
- [ ] Add PostgreSQL row-level security (RLS) or an independently reviewed equivalent defence-in-depth policy. The current code relies on application-level scoping.
- [ ] Implement and test MFA for platform superusers and privileged tenant owners; implement email verification and secure invitation acceptance.
- [ ] Configure real SMTP/transactional email, verified sender/domain, reset/invitation delivery, bounce handling and abuse limits.
- [ ] Replace demo/local secrets. Use a deployment secret manager, least-privilege PostgreSQL role, TLS, Redis authentication/network isolation and restricted admin access.
- [ ] Run dependency, static-analysis, secret and container scans. Fix all critical/high findings and commission an independent penetration test.
- [ ] Define personal-data retention, privacy notice, access/export/correction/deletion processes, incident response and applicable legal review for each operating country.
- [ ] Verify backups, point-in-time recovery and restore drills; document RPO/RTO and who can access backups.

## P1 — financial correctness and operational completeness

- [ ] Implement a double-entry general ledger with immutable journal entries, balanced debit/credit constraints, posting/reversal workflow, chart of accounts and accounting periods.
- [ ] Reconcile every payment to an invoice/collection/party balance; prevent duplicate provider webhooks with idempotency keys.
- [ ] Add invoices, credit notes, receipts, customer statements, farmer statements, supplier bills, supplier payments, bank reconciliation and period close.
- [ ] Add approval limits, segregation of duties, immutable status history and audit evidence for sensitive financial changes.
- [ ] Validate rounding, tax, currency and timezone behaviour with a qualified local accounting reviewer. Never hard-code tax rules for Nepal or another country without a maintained ruleset.

## P1 — dairy domain

- [ ] Confirm the exact milk pricing formula with the business owner and document units, precision, rounding and effective-date precedence.
- [ ] Add collection-centre close/reconciliation, duplicate-entry prevention, corrections through reversal rather than destructive edits, and farmer/customer balance ledgers.
- [ ] Add daily/monthly production, quality, farmer, branch and reconciliation reports with CSV/XLSX/PDF exports.
- [ ] Test daylight-saving and local-midnight boundaries for every supported timezone.
- [ ] Add offline/mobile collection capture only with conflict resolution and server-side recalculation.

## P1 — inventory and procurement

- [ ] Add purchase orders, approval, goods-received notes, supplier invoices, returns, stock transfers with paired source/destination movements, stock valuation and stocktake.
- [ ] Add immutable movement history, idempotency and concurrency tests on PostgreSQL.
- [ ] Add supplier payable reconciliation and low-stock notification rules.

## P1 — SaaS platform

- [ ] Implement subscription lifecycle, trial expiry, invoices, payment provider checkout, signed webhook verification, idempotency, refunds and cancellation.
- [ ] Enforce plan entitlements server-side for branch/staff/customer counts, features and usage; do not rely on hiding UI links.
- [ ] Add platform support audit, tenant suspension/reactivation workflow, platform revenue/retention metrics and support impersonation safeguards.
- [ ] Add service-level monitoring and customer-facing status/incident communication.

## P2 — reliability and scale

- [ ] Add a task queue with retry/backoff, dead-letter handling and idempotent task design for emails, exports, notifications and integrations.
- [ ] Add structured correlation IDs, error tracking, metrics, traces, alerting and dashboards.
- [ ] Add load tests for collection entry, reporting, concurrent stock movements and tenant isolation at expected peak volume.
- [ ] Add database index review, query budgets, pagination limits, caching strategy and capacity planning.
- [ ] Add staging deployment, rollback procedure, blue/green or rolling release strategy and tested disaster recovery.

## P2 — user experience and integration

- [ ] Complete farmer self-service portal and role-specific dashboards.
- [ ] Add accessible responsive UI, Nepali/English localisation, configurable currency/timezone/date formats and usability testing on low-end Android devices.
- [ ] Integrate SMS/WhatsApp only through verified providers with consent, opt-out and delivery audit.
- [ ] Add payment gateway integrations only after provider contracts, webhook signature validation and reconciliation tests.

## Evidence required for sign-off

A release candidate must attach: migration review, PostgreSQL test report, authorization matrix and test results, import reconciliation report, security scan reports, penetration-test report, backup restore evidence, accounting sign-off, privacy/legal review, load-test report, deployment rollback rehearsal and named operational owners.

## Non-negotiable data integrity rules

1. Never edit or delete posted financial journal entries; reverse them with linked compensating entries.
2. Never trust tenant, branch, price, total, role, plan or payment status supplied by the browser.
3. Never mark a payment completed solely because the browser returned from a payment page.
4. Never run destructive migrations or imports without verified backups and a rehearsed rollback.
5. Never use demo identities or passwords in production.
