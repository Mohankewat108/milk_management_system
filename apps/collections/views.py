from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.core.nepali_dates import format_local_date, parse_local_date
from apps.organizations.decorators import organization_access
from apps.organizations.models import Branch, Membership
from apps.organizations.permissions import (
    accessible_branch_ids,
    can_access_branch,
    has_organization_permission,
)

from .forms import CollectionEditForm, CollectionEntryForm
from .models import MilkCollection
from .services import approve_collection as approve_collection_service
from .services import create_collection
from .services import reverse_collection as reverse_collection_service


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.DAIRY_MANAGER,
    Membership.Role.BRANCH_MANAGER,
    Membership.Role.COLLECTION_OPERATOR,
    Membership.Role.QUALITY_OFFICER,
    permission="collections.view",
)
def collection_list(request, organization_slug):
    organization = request.organization
    creator_roles = {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.BRANCH_MANAGER,
        Membership.Role.COLLECTION_OPERATOR,
    }
    can_create = request.membership.role in creator_roles or (
        request.membership.role == Membership.Role.DAIRY_MANAGER
        and has_organization_permission(request.membership, "collections.create")
    )
    collection_form = (
        CollectionEntryForm(
            request.POST or None, organization=organization, membership=request.membership
        )
        if can_create
        else None
    )
    if request.method == "POST" and not can_create:
        return HttpResponseForbidden("You are not authorised to record collections.")
    if request.method == "POST" and collection_form.is_valid():
        data = collection_form.cleaned_data
        if not can_access_branch(request.membership, data["branch"]):
            collection_form.add_error("branch", "You are not assigned to this branch.")
        else:
            try:
                entry = create_collection(
                    organization=organization,
                    branch=data["branch"],
                    actor=request.user,
                    collected_at=data["collected_at"],
                    quantity_litres=data["quantity_litres"],
                    snf=data["snf"],
                    fat=data["fat"],
                    lactose=data["lactose"],
                    farmer=data["farmer"],
                    customer=data["customer"],
                    notes=data["notes"],
                    lactometer_reading=data.get("lactometer_reading"),
                    milk_temperature_c=data.get("milk_temperature_c"),
                    sample_reference=data.get("sample_reference", ""),
                    quality_test_method=data.get("quality_test_method", ""),
                    tested_by=request.user,
                    idempotency_key=data["idempotency_key"],
                )
            except ValidationError as exc:
                collection_form.add_error(None, exc)
            else:
                record_event(
                    actor=request.user,
                    organization=organization,
                    action="milk_collection.created",
                    target=entry,
                    request=request,
                )
                messages.success(request, f"Collection {entry.reference} recorded.")
                return redirect("collections:list", organization_slug=organization_slug)
    records = (
        MilkCollection.objects.filter(organization=organization)
        .select_related("branch", "farmer", "customer", "recorded_by")
        .order_by("-collected_at")
    )
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None:
        records = records.filter(branch_id__in=branch_ids)

    selected_branch = request.GET.get("branch", "").strip()
    if selected_branch:
        try:
            selected_branch = str(UUID(selected_branch))
        except (ValueError, AttributeError):
            selected_branch = ""
        if selected_branch and (
            branch_ids is None or selected_branch in {str(value) for value in branch_ids}
        ):
            records = records.filter(branch_id=selected_branch)
        else:
            selected_branch = ""
    party_filter = request.GET.get("party", "").strip()
    if party_filter:
        records = records.filter(
            Q(farmer__full_name__icontains=party_filter)
            | Q(customer__full_name__icontains=party_filter)
        )

    start_text = request.GET.get("from", "").strip()
    end_text = request.GET.get("to", "").strip()
    query = request.GET.get("q", "").strip()[:100]
    status_filter = request.GET.get("status", "").strip()
    language_code = getattr(request, "LANGUAGE_CODE", "en")
    date_error = ""
    try:
        start = parse_local_date(start_text, language_code)
        end = parse_local_date(end_text, language_code)
    except ValueError as exc:
        start = end = None
        date_error = str(exc)
    if start and end and start > end:
        date_error = "The start date must be on or before the end date."
        start = end = None
    if start:
        records = records.filter(collected_at__date__gte=start)
    if end:
        records = records.filter(collected_at__date__lte=end)
    if query:
        records = records.filter(
            Q(reference__icontains=query)
            | Q(branch__name__icontains=query)
            | Q(farmer__full_name__icontains=query)
            | Q(customer__full_name__icontains=query)
        )
    status_scope_records = records
    valid_statuses = {value for value, _label in MilkCollection.Status.choices}
    if status_filter in valid_statuses:
        records = records.filter(status=status_filter)

    active_records = records.exclude(status=MilkCollection.Status.REVERSED)
    summary = active_records.aggregate(
        litres=Sum("quantity_litres"),
        value=Sum("total_amount"),
        count=Count("id"),
        weighted_fat=Sum(F("quantity_litres") * F("fat")),
        weighted_snf=Sum(F("quantity_litres") * F("snf")),
    )
    total_litres = summary["litres"] or 0
    weighted_fat = summary["weighted_fat"] / total_litres if total_litres else None
    weighted_snf = summary["weighted_snf"] / total_litres if total_litres else None
    status_counts = status_scope_records.aggregate(
        submitted=Count("id", filter=Q(status=MilkCollection.Status.SUBMITTED)),
        approved=Count("id", filter=Q(status=MilkCollection.Status.APPROVED)),
        rejected=Count("id", filter=Q(status=MilkCollection.Status.REJECTED)),
        reversed=Count("id", filter=Q(status=MilkCollection.Status.REVERSED)),
    )
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    filter_querystring = request.GET.copy()
    filter_querystring.pop("page", None)
    filter_branches = Branch.objects.filter(
        organization=organization,
        is_active=True,
        deleted_at__isnull=True,
        **({"pk__in": branch_ids} if branch_ids is not None else {}),
    ).order_by("name")
    branch_context = "All branches"
    if branch_ids is not None:
        assigned_count = filter_branches.count()
        branch_context = (
            f"{assigned_count} assigned branches"
            if assigned_count != 1
            else filter_branches.first().name
        )
    if selected_branch:
        branch_context = filter_branches.filter(pk=selected_branch).values_list(
            "name", flat=True
        ).first() or branch_context
    return render(
        request,
        "collections/list.html",
        {
            "organization": organization,
            "page_obj": page,
            "total_litres": total_litres,
            "total_value": summary["value"] or 0,
            "total_records": summary["count"] or 0,
            "weighted_fat": weighted_fat,
            "weighted_snf": weighted_snf,
            "status_counts": status_counts,
            "membership": request.membership,
            "date_from": format_local_date(start, language_code) if start else start_text,
            "date_to": format_local_date(end, language_code) if end else end_text,
            "date_error": date_error,
            "date_calendar": "BS" if language_code == "ne" else "AD",
            "search_query": query,
            "status_filter": status_filter,
            "branch_filter": selected_branch,
            "party_filter": party_filter,
            "filter_branches": filter_branches,
            "branch_context": branch_context,
            "can_create_collection": can_create,
            "can_approve_collection": request.membership.role in {
                Membership.Role.OWNER,
                Membership.Role.ADMIN,
                Membership.Role.QUALITY_OFFICER,
            } or (
                request.membership.role == Membership.Role.DAIRY_MANAGER
                and has_organization_permission(request.membership, "collections.approve")
            ),
            "filter_querystring": filter_querystring.urlencode(),
            "status_choices": MilkCollection.Status.choices,
            "collection_form": collection_form,
            "export_from": start.isoformat() if start else "",
            "export_to": end.isoformat() if end else "",
        },
    )


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.DAIRY_MANAGER,
    Membership.Role.BRANCH_MANAGER,
    Membership.Role.COLLECTION_OPERATOR,
    permission="collections.create",
)
@require_http_methods(["GET", "POST"])
def collection_create(request, organization_slug):
    # Keep old bookmarks working while routing all entry through the unified page.
    return redirect("collections:list", organization_slug=organization_slug)


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.DAIRY_MANAGER,
    Membership.Role.QUALITY_OFFICER,
    permission="collections.approve",
)
@require_POST
def approve_collection(request, organization_slug, collection_id):
    branch_ids = accessible_branch_ids(request.membership)
    scoped = MilkCollection.objects.filter(organization=request.organization)
    if branch_ids is not None:
        scoped = scoped.filter(branch_id__in=branch_ids)
    get_object_or_404(scoped, pk=collection_id)
    try:
        entry = approve_collection_service(
            collection_id=collection_id, organization=request.organization, actor=request.user
        )
    except (MilkCollection.DoesNotExist, ValidationError) as exc:
        messages.error(request, str(exc))
    else:
        record_event(
            actor=request.user,
            organization=request.organization,
            action="milk_collection.approved",
            target=entry,
            request=request,
        )
        messages.success(request, "Collection approved.")
    return redirect("collections:list", organization_slug=organization_slug)


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.DAIRY_MANAGER,
    Membership.Role.BRANCH_MANAGER,
    Membership.Role.COLLECTION_OPERATOR,
    Membership.Role.QUALITY_OFFICER,
    permission="collections.create",
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
        entry = get_object_or_404(records, pk=collection_id)
        if entry.status in {MilkCollection.Status.REVERSED, MilkCollection.Status.APPROVED}:
            messages.error(
                request,
                "Approved or reversed collections cannot be edited; "
                "reverse an approved record with a reason.",
            )
            return redirect("collections:list", organization_slug=organization_slug)
        form = CollectionEditForm(request.POST or None, instance=entry)
        if request.method == "POST" and form.is_valid():
            data = form.cleaned_data
            before = {
                "quantity_litres": str(entry.quantity_litres),
                "snf": str(entry.snf),
                "fat": str(entry.fat),
                "lactose": str(entry.lactose),
                "milk_rate": str(entry.milk_rate),
                "total_amount": str(entry.total_amount),
            }
            from decimal import ROUND_HALF_UP, Decimal

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
            entry.total_amount = (entry.quantity_litres * entry.milk_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            entry.save(
                update_fields=[
                    "quantity_litres",
                    "snf",
                    "fat",
                    "lactose",
                    "milk_rate",
                    "lactometer_reading",
                    "milk_temperature_c",
                    "sample_reference",
                    "quality_test_method",
                    "notes",
                    "total_amount",
                    "updated_at",
                ]
            )
            after = {
                "quantity_litres": str(entry.quantity_litres),
                "snf": str(entry.snf),
                "fat": str(entry.fat),
                "lactose": str(entry.lactose),
                "milk_rate": str(entry.milk_rate),
                "total_amount": str(entry.total_amount),
            }
            record_event(
                actor=request.user,
                organization=organization,
                action="milk_collection.updated",
                target=entry,
                changes={"before": before, "after": after},
                request=request,
            )
            messages.success(request, f"Collection {entry.reference} updated.")
            return redirect("collections:list", organization_slug=organization_slug)
    return render(
        request,
        "collections/edit.html",
        {
            "organization": organization,
            "entry": entry,
            "form": form,
        },
    )


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
)
@require_POST
def collection_reverse(request, organization_slug, collection_id):
    reason = request.POST.get("reason", "").strip()
    if len(reason) < 8:
        messages.error(request, "Provide a clear reversal reason (at least 8 characters).")
        return redirect("collections:list", organization_slug=organization_slug)
    try:
        with transaction.atomic():
            entry = MilkCollection.objects.select_for_update().get(
                pk=collection_id, organization=request.organization
            )
            old_status = entry.status
            if entry.status == MilkCollection.Status.REVERSED:
                messages.info(request, "This collection has already been reversed.")
            else:
                entry = reverse_collection_service(
                    collection_id=collection_id,
                    organization=request.organization,
                    actor=request.user,
                    reason=reason,
                )
                record_event(
                    actor=request.user,
                    organization=request.organization,
                    action="milk_collection.reversed",
                    target=entry,
                    changes={
                        "from_status": old_status,
                        "to_status": entry.status,
                        "reason": reason,
                    },
                    request=request,
                )
                messages.success(
                    request,
                    f"Collection {entry.reference} reversed. Its audit history remains available.",
                )
    except (MilkCollection.DoesNotExist, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("collections:list", organization_slug=organization_slug)
