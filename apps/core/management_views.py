from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids

from .soft_delete import MODEL_REGISTRY, display_record, get_registered_model, restore_record, soft_delete_record


MANAGERS = (Membership.Role.OWNER, Membership.Role.ADMIN)


@login_required
@organization_access(*MANAGERS)
def trash_list(request, organization_slug):
    selected = request.GET.get("type", "all")
    records = []
    branch_ids = accessible_branch_ids(request.membership)
    for key, (model, label) in MODEL_REGISTRY.items():
        if selected not in {"all", key}:
            continue
        queryset = model.objects.filter(
            organization=request.organization, deleted_at__isnull=False
        ).select_related("deleted_by")
        if branch_ids is not None and key != "branch" and hasattr(model, "branch"):
            queryset = queryset.filter(branch_id__in=branch_ids)
        for obj in queryset.order_by("-deleted_at"):
            records.append({"key": key, "label": label, "object": obj, "display": display_record(obj)})
    records.sort(key=lambda item: item["object"].deleted_at, reverse=True)
    return render(request, "organizations/trash.html", {
        "organization": request.organization, "records": records,
        "selected_type": selected,
        "types": [(key, label) for key, (_, label) in MODEL_REGISTRY.items()],
    })


@login_required
@organization_access(*MANAGERS)
@require_POST
def trash_delete(request, organization_slug, model_key, object_id):
    model = get_registered_model(model_key)
    branch_ids = accessible_branch_ids(request.membership)
    try:
        with transaction.atomic():
            queryset = model.objects.filter(
                organization=request.organization, deleted_at__isnull=True
            )
            if branch_ids is not None and hasattr(model, "branch"):
                queryset = queryset.filter(branch_id__in=branch_ids)
            record = get_object_or_404(queryset.select_for_update(), pk=object_id)
            soft_delete_record(key=model_key, record=record, actor=request.user)
            record_event(
                actor=request.user, organization=request.organization,
                action=f"{model_key}.moved_to_trash", target=record, request=request,
            )
    except ValidationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{display_record(record)} moved to Trash. Its history has been retained.")
    return redirect("business:trash", organization_slug=organization_slug)


@login_required
@organization_access(*MANAGERS)
@require_POST
def trash_restore(request, organization_slug, model_key, object_id):
    model = get_registered_model(model_key)
    branch_ids = accessible_branch_ids(request.membership)
    try:
        with transaction.atomic():
            queryset = model.objects.filter(
                organization=request.organization, deleted_at__isnull=False
            )
            if branch_ids is not None and hasattr(model, "branch"):
                queryset = queryset.filter(branch_id__in=branch_ids)
            record = get_object_or_404(queryset.select_for_update(), pk=object_id)
            restore_record(record=record)
            record_event(
                actor=request.user, organization=request.organization,
                action=f"{model_key}.restored", target=record, request=request,
            )
    except ValidationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{display_record(record)} restored successfully.")
    return redirect("business:trash", organization_slug=organization_slug)
