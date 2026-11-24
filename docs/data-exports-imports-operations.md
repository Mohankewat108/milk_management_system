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
The repository's Docker Compose configuration includes a worker service. Starting the stack with docker compose up --build runs the background worker automatically. For a non-Compose deployment, run the continuous worker under a process supervisor (systemd, Supervisor, or Windows Task Scheduler). The command supports continuous polling:

    python manage.py process_data_jobs --limit 20 --loop --interval 5

Without `--loop`, it runs one batch and exits (suitable for cron). In loop mode, it polls every five seconds by default; `--interval` is clamped to 1–300 seconds. It processes queued exports, uploaded imports, due schedules, and expired export cleanup. Keep one worker instance unless import/schedule locking is added.


### Local Windows development

Run from the project root in PowerShell:


    .\.venv\Scripts\python.exe manage.py process_data_jobs --limit 20 --loop --interval 5


Keep this terminal open while testing queued exports. Stop the worker with Ctrl+C.


### Docker Compose

The Compose `worker` service uses the same built-in loop mode and restarts unless stopped. Start the stack with:


    docker compose up --build


Ensure Docker Desktop is running and `.env` contains valid `KEY=value` entries before starting Compose.

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
- Export and import files are stored under the private_uploads directory, outside MEDIA_ROOT, using a storage backend that refuses public URLs. Persist this directory on a restricted volume in production; use only the authenticated download view.

## Security checklist before production
1. Configure SMTP and verify completion/failure notifications.
2. Store private uploads in a non-public volume and back them up with restricted access.
3. Ensure the worker command is running and monitored.
4. Set upload size limits at the reverse proxy as well as Django.
5. Test cross-organisation IDs, branch-assignment changes, and role revocation with dedicated integration tests.
6. Add malware scanning for uploaded CSV files if imports are opened to less-trusted operators.
7. Configure HTTPS, secure cookies, and secret management independently of this feature.
