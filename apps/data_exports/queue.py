from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.organizations.models import Branch
from apps.organizations.permissions import accessible_branch_ids

from .formats import build_export_file
from .models import ExportJob
from .services import export_queryset


def queue_export(*, module, file_format, organization, membership, actor, filters):
    if file_format not in {"csv", "xlsx", "pdf"}:
        raise ValueError("Choose CSV, Excel or PDF.")
    export_queryset(
        module=module, organization=organization, membership=membership, params=filters
    )
    branch_scope = None
    if module != "suppliers":
        accessible_ids = accessible_branch_ids(membership)
        branches = Branch.objects.filter(
            organization=organization,
            is_active=True,
            deleted_at__isnull=True,
        )
        if accessible_ids is not None:
            branches = branches.filter(pk__in=accessible_ids)
        selected_branch = filters.get("branch", "").strip()
        if selected_branch:
            branches = branches.filter(pk=selected_branch)
        branch_scope = [str(branch_id) for branch_id in branches.values_list("pk", flat=True)]
    job = ExportJob.objects.create(
        organization=organization,
        requested_by=actor,
        module=module,
        file_format=file_format,
        status=ExportJob.Status.QUEUED,
        filters={
            "branch": filters.get("branch", ""),
            "status": filters.get("status", ""),
            "from": filters.get("from", ""),
            "to": filters.get("to", ""),
            "branch_scope": branch_scope,
        },
        expires_at=timezone.now() + timedelta(days=7),
    )
    record_event(
        actor=actor,
        organization=organization,
        action="export.queued",
        target=job,
        changes={"module": module, "format": file_format},
    )
    return job


def process_export_job(job_id):
    with transaction.atomic():
        job = (
            ExportJob.objects.select_for_update()
            .select_related("organization", "requested_by")
            .get(pk=job_id)
        )
        if job.status != ExportJob.Status.QUEUED:
            return job
        job.status = ExportJob.Status.PROCESSING
        job.save(update_fields=["status", "updated_at"])
    try:
        membership = job.organization.memberships.get(user=job.requested_by, status="active")
        if (
            not isinstance(job.filters, dict)
            or "branch_scope" not in job.filters
            or (job.module != "suppliers" and not isinstance(job.filters["branch_scope"], list))
        ):
            raise ValueError("Export branch scope is missing; queue the export again.")
        queryset = export_queryset(
            module=job.module,
            organization=job.organization,
            membership=membership,
            params=_FilterParams(job.filters),
            branch_scope=job.filters.get("branch_scope"),
        )
        payload, count = build_export_file(
            job.module, queryset, job.file_format, job.organization.name
        )
        extension = job.file_format
        filename = (
            f"{job.organization.slug}-{job.module}-{timezone.now():%Y%m%d-%H%M%S}.{extension}"
        )
        job.file.save(filename, ContentFile(payload), save=False)
        job.record_count = count
        job.file_size = len(payload)
        job.status = ExportJob.Status.COMPLETED
        job.error_message = ""
        job.save()
        record_event(
            actor=job.requested_by,
            organization=job.organization,
            action="export.completed",
            target=job,
            changes={"module": job.module, "format": job.file_format, "record_count": count},
        )
    except Exception as exc:
        job.status = ExportJob.Status.FAILED
        job.error_message = str(exc)[:500]
        job.save(update_fields=["status", "error_message", "updated_at"])
        record_event(
            actor=job.requested_by,
            organization=job.organization,
            action="export.failed",
            target=job,
            changes={"reason": str(exc)[:300]},
        )
    _notify_export_ready(job)
    return job


class _FilterParams:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=""):
        return self.values.get(key, default)

    def getlist(self, key):
        return self.values.get(key, [])


def _notify_export_ready(job):
    if not job.requested_by.email or job.notification_sent_at:
        return
    state = "ready" if job.status == ExportJob.Status.COMPLETED else "failed"
    subject = f"DairyNexus export {state}: {job.get_module_display()}"
    message = (
        f"Your {job.get_module_display()} export is {state}. "
        f"Records: {job.record_count}. "
        f"Sign in to your DairyNexus workspace to view the export centre. "
        f"Files expire after seven days."
    )
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [job.requested_by.email],
            fail_silently=False,
        )
        job.notification_sent_at = timezone.now()
        job.save(update_fields=["notification_sent_at", "updated_at"])
    except Exception:
        # A mail transport outage must not change the export result.
        return
