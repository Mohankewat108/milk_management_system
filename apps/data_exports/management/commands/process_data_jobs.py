import calendar
import csv
import io
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.services import record_event
from apps.data_exports.models import ExportJob, ImportBatch, ScheduledExport
from apps.data_exports.queue import _notify_export_ready, process_export_job, queue_export
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
                if len(row.get("phone", "")) > 30 or len(row.get("email", "")) > 254:
                    raise ValueError("phone or email exceeds the allowed length")
                branch = None
                branch_code = row.get("branch_code", "")
                if branch_code:
                    branch = batch.organization.branches.get(
                        code=branch_code, deleted_at__isnull=True, is_active=True
                    )
                values = {
                    "organization": batch.organization,
                    "code": code,
                    "full_name": name,
                    "phone": row.get("phone", "")[:30],
                    "email": row.get("email", ""),
                    "address": row.get("address", ""),
                }
                if branch:
                    values["branch"] = branch
                if model.objects.filter(organization=batch.organization, code=code).exists():
                    raise ValueError("duplicate code already exists in this organisation")
                instance = model(**values)
                instance.full_clean()
                instance.save()
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
    batch.save(
        update_fields=[
            "total_rows",
            "imported_rows",
            "failed_rows",
            "row_errors",
            "status",
            "processed_at",
            "updated_at",
        ]
    )
    record_event(
        actor=batch.uploaded_by,
        organization=batch.organization,
        action="import.completed"
        if batch.status == ImportBatch.Status.COMPLETED
        else "import.failed",
        target=batch,
        changes={"imported_rows": batch.imported_rows, "failed_rows": batch.failed_rows},
    )
    if batch.uploaded_by.email:
        send_mail(
            f"DairyNexus import {batch.status}: {batch.get_module_display()}",
            f"Imported: {batch.imported_rows}; failed rows: {batch.failed_rows}. Review Import Centre for row-level errors.",
            settings.DEFAULT_FROM_EMAIL,
            [batch.uploaded_by.email],
            fail_silently=True,
        )
    return batch


class Command(BaseCommand):
    help = (
        "Process queued exports, CSV imports and due scheduled exports. Run from cron or a worker."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 100))
        for job in ExportJob.objects.filter(status=ExportJob.Status.QUEUED).order_by("created_at")[
            :limit
        ]:
            process_export_job(job.pk)
            self.stdout.write(f"Export {job.pk}: processed")
        remaining = max(
            0, limit - ExportJob.objects.filter(status=ExportJob.Status.PROCESSING).count()
        )
        for batch in ImportBatch.objects.filter(status=ImportBatch.Status.UPLOADED).order_by(
            "created_at"
        )[:remaining]:
            process_import_batch(batch)
            self.stdout.write(
                f"Import {batch.pk}: {batch.status} ({batch.imported_rows} imported, {batch.failed_rows} failed)"
            )
        for pending_notice in ExportJob.objects.filter(
            status__in=[ExportJob.Status.COMPLETED, ExportJob.Status.FAILED],
            notification_sent_at__isnull=True,
        ).select_related("requested_by")[:limit]:
            _notify_export_ready(pending_notice)
        now = timezone.now()
        for old_import in ImportBatch.objects.filter(created_at__lte=now - timedelta(days=30)):
            if old_import.file:
                old_import.file.delete(save=False)
                old_import.file = ""
                old_import.save(update_fields=["file", "updated_at"])
        for expired in ExportJob.objects.filter(expires_at__lte=now).exclude(
            status=ExportJob.Status.EXPIRED
        ):
            if expired.file:
                expired.file.delete(save=False)
            expired.status = ExportJob.Status.EXPIRED
            expired.save(update_fields=["status", "updated_at"])
        for schedule in ScheduledExport.objects.filter(
            is_active=True, next_run_at__lte=now
        ).select_related("organization", "created_by")[:limit]:
            try:
                membership = Membership.objects.get(
                    organization=schedule.organization,
                    user=schedule.created_by,
                    status=Membership.Status.ACTIVE,
                )

                class Params:
                    def get(self, key, default=""):
                        return schedule.filters.get(key, default)

                    def getlist(self, key):
                        return []

                job = queue_export(
                    module=schedule.module,
                    file_format=schedule.file_format,
                    organization=schedule.organization,
                    membership=membership,
                    actor=schedule.created_by,
                    filters=Params(),
                )
                schedule.last_run_at = now
                if schedule.frequency == ScheduledExport.Frequency.DAILY:
                    schedule.next_run_at += timedelta(days=1)
                elif schedule.frequency == ScheduledExport.Frequency.WEEKLY:
                    schedule.next_run_at += timedelta(days=7)
                else:
                    current = schedule.next_run_at
                    year = current.year + (1 if current.month == 12 else 0)
                    month = 1 if current.month == 12 else current.month + 1
                    day = min(current.day, calendar.monthrange(year, month)[1])
                    schedule.next_run_at = current.replace(year=year, month=month, day=day)
                schedule.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
                self.stdout.write(f"Schedule {schedule.pk}: queued {job.pk}")
            except Exception as exc:
                self.stderr.write(f"Schedule {schedule.pk}: {exc}")
