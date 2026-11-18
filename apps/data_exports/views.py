from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids

from .models import ExportJob, SavedExportTemplate, ScheduledExport, ImportBatch
from .queue import queue_export
from .services import MODULE_ROLES


@login_required
@organization_access()
def export_centre(request, organization_slug):
    membership = request.membership
    allowed = [key for key, roles in MODULE_ROLES.items() if membership.role in roles]
    jobs = ExportJob.objects.filter(organization=request.organization, requested_by=request.user)
    if membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        jobs = ExportJob.objects.filter(organization=request.organization)
    total_exports = jobs.count()
    completed_exports = jobs.filter(status=ExportJob.Status.COMPLETED).count()
    failed_exports = jobs.filter(status=ExportJob.Status.FAILED).count()
    queued_exports = jobs.filter(status__in=[ExportJob.Status.QUEUED, ExportJob.Status.PROCESSING]).count()
    jobs = jobs.select_related("requested_by")[:50]
    branch_ids = accessible_branch_ids(membership)
    branches = request.organization.branches.filter(is_active=True, deleted_at__isnull=True)
    if branch_ids is not None:
        branches = branches.filter(pk__in=branch_ids)
    templates = SavedExportTemplate.objects.filter(organization=request.organization)
    templates = (templates.filter(is_shared=True) | templates.filter(created_by=request.user)).distinct().order_by("name")
    schedules = ScheduledExport.objects.filter(organization=request.organization)
    if membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        schedules = schedules.filter(created_by=request.user)
    imports = ImportBatch.objects.filter(organization=request.organization, uploaded_by=request.user)[:20]
    return render(request, "data_exports/centre.html", {
        "organization": request.organization,
        "allowed_modules": [(key, ExportJob.Module(key).label) for key in allowed],
        "jobs": jobs, "branches": branches.order_by("name"), "templates": templates,
        "schedules": schedules.order_by("next_run_at"), "imports": imports,
        "now": timezone.now(), "total_exports": total_exports,
        "completed_exports": completed_exports, "failed_exports": failed_exports,
        "processing_exports": queued_exports,
    })


@login_required
@organization_access()
@require_POST
def queue_export_view(request, organization_slug, module):
    try:
        job = queue_export(
            module=module, file_format=request.POST.get("file_format", "xlsx").lower(),
            organization=request.organization, membership=request.membership,
            actor=request.user, filters=request.POST,
        )
    except PermissionDenied:
        raise Http404
    except (ValueError, ValidationError) as exc:
        messages.error(request, str(exc))
        return redirect("data_exports:centre", organization_slug=organization_slug)
    messages.success(request, f"Export queued. Job {str(job.pk)[:8]} will appear in Export History.")
    return redirect("data_exports:centre", organization_slug=organization_slug)


@login_required
@organization_access()
def download_export(request, organization_slug, job_id):
    job = get_object_or_404(ExportJob, pk=job_id, organization=request.organization)
    if job.requested_by_id != request.user.pk and request.membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        raise Http404
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None and job.filters.get("branch") and str(job.filters["branch"]) not in {str(value) for value in branch_ids}:
        raise Http404
    if job.status != ExportJob.Status.COMPLETED or job.expires_at <= timezone.now() or not job.file:
        raise Http404
    try:
        stream = job.file.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404
    record_event(actor=request.user, organization=request.organization, action="export.downloaded", target=job, request=request)
    content_types = {"csv": "text/csv; charset=utf-8", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "pdf": "application/pdf"}
    response = FileResponse(stream, as_attachment=True, filename=job.file.name.rsplit("/", 1)[-1], content_type=content_types.get(job.file_format, "application/octet-stream"))
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
