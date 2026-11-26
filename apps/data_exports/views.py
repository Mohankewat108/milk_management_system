from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Branch, Membership
from apps.organizations.permissions import accessible_branch_ids

from .models import ExportJob, ImportBatch, SavedExportTemplate, ScheduledExport
from .queue import queue_export
from .services import MODULE_ROLES, can_export_module


@login_required
@organization_access()
def export_centre(request, organization_slug):
    membership = request.membership
    allowed = [key for key in MODULE_ROLES if can_export_module(membership, key)]
    jobs = ExportJob.objects.filter(organization=request.organization, requested_by=request.user)
    if membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        jobs = ExportJob.objects.filter(organization=request.organization)
    total_exports = jobs.count()
    completed_exports = jobs.filter(status=ExportJob.Status.COMPLETED).count()
    failed_exports = jobs.filter(status=ExportJob.Status.FAILED).count()
    queued_exports = jobs.filter(
        status__in=[ExportJob.Status.QUEUED, ExportJob.Status.PROCESSING]
    ).count()
    jobs = jobs.select_related("requested_by")[:50]
    branch_ids = accessible_branch_ids(membership)
    branches = request.organization.branches.filter(is_active=True, deleted_at__isnull=True)
    if branch_ids is not None:
        branches = branches.filter(pk__in=branch_ids)
    templates = SavedExportTemplate.objects.filter(organization=request.organization)
    if membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        templates = templates.filter(is_shared=True) | templates.filter(created_by=request.user)
    else:
        templates = templates.filter(created_by=request.user)
    templates = templates.distinct().order_by("name")
    schedules = ScheduledExport.objects.filter(organization=request.organization)
    if membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        schedules = schedules.filter(created_by=request.user)
    imports = ImportBatch.objects.filter(
        organization=request.organization, uploaded_by=request.user
    )[:20]
    return render(
        request,
        "data_exports/centre.html",
        {
            "organization": request.organization,
            "allowed_modules": [(key, ExportJob.Module(key).label) for key in allowed],
            "jobs": jobs,
            "branches": branches.order_by("name"),
            "templates": templates,
            "schedules": schedules.order_by("next_run_at"),
            "imports": imports,
            "now": timezone.now(),
            "total_exports": total_exports,
            "completed_exports": completed_exports,
            "failed_exports": failed_exports,
            "processing_exports": queued_exports,
        },
    )


@login_required
@organization_access()
@require_POST
def queue_export_view(request, organization_slug, module):
    try:
        job = queue_export(
            module=module,
            file_format=request.POST.get("file_format", "xlsx").lower(),
            organization=request.organization,
            membership=request.membership,
            actor=request.user,
            filters=request.POST,
        )
    except PermissionDenied as exc:
        raise Http404 from exc
    except (ValueError, ValidationError) as exc:
        messages.error(request, str(exc))
        return redirect("data_exports:centre", organization_slug=organization_slug)
    messages.success(
        request, f"Export queued. Job {str(job.pk)[:8]} will appear in Export History."
    )
    return redirect("data_exports:centre", organization_slug=organization_slug)


@login_required
@organization_access()
def download_export(request, organization_slug, job_id):
    job = get_object_or_404(ExportJob, pk=job_id, organization=request.organization)
    if job.requested_by_id != request.user.pk and request.membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }:
        raise Http404
    if not can_export_module(request.membership, job.module):
        raise Http404
    if job.module == "reports" and not isinstance(job.filters, dict):
        raise Http404
    if job.module == "reports":
        if not isinstance(job.filters, dict) or "branch_scope" not in job.filters:
            raise Http404
    if not isinstance(job.filters, dict) or "branch_scope" not in job.filters:
        raise Http404
    branch_ids = accessible_branch_ids(request.membership)
    if job.module != "suppliers":
        branch_scope = job.filters["branch_scope"]
        if not isinstance(branch_scope, list) or any(
            value is not None and not isinstance(value, str) for value in branch_scope
        ):
            raise Http404
        if branch_ids is not None:
            scope_ids = {value for value in branch_scope if value is not None}
            current_branch_ids = set(
                str(value)
                for value in Branch.objects.filter(
                    organization=request.organization,
                    pk__in=branch_ids,
                    is_active=True,
                    deleted_at__isnull=True,
                ).values_list("pk", flat=True)
            )
            if None in branch_scope or not scope_ids.issubset(current_branch_ids):
                raise Http404
    if job.status != ExportJob.Status.COMPLETED or job.expires_at <= timezone.now() or not job.file:
        raise Http404
    try:
        stream = job.file.open("rb")
    except (FileNotFoundError, OSError) as exc:
        raise Http404 from exc
    record_event(
        actor=request.user,
        organization=request.organization,
        action="export.downloaded",
        target=job,
        request=request,
    )
    content_types = {
        "csv": "text/csv; charset=utf-8",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    response = FileResponse(
        stream,
        as_attachment=True,
        filename=job.file.name.rsplit("/", 1)[-1],
        content_type=content_types.get(job.file_format, "application/octet-stream"),
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@organization_access()
@require_POST
def retry_export(request, organization_slug, job_id):
    job = get_object_or_404(ExportJob, pk=job_id, organization=request.organization)
    if job.requested_by_id != request.user.pk and request.membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }:
        raise Http404
    if not can_export_module(request.membership, job.module):
        raise Http404
    if job.status != ExportJob.Status.FAILED:
        messages.error(request, "Only failed exports can be retried.")
    else:
        if job.file:
            job.file.delete(save=False)
        job.file = ""
        job.file_size = 0
        job.record_count = 0
        job.error_message = ""
        job.status = ExportJob.Status.QUEUED
        job.save(
            update_fields=[
                "file",
                "file_size",
                "record_count",
                "error_message",
                "status",
                "updated_at",
            ]
        )
        record_event(
            actor=request.user,
            organization=request.organization,
            action="export.retried",
            target=job,
            request=request,
        )
        messages.success(request, "Export queued for retry.")
    return redirect("data_exports:centre", organization_slug=organization_slug)


@login_required
@organization_access()
@require_POST
def cancel_export(request, organization_slug, job_id):
    job = get_object_or_404(ExportJob, pk=job_id, organization=request.organization)
    if job.requested_by_id != request.user.pk and request.membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }:
        raise Http404
    if job.status != ExportJob.Status.QUEUED:
        messages.error(request, "Only queued exports can be cancelled.")
    else:
        job.status = ExportJob.Status.CANCELLED
        job.error_message = "Cancelled by user."
        job.save(update_fields=["status", "error_message", "updated_at"])
        record_event(
            actor=request.user,
            organization=request.organization,
            action="export.cancelled",
            target=job,
            request=request,
        )
        messages.success(request, "Export cancelled.")
    return redirect("data_exports:centre", organization_slug=organization_slug)


@login_required
@organization_access()
@require_POST
def delete_export(request, organization_slug, job_id):
    job = get_object_or_404(ExportJob, pk=job_id, organization=request.organization)
    if job.requested_by_id != request.user.pk and request.membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }:
        raise Http404
    if job.status in {ExportJob.Status.QUEUED, ExportJob.Status.PROCESSING}:
        messages.error(request, "Cancel or wait for this export before deleting it.")
    else:
        if job.file:
            job.file.delete(save=False)
        record_event(
            actor=request.user,
            organization=request.organization,
            action="export.deleted",
            target=job,
            request=request,
        )
        job.delete()
        messages.success(request, "Export history entry deleted.")
    return redirect("data_exports:centre", organization_slug=organization_slug)
