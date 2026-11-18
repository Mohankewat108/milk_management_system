# Data exports, imports and scheduled jobs

## Features
- CSV, XLSX and PDF exports for farmers, customers, milk collections, payments, expenses, inventory and suppliers.
- Export requests are persisted as database jobs and processed by a Django management command.
- Files are served through an authenticated, organisation-scoped download view. Links expire after seven days.
- CSV imports create new farmer/customer records only. Existing organisation codes are not overwritten. Each invalid row is recorded in the import batch.
- Saved export templates and daily, weekly or monthly schedules are stored per organisation.
- Export completion/failure and import completion email notifications use Django's configured email backend.
- Reports are restricted by organisation and branch membership.

## Run migrations
    python manage.py migrate

## Run the worker
Run this command continuously from a process supervisor, or on a short recurring schedule:

    python manage.py process_data_jobs --limit 20

It processes queued exports, uploaded imports, due schedules, and deletes expired export files. The command is safe to invoke repeatedly; job status transitions prevent an already-claimed export from being processed twice.

Example cron entry (every minute):

    * * * * * cd /srv/dairynexus && /srv/dairynexus/.venv/bin/python manage.py process_data_jobs --limit 20 >> /var/log/dairynexus-data-jobs.log 2>&1

Use a supervisor/worker process in container deployments instead of cron if preferred. Only one scheduled worker should run per deployment unless you add dedicated locking for import batches and schedule rows.

## Email configuration
Set DJANGO_EMAIL_BACKEND, EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_TLS, and DEFAULT_FROM_EMAIL. The development default is Django's console email backend; production delivery requires a configured SMTP provider.

## CSV import format
Required headers: code,full_name.
Optional headers: phone,email,address,branch_code.
Use the sample downloads in Import Centre. CSV uploads are limited to 10 MB. Import processing validates each row, checks branch codes within the current organisation, and rejects duplicate codes rather than overwriting records.

## Limits and current scope
- Instant file generation is capped at 20,000 rows. PDF exports are capped at 2,500 rows; choose XLSX for larger datasets.
- Import Centre currently supports farmers and customers. It is append-only; it does not bulk edit or delete.
- Bulk activation/deactivation currently supports farmers and customers. Financial records and milk collections do not expose destructive bulk actions.
- Scheduled exports currently deliver to the schedule creator's email address; arbitrary recipient lists are intentionally not enabled.
- PDF uses ReportLab's built-in Helvetica fonts. Nepali/Devanagari glyph coverage is not guaranteed in PDF; XLSX and UTF-8 CSV should be used for Nepali text until a licensed Unicode font is bundled.
- Schedules are enqueued by the worker command; they do not run unless the command is deployed and scheduled.
- Private export/import files must remain outside any publicly served static/media directory in production. Configure the media volume so private_exports/ and private_imports/ are not directly exposed; use only the authenticated download view.

## Security checklist before production
1. Configure SMTP and verify completion/failure notifications.
2. Store private uploads in a non-public volume and back them up with restricted access.
3. Ensure the worker command is running and monitored.
4. Set upload size limits at the reverse proxy as well as Django.
5. Test cross-organisation IDs, branch-assignment changes, and role revocation with dedicated integration tests.
6. Add malware scanning for uploaded CSV files if imports are opened to less-trusted operators.
7. Configure HTTPS, secure cookies, and secret management independently of this feature.
