# Local development and operations

## Supported development setup

- Python 3.12+
- SQLite for a single-user local development instance
- PostgreSQL for production-like validation
- Redis for the shared production cache
- Git and GitHub Actions

## Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements/development.txt
Copy-Item .env.example .env
```

Edit `.env` and set a unique `DJANGO_SECRET_KEY`. Set `DJANGO_DEMO_PASSWORD` only if you want password-enabled local demo accounts.

## First database setup

The repository uses a custom user model, so the initial migrations must be generated before the first migration is applied:

```powershell
python manage.py makemigrations accounts core organizations parties pricing collections finance inventory audit platform_admin
python manage.py migrate
python manage.py check
python manage.py createsuperuser
```

Review and commit all generated migration files before deploying. The feature branch currently contains models and CI migration generation; production rollout must not proceed until reviewed migration files have been checked in.

## Demo data

```powershell
python manage.py seed_demo_data
python manage.py seed_demo_data --clear
```

- Set `DJANGO_DEMO_PASSWORD` in `.env` before seeding to enable demo login.
- Demo usernames: `demo-platform-admin`, `demo-owner-1` to `demo-owner-3`, `demo-staff-1-1` to `demo-staff-3-3`, and `demo-customer-1` to `demo-customer-3`.
- If no demo password is configured, seeded demo users receive unusable passwords.
- `--clear` removes only organisation records already marked `is_demo=True` and their dependent business records. It does not clear non-demo organisations or remove user accounts.
- Demo accounts and data are fictional and must never be used as production identities.

## Run locally

```powershell
python manage.py runserver
```

Useful routes:
- `/` — landing page
- `/accounts/register/` — account registration
- `/accounts/login/` — login
- `/business/register/` — dairy workspace onboarding
- `/business/<slug>/` — business dashboard
- `/business/<slug>/staff/` — staff and branch assignments
- `/business/<slug>/customers/` and `/farmers/` — party directories
- `/business/<slug>/collections/` — collection list
- `/business/<slug>/pricing/` — pricing configuration
- `/business/<slug>/quality/` — quality profiles
- `/business/<slug>/payments/` — payment records
- `/portal/` — customer portal
- `/platform/` — platform overview (superuser only)
- `/healthz/` — database health check

## PostgreSQL environment

Set a PostgreSQL URL such as:

```text
DATABASE_URL=postgresql://dairynexus:replace-me@db:5432/dairynexus
```

Use a dedicated least-privilege database role. Do not use the PostgreSQL superuser from the application.

## Production commands

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Set the environment secrets and trusted origins before starting production. Configure SMTP, Redis, TLS termination, backup/restore, log routing and alerting before real users are onboarded.

## Tests

```powershell
python manage.py test
pytest
```

CI runs the Django system check, generates migration files in the ephemeral runner for validation, applies migrations, and runs the test suite. That generation step does not replace committing reviewed migrations to the repository.
