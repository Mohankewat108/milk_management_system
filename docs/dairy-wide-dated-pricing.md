# Dairy-wide dated milk pricing

A PricingConfiguration belongs to a dairy Organization tenant. If its Branch is blank, the approved configuration is the common schedule for all customers and all branches in that dairy. Customer records do not carry individual rate coefficients.

A branch-specific configuration is an explicit override and applies only to collections at that branch. Branch overrides do not modify other branches.

## Dairy owner workflow
1. Open the dairy workspace and choose Milk rate management.
2. Leave Branch as “All customers and all branches”.
3. Enter SNF, fat and lactose coefficients.
4. Select effective-from and optional inclusive effective-to dates.
5. Save. Owner-created rates are approved immediately; Admin-created rates await owner approval.
6. The server resolves the effective configuration using the collection date and branch. The selected version, dates, coefficients and components are snapshotted to the collection.

## Pricing formula
Existing formula is retained: (SNF × SNF coefficient) + (Fat × Fat coefficient) + (Lactose × Lactose coefficient). The dairy must confirm coefficient units, output currency/unit, and rounding policy before commercial use.

## Historical integrity
Do not overwrite old rates or recalculate already-recorded milk collections when a future rate changes. Close the old range and publish a new version. Corrections to prior transactions require a separate adjustment/reversal workflow.

## Launch checks
Run makemigrations --check --dry-run, migrate against a database backup, manage.py check and the complete test suite. Review date/time handling against each Organization.timezone before production deployment.
