# DairyNexus — multi-tenant dairy management SaaS

DairyNexus is the Python/Django replacement being developed for the original PHP Milk Management System.

> **Release status: development only.** Do not onboard real dairy businesses or production personal/financial data until every P0 item in [the production release gate](docs/production-release-gate.md) has evidence and approval.

## Implemented foundation

- Django project and custom UUID user model.
- Username/email login, Django sessions, password reset/change and basic login throttling.
- Tenant organisations, branches, memberships, roles and explicit branch assignments.
- Customer and Farmer records plus a basic customer portal.
- Effective-dated SNF/FAT/Lactose pricing and configurable quality ranges.
- Decimal milk calculation with pricing/quality snapshots and collection approval workflow.
- Pending/completed payment workflow and approval-based expense recording.
- Supplier directory, inventory items and transactional stock movement service.
- Subscription plan/subscription data models and superuser platform overview.
- Audit events, fictional demo seeding, responsive Django templates.
- Docker development environment and GitHub Actions CI.

## Stack

Python 3.12+, Django 5.2, PostgreSQL (CI/production), SQLite (quick local development), Redis, WhiteNoise and Gunicorn.

## Windows PowerShell quick start

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements/development.txt
Copy-Item .env.example .env
```

Set a unique local `DJANGO_SECRET_KEY` in `.env`. Generate and review initial migrations before applying them:

```powershell
python manage.py makemigrations accounts core organizations parties pricing collections finance inventory audit platform_admin
python manage.py migrate
python manage.py check
python manage.py createsuperuser
python manage.py seed_demo_data
python manage.py runserver
```

Open http://127.0.0.1:8000/.

## Demo users

Set `DJANGO_DEMO_PASSWORD` before seeding if you need to sign in as demo users. Demo accounts and data are fictional and must never be used in production. The seed command's `--clear` option only removes organisations explicitly marked as demo.

## Core routes

- `/accounts/login/` — login
- `/business/register/` — create a dairy workspace
- `/business/<slug>/` — dairy workspace
- `/portal/` — customer portal
- `/platform/` — platform superuser overview
- `/healthz/` — liveness check
- `/readyz/` — readiness check (fails while migrations are missing or pending)

## CI

GitHub Actions runs Django checks and tests using PostgreSQL and Redis services, generates migration files only inside its ephemeral runner for test execution, reports branch coverage and audits Python dependencies. The CI-generated migration files are not committed and do not satisfy the production migration gate.

## Known incomplete scope

Double-entry accounting, invoices/statements, supplier purchasing, farmer portal, real subscription billing and entitlement enforcement, provider payment webhooks, notification delivery, export/reporting suite, MFA, email/phone verification, database RLS, legacy data migration and production deployment remain incomplete. See [architecture](docs/architecture.md), [security](docs/security.md), [operations](docs/operations.md), and [production release gate](docs/production-release-gate.md).

## Legacy data

The old README references `milk.sql`, but that SQL dump is absent from the repository. No legacy data has been imported. Obtain and verify the actual MySQL export/schema and confirm the historical milk-price formula before planning cutover.

## Commercial use

The old README describes the PHP project as educational. Confirm ownership and licensing of all original assets/code before commercial distribution.
