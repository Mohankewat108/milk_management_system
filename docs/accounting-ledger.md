# Accounting ledger foundation

## Scope

This increment adds the tenant-scoped double-entry ledger primitives to the existing `finance` Django app. It does not backfill or rewrite historical payment, expense, or milk-collection records.

## Data model

- **Account** is a tenant-owned chart-of-accounts row with a code, account type, normal balance, optional parent, and system/manual-entry flags.
- **AccountingPeriod** defines an organisation's open or closed posting window. The service rejects overlapping periods and posting into closed periods.
- **JournalEntry** records the organisation, branch, period, reference, date, source identity, idempotency key, creator, and posting metadata.
- **JournalLine** records one account and exactly one positive debit or credit amount.

All money values use the organisation's configured base currency and two decimal places in this initial ledger increment. Foreign-currency accounting and FX revaluation are not implemented.

## Posting invariants

Use `apps.finance.ledger_services.post_journal_entry` for all postings. It:

1. Requires active tenant membership and access to the selected branch.
2. Requires an active branch belonging to the organisation.
3. Requires an open accounting period covering the entry date.
4. Requires at least two lines, active tenant-owned accounts, and exactly one positive side per line.
5. Requires total debits to equal total credits and be greater than zero.
6. Creates the entry and all lines in one database transaction, then marks it posted.
7. Supports an organisation-scoped idempotency key to prevent duplicate posting on retries.

Posted journal entries and their lines reject normal model-level save/delete attempts. The original journal is not edited to correct a mistake: use `reverse_journal_entry` to create a separately posted equal-and-opposite journal linked to the original. Database administrators can still bypass application-level immutability; production database permissions and/or database triggers are a later hardening task.

## Starter chart of accounts

`create_default_chart_of_accounts` can create a starter set once per organisation. It does not overwrite existing account names, types, or settings. The initial accounts cover cash, bank, receivables, milk inventory, payables, farmer milk payable, owner equity, milk sales revenue, procurement expense, and operating expenses.

## Important integration boundary

This increment deliberately does **not** automatically post existing payments, expenses, or collections, and it does not create opening balances or historical journals. Existing business workflows therefore continue to operate without being blocked by an organisation that has not configured its chart and accounting periods.

The next accounting increment must add reviewed posting adapters and lifecycle hooks for:
- approved expenses (expense debit; cash/bank/mobile-wallet credit),
- completed incoming customer payments (cash/bank debit; receivables credit),
- completed outgoing farmer payments (farmer payable debit; cash/bank credit),
- approved farmer milk collections (procurement debit; farmer payable credit), and
- customer milk sales/collections (receivable or cash debit; milk revenue credit, depending on the dairy's sale/credit policy).

Before enabling those hooks, the product must define cash/bank/mobile-wallet account mapping, the accounting treatment of farmer milk collections, and whether a collection represents a sale or procurement in each workflow. No historical records should be posted automatically without an explicit, separately reviewed opening-balance/backfill plan.

## Current limitations

Payment allocation to invoices/receivables, bank statement import and matching, reconciliation workflows, fiscal year closing/retained earnings, tax accounts, multi-currency/FX, and database-enforced append-only controls are not part of this foundation. They remain subsequent work, not completed features.
