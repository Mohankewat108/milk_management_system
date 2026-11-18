# Local development and operations

## Supported development setup

- Python 3.12+
- SQLite for quick local development
- PostgreSQL for CI, staging and production
- Redis for shared production caching and rate limiting
- GitHub Actions for automated checks

## Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements/development.txt
Copy-Item .env.example .env
```

Set a unique `DJANGO_SECRET_KEY` in `.env`. Set `DJANGO_DEMO_PASSWORD` only when you need local demo logins.

## Initial database setup

The custom UUID user model must be included in the initial migration set:

```powershell
python manage.py makemigrations accounts core organizations parties pricing collections finance inventory audit platform_admin
python manage.py migrate
python manage.py check
python manage.py createsuperuser
```

Review and commit every generated migration file. Never let production generate migrations at startup. Before deployment, run against an empty PostgreSQL database and a restored staging backup:

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py migrate --check
python manage.py check --deploy --settings=config.settings.production
python manage.py check_release_readiness --settings=config.settings.production
```

The release-readiness command intentionally fails while any required application lacks a committed migration package or when the database is not PostgreSQL.

## Demo data

```powershell
python manage.py seed_demo_data
python manage.py seed_demo_data --clear
```

Demo users are fictional and must never be used in production. The clear command only removes organisations marked as demo; it does not clear normal tenant records or delete user accounts.

## Run locally

```powershell
python manage.py runserver
```

Routes include `/accounts/login/`, `/business/register/`, `/business/<slug>/`, `/portal/`, and `/platform/`.

## Health and readiness

- `/healthz/` is a liveness check: it verifies that the process can query the database.
- `/readyz/` is a readiness check: it returns HTTP 503 while database migrations are pending.

Do not expose detailed exception traces from health endpoints.

## Production environment

Production requires PostgreSQL, Redis, a strong secret, allowed hosts, trusted CSRF origins, and a real SMTP provider. Configure `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `DEFAULT_FROM_EMAIL` through a secret manager. Do not commit `.env` or real credentials.

Use a dedicated least-privilege database role. Put the app behind a TLS-terminating reverse proxy that overwrites forwarded-protocol headers. Configure SMTP delivery, backups, restore drills, monitoring and alerting before onboarding real users.

## Production commands

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py check --deploy
python manage.py check_release_readiness
python manage.py migrate --check
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Run migrations as a controlled release step, not from every web container.

## Tests

```powershell
python manage.py test
pytest
```

GitHub Actions uses PostgreSQL and Redis services, generates migrations in the ephemeral CI workspace for test execution, runs the suite with coverage and audits dependencies. This ephemeral generation is not a substitute for checked-in, reviewed production migrations.
