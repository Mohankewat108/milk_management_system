# Automated ledger posting

This increment connects the ledger foundation to existing finance and milk-collection approval workflows. It is intentionally opt-in per organisation.

## Configuration

Create a `LedgerConfiguration` for an organisation after setting up its chart of accounts and an open accounting period. Map each field to an active account belonging to the same organisation:

| Mapping | Required account type |
|---|---|
| Cash, bank, mobile wallet, online clearing, other payment | Asset |
| Receivables | Asset |
| Farmer payable | Liability |
| Procurement expense | Expense |
| Sales revenue | Income |
| Default expense | Expense |

Enable `is_enabled` only after all mappings are correct. Automated posting validates account tenant ownership, active state and account type at posting time. A missing or disabled configuration leaves the existing approval/completion workflow operational without generating a journal.

## Posting rules

- **Approved expense:** debit the configured default expense account; credit the account mapped to the expense payment method.
- **Completed incoming customer payment:** debit the payment-method asset/clearing account; credit receivables.
- **Completed outgoing farmer payment:** debit farmer payable; credit the payment-method asset/clearing account.
- **Approved farmer milk collection:** when `enable_farmer_collection_posting` is enabled, debit procurement expense; credit farmer payable.
- **Approved customer collection:** when `enable_customer_sales_posting` is enabled, debit receivables; credit sales revenue.

Customer collection semantics must be confirmed by each dairy before enabling customer sales posting. If the customer's milk collection represents a purchase from that customer rather than a sale by the dairy, this rule is not appropriate. Keep the flag disabled until the organisation has explicitly configured the intended business meaning.

## Transactional and retry behaviour

The source workflow state change and journal posting run in the same database transaction. A posting failure rolls back the approval/completion change. Source-specific idempotency keys prevent ordinary retries from creating duplicate journals. Journals retain the originating source type and UUID.

## Historical records

No historical payments, expenses or collections are backfilled. The hooks only run when a record transitions through the relevant service after this feature is deployed and the organisation has explicitly enabled its ledger configuration. No automatic opening balance is inferred.

## Still outstanding

This increment does not implement invoice allocation, bank statement import/matching, statement-level reconciliation, settlement statements, tax handling, multi-currency/FX, year-end closing entries, or database-trigger-enforced append-only journal protection. Invoice allocations depend on the invoice/credit-note models in the next finance work package. These are not represented as completed capabilities.
