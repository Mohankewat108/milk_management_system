# DairyNexus — multi-tenant dairy management SaaS

DairyNexus is the Python/Django replacement being developed for the original PHP Milk Management System.

> Migration status: active foundation branch, not yet a production-ready commercial release. The original PHP files remain on main and have not been overwritten.

## Implemented foundation

- Django 5.2-compatible project structure and custom UUID user model.
- Username/email login, Django sessions, password reset/change and login throttling.
- Tenant organisations, branch memberships, roles and explicit branch assignments.
- Separate Customer and Farmer domain models and customer portal.
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
| /portal/ | Customer portal |
| /platform/ | Superuser platform overview |
| /healthz/ | Database health check |

## Docker

Copy .env.example to .env, set local secret values, then run docker compose up --build. The Compose file is for local development and must not be used as a production deployment procedure.

## Tests

Run python manage.py test and pytest. GitHub Actions runs migration generation, Django checks and the automated test suite on pushes and pull requests.

## Legacy migration blocker

The old README references milk.sql, but that SQL dump is absent from the repository tree. The exact legacy schema and generated milk_total_price expression cannot be verified. No legacy business data has been migrated. Obtain a current MySQL export and schema before planning cutover. See docs/legacy-audit.md.

## Current limitations

Advanced supplier purchasing/payables, double-entry accounting, invoice/statement generation, subscription charging and plan-limit enforcement, farmer portal, notification delivery, exports, richer reporting, background jobs, MFA, email verification, production email delivery, database-level RLS and committed reviewed migrations remain outstanding. See docs/architecture.md, docs/security.md and docs/operations.md.

## Original source

The original PHP implementation remains on main. The original README described the PHP project as educational; confirm licensing before distributing the replacement commercially.