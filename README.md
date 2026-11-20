# DairyNexus — multi-tenant dairy management SaaS

DairyNexus is the Python/Django replacement being developed for the original PHP Milk Management System.

> Migration status: active foundation branch, not yet a production-ready commercial release. The original PHP files remain on main and have not been overwritten.

## Implemented foundation

- Django 5.2-compatible project structure and custom UUID user model.
- Username/email login, Django sessions, password reset/change and login throttling.
- Tenant organisations, branch memberships, roles and explicit branch assignments.
- Separate Customer and Farmer domain models with account linking, a customer portal and a farmer self-service portal.
- Effective-dated SNF/FAT/Lactose pricing and configurable quality ranges.
- Server-side Decimal pricing and collection calculations with historical snapshots.
- Collection submission and approval workflow.
- Pending/completed payment workflow with transactional verification.
- Inventory items, supplier directory and transactional stock movement workflow.
- Pending/approved expense recording alongside payment management.
- Subscription plan/subscription models and superuser platform overview.
- Audit events, demo seeding, responsive templates, security/operations documentation.

## Stack

Python 3.12+, Django 5.2, PostgreSQL (production), SQLite (local), Django ORM, Django templates, WhiteNoise, Gunicorn and Redis (production cache).

## Windows PowerShell setup

1. Create and activate a Python virtual environment:

    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements/development.txt
    Copy-Item .env.example .env

2. Set a unique DJANGO_SECRET_KEY in .env. Optionally set DJANGO_DEMO_PASSWORD for local demo logins.

3. Generate and review initial migrations. This project uses a custom user model:

    python manage.py makemigrations accounts core organizations parties pricing collections finance inventory audit platform_admin
    python manage.py migrate
    python manage.py check
    python manage.py createsuperuser

Commit reviewed migration files before any production deployment. CI generates migrations in its runner for model validation, but production must use reviewed, committed migration files.

4. Seed fictional demo data and start the server:

    python manage.py seed_demo_data
    python manage.py runserver

Open http://127.0.0.1:8000/.

## Demo accounts

Set DJANGO_DEMO_PASSWORD before seeding. Usernames are demo-platform-admin, demo-owner-1 through demo-owner-3, demo-staff-1-1 through demo-staff-3-3, and demo-customer-1 through demo-customer-3. Demo identities are fictional and must not be used in production.

To clear only organisations already explicitly marked as demo and their dependent business records, run python manage.py seed_demo_data --clear. The command does not clear ordinary organisations or user accounts.

## Main routes

| Route | Purpose |
|---|---|
| / | Public landing page |
| /accounts/register/ | Account registration |
| /accounts/login/ | Login |
| /business/register/ | Dairy workspace onboarding |
| /business/<slug>/ | Business dashboard |
| /business/<slug>/staff/ | Staff and branch assignments |
| /business/<slug>/customers/ and /farmers/ | Party directories |
| /business/<slug>/collections/ | Milk collection list |
| /business/<slug>/pricing/ | Pricing configuration |
| /business/<slug>/quality/ | Quality profiles |
| /business/<slug>/payments/ | Payments |
| /portal/ | Customer portal (linked customer accounts) |\n| /farmer/ | Farmer self-service portal (linked farmer accounts) |
| /platform/ | Superuser platform control centre and multi-farm onboarding |
| /healthz/ | Database health check |

## Docker

Copy .env.example to .env, set local secret values, then run docker compose up --build. The Compose file is for local development and must not be used as a production deployment procedure.

## Tests

Run python manage.py test and pytest. GitHub Actions runs migration generation, Django checks and the automated test suite on pushes and pull requests.

## Legacy migration blocker

The old README references milk.sql, but that SQL dump is absent from the repository tree. The exact legacy schema and generated milk_total_price expression cannot be verified. No legacy business data has been migrated. Obtain a current MySQL export and schema before planning cutover. See docs/legacy-audit.md.

## Current limitations

Advanced supplier purchasing/payables, double-entry accounting, invoice/statement generation, subscription charging and plan-limit enforcement, farmer ordering and self-service profile edits, notification delivery, exports, richer reporting, background jobs, MFA, email verification, production SMTP credentials/provider setup, invitation revocation UI, database-level RLS and committed reviewed migrations remain outstanding. See docs/architecture.md, docs/security.md and docs/operations.md.

## Original source

The original PHP implementation remains on main. The original README described the PHP project as educational; confirm licensing before distributing the replacement commercially.
## Front-end design system

DairyNexus uses a mobile-first, light-theme design system in `static/css/app.css`. The shared layout is `templates/base.html`; new pages should extend it and use the existing component classes rather than adding page-global rules.

