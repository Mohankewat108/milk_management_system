from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids, can_access_branch

from .forms import CustomerForm, FarmerForm
from .models import Customer, Farmer


MANAGERS = (Membership.Role.OWNER, Membership.Role.ADMIN)


def _party_model(kind):
    return Customer if kind == "customer" else Farmer


def _party_form(kind):
    return CustomerForm if kind == "customer" else FarmerForm


def _detail_name(kind):
    return f"parties:{kind}_detail"


def _list_name(kind):
    return f"parties:{'customers' if kind == 'customer' else 'farmers'}"


@login_required
@organization_access(*MANAGERS)
@require_http_methods(["GET", "POST"])
def party_edit(request, organization_slug, kind, party_id):
    model = _party_model(kind)
    party = get_object_or_404(model.objects.filter(
        organization=request.organization, deleted_at__isnull=True
    ), pk=party_id)
    form_class = _party_form(kind)
    form = form_class(request.POST or None, instance=party,
                      organization=request.organization, membership=request.membership)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        branch = form.cleaned_data.get("branch")
        if branch and not can_access_branch(request.membership, branch):
            form.add_error("branch", "You cannot assign this record to that branch.")
        else:
            updated.save()
            record_event(
                actor=request.user, organization=request.organization,
                action=f"{kind}.updated", target=updated,
                changes={"updated_fields": list(form.changed_data)}, request=request,
            )
            messages.success(request, f"{kind.title()} profile updated successfully.")
            return redirect(_detail_name(kind), organization_slug=organization_slug,
                            **{f"{kind}_id": party.pk})
    return render(request, f"parties/{kind}_form.html", {
        "organization": request.organization, "form": form, "party": party,
        "is_edit": True,
    })


@login_required
@organization_access(*MANAGERS)
@require_POST
def party_trash(request, organization_slug, kind, party_id):
    model = _party_model(kind)
    party = get_object_or_404(
        model.objects.filter(organization=request.organization, deleted_at__isnull=True),
        pk=party_id,
    )
    party.deleted_at = timezone.now()
    party.deleted_by = request.user
    party.save(update_fields=["deleted_at", "deleted_by", "updated_at"])
    record_event(actor=request.user, organization=request.organization,
                 action=f"{kind}.moved_to_trash", target=party, request=request)
    messages.success(request, f"{kind.title()} moved to Trash. Its operational history has been retained.")
    return redirect(_list_name(kind), organization_slug=organization_slug)


@login_required
@organization_access(*MANAGERS)
def party_trash_list(request, organization_slug):
    kind = request.GET.get("kind", "customer")
    if kind not in {"customer", "farmer"}:
        kind = "customer"
    model = _party_model(kind)
    branch_ids = accessible_branch_ids(request.membership)
    records = model.objects.filter(
        organization=request.organization, deleted_at__isnull=False
    ).select_related("branch", "deleted_by").order_by("-deleted_at")
    if branch_ids is not None:
        records = records.filter(branch_id__in=branch_ids)
    return render(request, "parties/trash.html", {
        "organization": request.organization, "records": records,
        "kind": kind,
    })


@login_required
@organization_access(*MANAGERS)
@require_POST
def party_restore(request, organization_slug, kind, party_id):
    model = _party_model(kind)
    party = get_object_or_404(
        model.objects.filter(organization=request.organization, deleted_at__isnull=False),
        pk=party_id,
    )
    party.deleted_at = None
    party.deleted_by = None
    party.save(update_fields=["deleted_at", "deleted_by", "updated_at"])
    record_event(actor=request.user, organization=request.organization,
                 action=f"{kind}.restored", target=party, request=request)
    messages.success(request, f"{kind.title()} restored successfully.")
    return redirect("parties:trash", organization_slug=organization_slug)
