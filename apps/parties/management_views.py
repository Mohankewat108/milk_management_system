from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids, can_access_branch

from .forms import CustomerForm, FarmerForm
from .models import Customer, Farmer, FarmerNfcCard

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
    party = get_object_or_404(
        model.objects.filter(organization=request.organization, deleted_at__isnull=True),
        pk=party_id,
    )
    form_class = _party_form(kind)
    form = form_class(
        request.POST or None,
        instance=party,
        organization=request.organization,
        membership=request.membership,
    )
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        branch = form.cleaned_data.get("branch")
        if branch and not can_access_branch(request.membership, branch):
            form.add_error("branch", "You cannot assign this record to that branch.")
        else:
            updated.save()
            record_event(
                actor=request.user,
                organization=request.organization,
                action=f"{kind}.updated",
                target=updated,
                changes={"updated_fields": list(form.changed_data)},
                request=request,
            )
            messages.success(request, f"{kind.title()} profile updated successfully.")
            return redirect(
                _detail_name(kind), organization_slug=organization_slug, **{f"{kind}_id": party.pk}
            )
    return render(
        request,
        f"parties/{kind}_form.html",
        {
            "organization": request.organization,
            "form": form,
            "party": party,
            "is_edit": True,
        },
    )


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
    record_event(
        actor=request.user,
        organization=request.organization,
        action=f"{kind}.moved_to_trash",
        target=party,
        request=request,
    )
    messages.success(
        request, f"{kind.title()} moved to Trash. Its operational history has been retained."
    )
    return redirect(_list_name(kind), organization_slug=organization_slug)


@login_required
@organization_access(*MANAGERS)
def party_trash_list(request, organization_slug):
    kind = request.GET.get("kind", "customer")
    if kind not in {"customer", "farmer"}:
        kind = "customer"
    model = _party_model(kind)
    branch_ids = accessible_branch_ids(request.membership)
    records = (
        model.objects.filter(organization=request.organization, deleted_at__isnull=False)
        .select_related("branch", "deleted_by")
        .order_by("-deleted_at")
    )
    if branch_ids is not None:
        records = records.filter(branch_id__in=branch_ids)
    return render(
        request,
        "parties/trash.html",
        {
            "organization": request.organization,
            "records": records,
            "kind": kind,
        },
    )


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
    record_event(
        actor=request.user,
        organization=request.organization,
        action=f"{kind}.restored",
        target=party,
        request=request,
    )
    messages.success(request, f"{kind.title()} restored successfully.")
    return redirect("parties:trash", organization_slug=organization_slug)


@login_required
@organization_access(*MANAGERS)
@require_POST
def farmer_nfc_card_add(request, organization_slug, farmer_id):
    farmer = get_object_or_404(
        Farmer.objects.filter(organization=request.organization, deleted_at__isnull=True),
        pk=farmer_id,
    )
    uid = request.POST.get("card_uid", "").strip().upper()
    if not uid:
        messages.error(request, "Enter an NFC card UID.")
    elif FarmerNfcCard.objects.filter(card_uid=uid).exists():
        messages.error(
            request,
            "This NFC card is already assigned. Each card UID can belong to only one farmer.",
        )
    else:
        FarmerNfcCard.objects.create(farmer=farmer, card_uid=uid)
        record_event(
            actor=request.user,
            organization=request.organization,
            action="farmer.nfc_card_added",
            target=farmer,
            request=request,
        )
        messages.success(request, "NFC card linked to farmer.")
    return redirect(
        "parties:farmer_detail", organization_slug=organization_slug, farmer_id=farmer.pk
    )


@login_required
@organization_access(*MANAGERS)
@require_POST
def farmer_nfc_card_revoke(request, organization_slug, farmer_id, card_id):
    farmer = get_object_or_404(
        Farmer.objects.filter(organization=request.organization, deleted_at__isnull=True),
        pk=farmer_id,
    )
    card = get_object_or_404(FarmerNfcCard.objects.filter(farmer=farmer), pk=card_id)
    if card.status != FarmerNfcCard.Status.REVOKED:
        card.status = FarmerNfcCard.Status.REVOKED
        card.revoked_at = timezone.now()
        card.save(update_fields=["status", "revoked_at", "updated_at"])
        record_event(
            actor=request.user,
            organization=request.organization,
            action="farmer.nfc_card_revoked",
            target=farmer,
            request=request,
        )
        messages.success(request, "NFC card revoked.")
    return redirect(
        "parties:farmer_detail", organization_slug=organization_slug, farmer_id=farmer.pk
    )


@login_required
@organization_access(*MANAGERS)
def farmer_qr_card(request, organization_slug, farmer_id):
    farmer = get_object_or_404(
        Farmer.objects.filter(organization=request.organization, deleted_at__isnull=True),
        pk=farmer_id,
    )
    from io import BytesIO

    import qrcode

    payload = f"DNX-FARMER:{farmer.qr_token}"
    image = qrcode.make(payload)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="farmer-{farmer.code}-qr.png"'
    return response