### Tokens
- **Primary:** `--color-primary` and `--color-primary-strong` — trustworthy dairy blue for primary actions and navigation.
- **Surfaces:** `--color-page`, `--color-surface`, and `--color-border` — soft blue-gray page canvas, white cards and subtle dividers.
- **Accent:** `--color-accent` — teal accent for supporting emphasis.
- **Feedback:** `--color-success`, `--color-warning`, `--color-danger`, and `--color-info` with matching background tokens.
- **Typography, spacing, radii and shadows:** use the `--font-size-*`, `--space-*`, `--radius-*` and `--shadow-*` tokens.

### Components
Use `.button`, `.button-secondary`, `.panel`, `.content-card`, `.auth-card`, `.page-heading`, `.kpi-grid`, `.tag`, `.status`, `.table-wrap`, `.search-form`, `.pagination`, `.alert` and `.empty` for common page patterns. Forms should use real labels linked to field IDs and keep Django's generated errors adjacent to their fields.

### Accessibility and responsiveness
The shared shell includes a skip link and visible keyboard focus. Respect reduced-motion preferences. Layout breakpoints are designed for compact mobile, tablet and desktop widths. Tables scroll horizontally inside `.table-wrap`; print styles remove navigation and interactive controls.

Avoid styling `body`, `main`, bare `table` or bare headings in legacy feature stylesheets. Scope any remaining legacy page styles under a page-specific class. Keep Django template tags and server field contracts unchanged.
## Farm-owner email invitations

The platform owner can create a dairy tenant by entering the farm owner's name and email address. DairyNexus creates the tenant, initial branch, inactive account (when the email is new), pending OWNER membership and a single-use invitation token in one database transaction. The invitation link expires after 48 hours and only its SHA-256 hash is stored.

A new recipient opens the link and sets their password. An existing account holder must sign in with the invited account before accepting. Acceptance activates the membership and adds the farm to the user's workspace list. Replayed, expired or revoked tokens are rejected.

For local development, Django writes invitation emails to the runserver console by default. For real delivery, configure the SMTP variables in `.env` or the deployment secret manager:

- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `EMAIL_USE_SSL`
- `DEFAULT_FROM_EMAIL`

Never commit SMTP passwords. Use a transactional email provider and a sender domain you control in staging/production. The current implementation does not yet include an invitation resend/revoke management screen or background email queue.


## SaaS workspace UI update

A feature branch named `feature/saas-dashboard-collections-ui` contains an in-progress UI upgrade:

- Shared authenticated workspace shell with permission-aware sidebar navigation and mobile drawer.
- Light, dark and system theme selection persisted in browser local storage.
- Django language middleware and language selector for configured English, Nepali, Danish and Hindi locales.
- Milk collection edit route and form, with tenant/branch permission scoping and audit event capture.
- Collection listing now exposes an Edit action.

The collection edit operation intentionally retains the original effective-dated milk rate snapshot and recalculates the amount using that saved rate. It does not automatically revise already-generated farmer payment entries. Review reconciliation requirements before enabling edits on financially settled/approved records.

This is a development change set, not a verified production release. Run the Django checks and automated tests locally/CI before merging. Existing feature modules are not all upgraded to full CRUD by this change set.


## Full CRUD and central Trash development phase

Branch: `feature/full-crud-soft-delete`

### Editable business records
- Organisation profile: owner-managed profile updates.
- Branches: create, list, update, and soft-delete when no operational history is linked.
- Farmers and customers: existing create/read/update/soft-delete flows retained.
- Milk collections: create/read/update for editable states; approved entries are locked and corrected through a reasoned reversal workflow. Edits recalculate the rate from the collection's saved historical pricing coefficients.
- Inventory items and suppliers: create/read/update/soft-delete. Items with non-zero stock or stock-movement history are protected.
- Payments: create/read/update/soft-delete only while pending or failed. Completed and reversed payments are protected.
- Expenses: create/read/update/soft-delete while pending or rejected. Approved expenses are protected.
- Pricing schedules: create/read/approve; only unapproved schedules without linked collections may be edited or moved to Trash. Approved or referenced schedules are immutable.
- Staff: invitation, account activation, role editing, branch reassignment, membership suspension/reactivation and invitation revocation.
- Stock movements and approved quality/rate history remain append-only/versioned rather than being edited or erased.

### Central Trash
- Tenant-scoped Trash list across customers, farmers, branches, suppliers, inventory items, eligible payments/expenses and unapproved pricing schedules.
- Restore action and audit events for delete/restore operations.
- Role-based delete permissions and branch scoping.
- No permanent-delete action is exposed: retained business records should not be irreversibly removed through the application UI.

### Verification
This branch includes central soft-delete unit tests and migration files. Run `python manage.py makemigrations --check --dry-run`, `python manage.py migrate`, `python manage.py check`, and `python manage.py test` in the configured environment before production deployment. This development branch has not been approved or merged into `main`.
