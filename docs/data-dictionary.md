# Core data dictionary

The tables below summarise the principal business models currently present in code. This is not a substitute for the generated Django migration/SQL schema.

| Model | Tenant field | Key attributes | Integrity / behaviour |
|---|---|---|---|
| User | — | UUID, username, unique email, phone, verification flags, timezone, profile photo | Django AbstractUser; password hash managed by Django |
| Organization | — | owner, name, slug, legal name, registration no., status, country, currency, timezone | UUID; status trial/active/suspended/closed |
| Branch | organization | code, name, address, phone, manager, active | code unique within organisation |
| Membership | organization | user, role, status, invited email, joined timestamp | one membership per user+organisation |
| BranchAssignment | via membership | membership, branch | unique pair; role-specific branch scope |
| Customer | organization | code, name, phone, email, address, village/ward, optional linked user | code unique within organisation |
| Farmer | organization | code, name, contact, address, protected bank fields, optional linked user | separate from customers; code unique within organisation |
| PricingConfiguration | organization | optional branch, version, three rates, effective date range, approval | decimal rates, nonnegative checks, version unique per organisation |
| QualityConfiguration | organization | optional branch, version, min/max SNF/FAT/lactose, effective date range, approval | each minimum must be nonnegative and maximum >= minimum |
| MilkCollection | organization | branch, one farmer/customer, actor, timestamp, litres, quality, rate, amount, pricing snapshot, status | positive quantity; exactly one party; historical rate/config retained |
| Payment | organization | branch, direction, one party, decimal amount, currency, method, status, paid timestamp | positive amount; exactly one party; initially pending in web workflow |
| InventoryItem | organization | branch, code, name, unit, stock, reorder level, purchase price | code unique within organisation |
| StockMovement | organization | item, kind, quantity delta, reason, reference, actor | movement history; service locks item row and disallows negative stock |
| SubscriptionPlan | — | name, code, monthly/annual price, limits, features | unique name and code |
| Subscription | organization | plan, status, start/end date, auto-renew | historical subscription records retained |
| AuditEvent | optional organization | actor, action, target type/id, JSON changes, IP and user agent | ordered newest-first; admin is read-only |

## Currency and decimal policy

- Monetary values use Django `DecimalField`; no binary floats are used in business calculations.
- Milk quantities are stored to three decimal places.
- Quality values are stored to three decimal places.
- Per-component pricing coefficients are stored to four decimal places.
- Calculated rate and payment totals are stored to two decimal places.
- Organisation currency is currently a three-character ISO-style code field; currency-specific minor-unit rounding rules need to be added for currencies that do not use two decimal places.
