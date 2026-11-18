from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids, can_access_branch

from .forms import CollectionEditForm, CollectionEntryForm
from .models import MilkCollection
from .services import create_collection


@login_required
@organization_access(
    Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER,
    Membership.Role.COLLECTION_OPERATOR, Membership.Role.QUALITY_OFFICER,
)
def collection_list(request, organization_slug):
    organization = request.organization
    records = MilkCollection.objects.filter(organization=organization).select_related(
        "branch", "farmer", "customer", "recorded_by"
    ).order_by("-collected_at")
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None:
        records = records.filter(branch_id__in=branch_ids)
    start, end = request.GET.get("from"), request.GET.get("to")
    if start:
        records = records.filter(collected_at__date__gte=start)
    if end:
        records = records.filter(collected_at__date__lte=end)
    total_litres = records.exclude(status=MilkCollection.Status.REVERSED).aggregate(value=Sum("quantity_litres"))["value"] or 0
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(request, "collections/list.html", {
        "organization": organization, "page_obj": page, "total_litres": total_litres,
        "membership": request.membership,
    })


@login_required
@organization_access(
    Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER,
    Membership.Role.COLLECTION_OPERATOR,
)
@require_http_methods(["GET", "POST"])
def collection_create(request, organization_slug):
    organization = request.organization
    form = CollectionEntryForm(request.POST or None, organization=organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if not can_access_branch(request.membership, data["branch"]):
            form.add_error("branch", "You are not assigned to this branch.")
        else:
            try:
                entry = create_collection(
                    organization=organization, branch=data["branch"], actor=request.user,
                    collected_at=data["collected_at"], quantity_litres=data["quantity_litres"],
                    snf=data["snf"], fat=data["fat"], lactose=data["lactose"],
                    farmer=data["farmer"], customer=data["customer"], notes=data["notes"],
                    lactometer_reading=data.get("lactometer_reading"),
                    milk_temperature_c=data.get("milk_temperature_c"),
                    sample_reference=data.get("sample_reference", ""),
                    quality_test_method=data.get("quality_test_method", ""),
                    tested_by=request.user,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                record_event(actor=request.user, organization=organization,
                             action="milk_collection.created", target=entry, request=request)
                messages.success(request, f"Collection {entry.reference} recorded.")
                return redirect("collections:list", organization_slug=organization_slug)
    return render(request, "collections/form.html", {"organization": organization, "form": form})


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.QUALITY_OFFICER)
@require_POST
def approve_collection(request, organization_slug, collection_id):
    with transaction.atomic():
        entry = MilkCollection.objects.select_for_update().get(
            pk=collection_id, organization=request.organization
        )
        if entry.status != MilkCollection.Status.SUBMITTED:
            messages.error(request, "Only submitted collections can be approved.")
        else:
            entry.status = MilkCollection.Status.APPROVED
            entry.save(update_fields=["status", "updated_at"])
            record_event(actor=request.user, organization=request.organization,
                         action="milk_collection.approved", target=entry, request=request)
            messages.success(request, "Collection approved.")
    return redirect("collections:list", organization_slug=organization_slug)


@login_required
@organization_access(
    Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER,
    Membership.Role.COLLECTION_OPERATOR, Membership.Role.QUALITY_OFFICER,
)
@require_http_methods(["GET", "POST"])
def collection_edit(request, organization_slug, collection_id):
    organization = request.organization
    branch_ids = accessible_branch_ids(request.membership)
    with transaction.atomic():
        records = MilkCollection.objects.filter(organization=organization)
        if branch_ids is not None:
            records = records.filter(branch_id__in=branch_ids)
        if request.method == "POST":
            records = records.select_for_update()
        entry = records.get(pk=collection_id)
        if entry.status in {MilkCollection.Status.REVERSED, MilkCollection.Status.APPROVED}:
            messages.error(request, "Approved or reversed collections cannot be edited; reverse an approved record with a reason.")
            return redirect("collections:list", organization_slug=organization_slug)
        form = CollectionEditForm(request.POST or None, instance=entry)
        if request.method == "POST" and form.is_valid():
            data = form.cleaned_data
            before = {
                "quantity_litres": str(entry.quantity_litres),
                "snf": str(entry.snf), "fat": str(entry.fat),
                "lactose": str(entry.lactose), "milk_rate": str(entry.milk_rate), "total_amount": str(entry.total_amount),
            }
            from decimal import Decimal, ROUND_HALF_UP
            entry.quantity_litres = data["quantity_litres"]
            entry.snf = data["snf"]
            entry.fat = data["fat"]
            entry.lactose = data["lactose"]
            entry.lactometer_reading = data.get("lactometer_reading")
            entry.milk_temperature_c = data.get("milk_temperature_c")
            entry.sample_reference = data.get("sample_reference", "")
            entry.quality_test_method = data.get("quality_test_method", "")
            entry.notes = data.get("notes", "")
            # Do not silently apply a newer tariff: keep this record's rate snapshot.
            snapshot = entry.pricing_snapshot or {}
            if all(key in snapshot for key in ("snf_rate", "fat_rate", "lactose_rate")):
                entry.milk_rate = (
                    entry.snf * Decimal(snapshot["snf_rate"])
                    + entry.fat * Decimal(snapshot["fat_rate"])
                    + entry.lactose * Decimal(snapshot["lactose_rate"])
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            entry.total_amount = (
                entry.quantity_litres * entry.milk_rate
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            entry.save(update_fields=[
                "quantity_litres", "snf", "fat", "lactose", "milk_rate",
                "lactometer_reading", "milk_temperature_c", "sample_reference",
                "quality_test_method", "notes", "total_amount", "updated_at",
            ])
            after = {
                "quantity_litres": str(entry.quantity_litres),
                "snf": str(entry.snf), "fat": str(entry.fat),
                "lactose": str(entry.lactose), "total_amount": str(entry.total_amount),
            }
            record_event(
                actor=request.user, organization=organization,
                action="milk_collection.updated", target=entry,
                changes={"before": before, "after": after}, request=request,
            )
            messages.success(request, f"Collection {entry.reference} updated.")
            return redirect("collections:list", organization_slug=organization_slug)
    return render(request, "collections/edit.html", {
        "organization": organization, "entry": entry, "form": form,
    })


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN)
@require_POST
def collection_reverse(request, organization_slug, collection_id):
    reason = request.POST.get("reason", "").strip()
    if len(reason) < 8:
        messages.error(request, "Provide a clear reversal reason (at least 8 characters).")
        return redirect("collections:list", organization_slug=organization_slug)
    with transaction.atomic():
        entry = MilkCollection.objects.select_for_update().get(
            pk=collection_id, organization=request.organization
        )
        if entry.status == MilkCollection.Status.REVERSED:
            messages.info(request, "This collection has already been reversed.")
        else:
            old_status = entry.status
            entry.status = MilkCollection.Status.REVERSED
            entry.notes = (entry.notes + "\\n" if entry.notes else "") + f"REVERSAL: {reason}"
            entry.save(update_fields=["status", "notes", "updated_at"])
            record_event(
                actor=request.user, organization=request.organization,
                action="milk_collection.reversed", target=entry,
                changes={"from_status": old_status, "to_status": entry.status, "reason": reason},
                request=request,
            )
            messages.success(request, f"Collection {entry.reference} reversed. Its audit history remains available.")
    return redirect("collections:list", organization_slug=organization_slug)
