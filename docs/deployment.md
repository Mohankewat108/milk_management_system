# Deployment guide

## Production prerequisites

- PostgreSQL database and application-specific least-privilege role.
- Redis for shared login-rate-limit cache and future asynchronous tasks.
- TLS-enabled reverse proxy/load balancer.
- Secret manager for the Django key, database URL, email credentials and service credentials.
- Configured SMTP or transactional email provider.
- Committed and reviewed Django migration files.
- A tested backup and restore process.

## Required environment

```text
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<high-entropy-random-secret>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=your-domain.example
DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.example
DATABASE_URL=postgresql://<app-user>:<password>@<postgres-host>:5432/<database>
REDIS_URL=redis://<redis-host>:6379/0
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_DEFAULT_CURRENCY=NPR
DJANGO_DEFAULT_TIME_ZONE=Asia/Kathmandu
```

Do not commit this file or inject secrets into Docker build arguments.

## Release sequence

1. Build and scan the immutable container image.
2. Restore a recent database backup into staging.
3. Apply reviewed migrations in staging.
4. Run Django checks and the full test suite.
5. Run a tenant-isolation smoke test with two organisations.
6. Run a restore/reconciliation rehearsal.
7. Deploy the image behind TLS.
8. Apply migrations as a one-off release job, not independently from every web worker.
9. Run `collectstatic`.
10. Verify `/healthz/`, login, a test collection, pricing snapshot, payment pending/completion flow and customer portal.
11. Monitor application errors, database health, cache health and audit events.

## Scaling notes

The current implementation is a synchronous Django monolith. Use multiple Gunicorn workers behind a reverse proxy and shared PostgreSQL/Redis. Before adding Celery, define retry/idempotency policies for every financial or collection-related task. Do not run scheduled jobs from web workers.

## Rollback

- Keep the previous image digest available.
- Back up the database before migrations.
- Prefer forward-compatible migrations and expand/contract changes.
- Do not automatically roll back a migration that has removed or transformed data.
- Legacy PHP source remains on the original `main` branch for reference, but that is not a data rollback plan.
