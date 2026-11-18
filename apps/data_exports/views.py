from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db.models import Count, Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids

from .models import ExportJob
from .services import MODULE_ROLES, build_csv, export_queryset


@login_required
@organization_access()
def export_centre(request, organization_slug):
    membership = request.membership
    allowed = [key for key, roles in MODULE_ROLES.items() if membership.role in roles]
    jobs = ExportJob.objects.filter(organization=request.organization, requested_by=request.user)
    if membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        jobs = ExportJob.objects.filter(organization=request.organization)
    jobs = jobs.select_related("requested_by")[:50]
    context = {
        "organization": request.organization,
        "allowed_modules": [(key, ExportJob.Module(key).label) for key in allowed],
        "jobs": jobs,
        "total_exports": jobs.count(),
        "completed_exports": jobs.filter(status=ExportJob.Status.COMPLETED).count(),
        "failed_exports": jobs.filter(status=ExportJob.Status.FAILED).count(),
        "processing_exports": 0,
        "scheduled_exports": 0,
    }
    return render(request, "data_exports/centre.html", context)


@login_required
@organization_access()
@require_POST
def export_csv(request, organization_slug, module):
    params = request.POST
    try:
        queryset = export_queryset(module=module, organization=request.organization,
                                   membership=request.membership, params=params)
        csv_text, record_count = build_csv(module, queryset)
    except (PermissionDenied, ValidationError) as exc:
        if isinstance(exc, PermissionDenied):
            raise Http404
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
        return redirect("business:exports", organization_slug=organization_slug)

    filename = f"{request.organization.slug}-{module}-{timezone.now():%Y%m%d-%H%M%S}.csv"
    job = ExportJob(organization=request.organization, requested_by=request.user,
                    module=module, file_format="csv", record_count=record_count,
                    file_size=len(csv_text.encode("utf-8")), filters={
                        "branch": params.get("branch", ""), "status": params.get("status", ""),
                        "from": params.get("from", ""), "to": params.get("to", ""),
                        "scope": "selected" if params.getlist("selected") else "filtered_or_all",
                    }, expires_at=timezone.now() + timedelta(days=7))
    job.file.save(filename, ContentFile(csv_text.encode("utf-8")), save=True)
    record_event(actor=request.user, organization=request.organization, action="export.created",
                 target=job, changes={"module": module, "format": "csv", "record_count": record_count}, request=request)
    messages.success(request, f"Export ready: {record_count:,} records.")
    return redirect("data_exports:download", organization_slug=organization_slug, job_id=job.pk)


@login_required
@organization_access()
def download_export(request, organization_slug, job_id):
    job = get_object_or_404(ExportJob, pk=job_id, organization=request.organization)
    if job.requested_by_id != request.user.pk and request.membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        raise Http404
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None and job.filters.get("branch") and str(job.filters["branch"]) not in {str(value) for value in branch_ids}:
        raise Http404
    if job.expires_at <= timezone.now() or not job.file:
        raise Http404
    try:
        stream = job.file.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404
    record_event(actor=request.user, organization=request.organization, action="export.downloaded",
                 target=job, request=request)
    response = FileResponse(stream, as_attachment=True, filename=job.file.name.rsplit("/", 1)[-1], content_type="text/csv; charset=utf-8")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
