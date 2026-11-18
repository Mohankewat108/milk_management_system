import csv
import io
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.data_exports.models import ExportJob, ImportBatch, ScheduledExport
from apps.data_exports.queue import process_export_job, queue_export
from apps.organizations.models import Membership
from apps.parties.models import Customer, Farmer


def process_import_batch(batch):
    batch.status = ImportBatch.Status.PROCESSING
    batch.save(update_fields=["status", "updated_at"])
    imported, failed, errors, total = 0, 0, [], 0
    model = Farmer if batch.module == "farmers" else Customer
    try:
        with batch.file.open("rb") as source:
            text = source.read(10 * 1024 * 1024 + 1).decode("utf-8-sig")
        if len(text.encode("utf-8")) > 10 * 1024 * 1024:
            raise ValidationError("CSV exceeds the 10 MB processing limit.")
        reader = csv.DictReader(io.StringIO(text))
        required = {"code", "full_name"}
        headers = {str(h or "").strip().lower() for h in (reader.fieldnames or [])}
        if not required.issubset(headers):
            raise ValidationError("CSV must contain code and full_name columns.")
        for line_number, raw in enumerate(reader, start=2):
            total += 1
            row = {str(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            try:
                code, name = row.get("code", ""), row.get("full_name", "")
                if not code or not name:
                    raise ValueError("code and full_name are required")
                if len(code) > 40 or len(name) > 180:
                    raise ValueError("code or full_name exceeds the allowed length")
                branch = None
                branch_code = row.get("branch_code", "")
                if branch_code:
                    branch = batch.organization.branches.get(code=branch_code, deleted_at__isnull=True)
                values = {
                    "organization": batch.organization, "code": code, "full_name": name,
                    "phone": row.get("phone", "")[:30], "email": row.get("email", ""),
                    "address": row.get("address", ""),
                }
                if branch:
                    values["branch"] = branch
                if model.objects.filter(organization=batch.organization, code=code).exists():
                    raise ValueError("duplicate code already exists in this organisation")
                model.objects.create(**values)
                imported += 1
            except Exception as exc:
                failed += 1
                if len(errors) < 500:
                    errors.append({"row": line_number, "error": str(exc)[:250]})
        batch.total_rows = total
        batch.imported_rows = imported
        batch.failed_rows = failed
        batch.row_errors = errors
        batch.status = ImportBatch.Status.COMPLETED
    except Exception as exc:
        batch.status = ImportBatch.Status.FAILED
        batch.row_errors = [{"row": 0, "error": str(exc)[:250]}]
        batch.failed_rows = max(total, 1)
    batch.processed_at = timezone.now()
    batch.save(update_fields=["total_rows", "imported_rows", "failed_rows", "row_errors", "status", "processed_at", "updated_at"])
    return batch


class Command(BaseCommand):
    help = "Process queued exports, CSV imports and due scheduled exports. Run from cron or a worker."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 100))
        for job in ExportJob.objects.filter(status=ExportJob.Status.QUEUED).order_by("created_at")[:limit]:
            process_export_job(job.pk)
            self.stdout.write(f"Export {job.pk}: processed")
        remaining = max(0, limit - ExportJob.objects.filter(status=ExportJob.Status.PROCESSING).count())
        for batch in ImportBatch.objects.filter(status=ImportBatch.Status.UPLOADED).order_by("created_at")[:remaining]:
            process_import_batch(batch)
            self.stdout.write(f"Import {batch.pk}: {batch.status} ({batch.imported_rows} imported, {batch.failed_rows} failed)")
        now = timezone.now()
        for schedule in ScheduledExport.objects.filter(is_active=True, next_run_at__lte=now).select_related("organization", "created_by")[:limit]:
            try:
                membership = Membership.objects.get(organization=schedule.organization, user=schedule.created_by, status=Membership.Status.ACTIVE)
                class Params:
                    def get(self, key, default=""):
                        return schedule.filters.get(key, default)
                    def getlist(self, key):
                        return []
                job = queue_export(module=schedule.module, file_format=schedule.file_format,
                                   organization=schedule.organization, membership=membership,
                                   actor=schedule.created_by, filters=Params())
                schedule.last_run_at = now
                if schedule.frequency == ScheduledExport.Frequency.DAILY:
                    schedule.next_run_at += timedelta(days=1)
                elif schedule.frequency == ScheduledExport.Frequency.WEEKLY:
                    schedule.next_run_at += timedelta(days=7)
                else:
                    schedule.next_run_at += timedelta(days=30)
                schedule.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
                self.stdout.write(f"Schedule {schedule.pk}: queued {job.pk}")
            except Exception as exc:
                self.stderr.write(f"Schedule {schedule.pk}: {exc}")
