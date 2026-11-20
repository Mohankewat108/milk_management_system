from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.audit.services import record_event
from apps.collections.models import MilkCollection
from apps.core.nepali_dates import format_local_date, parse_local_date
from apps.finance.models import Payment
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids, can_access_branch

from .forms import CustomerForm, FarmerForm
from .models import Customer, Farmer

OWNER_ROLES = (Membership.Role.OWNER, Membership.Role.ADMIN)
PARTY_VIEW_ROLES = (
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.DAIRY_MANAGER,
    Membership.Role.BRANCH_MANAGER,
    Membership.Role.SUPPORT,
)


def _party_scope(queryset, membership):
    branch_ids = accessible_branch_ids(membership)
    return queryset if branch_ids is None else queryset.filter(branch_id__in=branch_ids)


def _date_bounds(request):
    """Return a validated inclusive date range; default is the current month."""
    today = timezone.localdate()
    start_text = request.GET.get("from", "").strip()
    end_text = request.GET.get("to", "").strip()
    language_code = getattr(request, "LANGUAGE_CODE", "en")
    try:
        start = parse_local_date(start_text, language_code) if start_text else today.replace(day=1)
        end = parse_local_date(end_text, language_code) if end_text else today
    except ValueError as exc:
        return today.replace(day=1), today, str(exc)
    if start > end:
        return today.replace(day=1), today, "The start date must be on or before the end date."
    if (end - start).days > 3660:
        return today.replace(day=1), today, "Choose a date range of ten years or less."
    return start, end, ""


def _party_profile_context(*, party, kind, request):
    try:
        today = timezone.now().astimezone(ZoneInfo(request.organization.timezone)).date()
    except Exception:
        today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    previous_month_end = month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    start, end, date_error = _date_bounds(request)

    relation = "customer" if kind == "customer" else "farmer"
    # MilkCollection uses workflow states (draft/submitted/approved/rejected/reversed)
    # and does not implement soft deletion. Do not filter on deleted_at here.
    collections = (
        MilkCollection.objects.filter(
            organization=request.organization,
            **{relation: party},
        )
        .select_related("branch", "recorded_by", "pricing")
        .order_by("-collected_at")
    )
    collections = _party_scope(collections, request.membership)

    approved = collections.filter(status=MilkCollection.Status.APPROVED)
    filtered_approved = approved.filter(collected_at__date__gte=start, collected_at__date__lte=end)
    metrics = {
        "today_litres": approved.filter(collected_at__date=today).aggregate(
            v=Sum("quantity_litres")
        )["v"]
        or Decimal("0"),
        "week_litres": approved.filter(
            collected_at__date__gte=week_start, collected_at__date__lte=today
        ).aggregate(v=Sum("quantity_litres"))["v"]
        or Decimal("0"),
        "month_litres": approved.filter(
            collected_at__date__gte=month_start, collected_at__date__lte=today
        ).aggregate(v=Sum("quantity_litres"))["v"]
        or Decimal("0"),
        "previous_month_litres": approved.filter(
            collected_at__date__gte=previous_month_start, collected_at__date__lte=previous_month_end
        ).aggregate(v=Sum("quantity_litres"))["v"]
        or Decimal("0"),
        "lifetime_litres": approved.aggregate(v=Sum("quantity_litres"))["v"] or Decimal("0"),
        "lifetime_value": approved.aggregate(v=Sum("total_amount"))["v"] or Decimal("0"),
        "active_collection_days": approved.values("collected_at__date").distinct().count(),
        "average_litres": approved.aggregate(v=Avg("quantity_litres"))["v"] or Decimal("0"),
        "average_fat": approved.aggregate(v=Avg("fat"))["v"],
        "average_snf": approved.aggregate(v=Avg("snf"))["v"],
        "average_lactose": approved.aggregate(v=Avg("lactose"))["v"],
    }
    metrics["average_per_collection_day"] = (
        metrics["lifetime_litres"] / metrics["active_collection_days"]
        if metrics["active_collection_days"]
        else Decimal("0")
    )

    payments = (
        Payment.objects.filter(
            organization=request.organization,
            **{relation: party},
        )
        .select_related("branch", "recorded_by")
        .order_by("-paid_at", "-created_at")
    )
    payments = _party_scope(payments, request.membership)
    completed = payments.filter(status=Payment.Status.COMPLETED)
    payment_direction = (
        Payment.Direction.INCOMING if kind == "customer" else Payment.Direction.OUTGOING
    )
    completed_sum = completed.filter(direction=payment_direction).aggregate(v=Sum("amount"))[
        "v"
    ] or Decimal("0")

    filtered_approved = (
        filtered_approved.filter(branch_id__in=accessible_branch_ids(request.membership))
        if accessible_branch_ids(request.membership) is not None
        else filtered_approved
    )
    selected_metrics = filtered_approved.aggregate(
        litres=Sum("quantity_litres"),
        value=Sum("total_amount"),
        average_fat=Avg("fat"),
        average_snf=Avg("snf"),
    )
    history = Paginator(
        collections.filter(collected_at__date__gte=start, collected_at__date__lte=end), 25
    ).get_page(request.GET.get("page"))
    payment_history = Paginator(payments, 15).get_page(request.GET.get("payment_page"))
    status_counts = collections.values("status").annotate(total=Count("id"))
    status_summary = {item["status"]: item["total"] for item in status_counts}

    return {
        "organization": request.organization,
        "party": party,
        "kind": kind,
        "metrics": metrics,
        "selected_metrics": selected_metrics,
        "date_from": start,
        "date_to": end,
        "date_error": date_error,
        "date_calendar": "BS" if (getattr(request, "LANGUAGE_CODE", "en") == "ne") else "AD",
        "history": history,
        "payments": payment_history,
        "completed_payment_total": completed_sum,
        "payment_direction_label": "Received from customer"
        if kind == "customer"
        else "Paid to farmer",
        "status_summary": status_summary,
        "currency": request.organization.currency,
        "can_view_finance": request.membership.role
        in {
            Membership.Role.OWNER,
            Membership.Role.ADMIN,
            Membership.Role.ACCOUNTANT,
        },
        "can_manage_parties": request.membership.role in OWNER_ROLES,
    }


@login_required
@organization_access(*PARTY_VIEW_ROLES)
def customer_list(request, organization_slug):
    org = request.organization
    records = (
        Customer.objects.filter(organization=org, deleted_at__isnull=True)
        .select_related("branch", "user")
        .order_by("full_name")
    )
    records = _party_scope(records, request.membership)
    term = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    branch = request.GET.get("branch", "").strip()
    registered_from = request.GET.get("registered_from", "").strip()
    registered_to = request.GET.get("registered_to", "").strip()
    if term:
        records = records.filter(
            Q(full_name__icontains=term)
            | Q(code__icontains=term)
            | Q(phone__icontains=term)
            | Q(email__icontains=term)
        )
    if status in {"active", "inactive"}:
        records = records.filter(is_active=(status == "active"))
    if branch:
        records = records.filter(branch_id=branch)
    language_code = getattr(request, "LANGUAGE_CODE", "en")
    date_error = ""
    try:
        from_date = parse_local_date(registered_from, language_code)
        to_date = parse_local_date(registered_to, language_code)
    except ValueError as exc:
        from_date = to_date = None
        date_error = str(exc)
    if from_date and to_date and from_date > to_date:
        from_date = to_date = None
        date_error = "The start date must be on or before the end date."
    if from_date:
        records = records.filter(created_at__date__gte=from_date)
    if to_date:
        records = records.filter(created_at__date__lte=to_date)
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "parties/customers.html",
        {
            "organization": org,
            "page_obj": page,
            "query": term,
            "status_filter": status,
            "branch_filter": branch,
            "registered_from": format_local_date(from_date, language_code)
            if from_date
            else registered_from,
            "registered_to": format_local_date(to_date, language_code)
            if to_date
            else registered_to,
            "date_error": date_error,
            "date_calendar": "BS" if language_code == "ne" else "AD",
            "branches": org.branches.filter(is_active=True, deleted_at__isnull=True)
            if accessible_branch_ids(request.membership) is None
            else org.branches.filter(
                pk__in=accessible_branch_ids(request.membership), is_active=True
            ),
        },
    )


@login_required
@organization_access(*PARTY_VIEW_ROLES)
def customer_detail(request, organization_slug, customer_id):
    party = get_object_or_404(
        _party_scope(
            Customer.objects.filter(organization=request.organization, deleted_at__isnull=True),
            request.membership,
        ),
        pk=customer_id,
    )
    return render(
        request,
        "parties/party_detail.html",
        _party_profile_context(
            party=party,
            kind="customer",
            request=request,
        ),
    )


@login_required
@organization_access(*PARTY_VIEW_ROLES)
def farmer_list(request, organization_slug):
    org = request.organization
    records = (
        Farmer.objects.filter(organization=org, deleted_at__isnull=True)
        .select_related("branch", "user")
        .order_by("full_name")
    )
    records = _party_scope(records, request.membership)
    term = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    branch = request.GET.get("branch", "").strip()
    registered_from = request.GET.get("registered_from", "").strip()
    registered_to = request.GET.get("registered_to", "").strip()
    if term:
        records = records.filter(
            Q(full_name__icontains=term)
            | Q(code__icontains=term)
            | Q(phone__icontains=term)
            | Q(email__icontains=term)
        )
    if status in {"active", "inactive"}:
        records = records.filter(is_active=(status == "active"))
    if branch:
        records = records.filter(branch_id=branch)
    language_code = getattr(request, "LANGUAGE_CODE", "en")
    date_error = ""
    try:
        from_date = parse_local_date(registered_from, language_code)
        to_date = parse_local_date(registered_to, language_code)
    except ValueError as exc:
        from_date = to_date = None
        date_error = str(exc)
    if from_date and to_date and from_date > to_date:
        from_date = to_date = None
        date_error = "The start date must be on or before the end date."
    if from_date:
        records = records.filter(created_at__date__gte=from_date)
    if to_date:
        records = records.filter(created_at__date__lte=to_date)
    branch_ids = accessible_branch_ids(request.membership)
    branches = (
        org.branches.filter(is_active=True, deleted_at__isnull=True)
        if branch_ids is None
        else org.branches.filter(pk__in=branch_ids, is_active=True)
    )
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "parties/farmers.html",
        {
            "organization": org,
            "page_obj": page,
            "query": term,
            "status_filter": status,
            "branch_filter": branch,
            "registered_from": format_local_date(from_date, language_code)
            if from_date
            else registered_from,
            "registered_to": format_local_date(to_date, language_code)
            if to_date
            else registered_to,
            "date_error": date_error,
            "date_calendar": "BS" if language_code == "ne" else "AD",
            "branches": branches,
        },
    )


@login_required
@organization_access(*PARTY_VIEW_ROLES)
def farmer_detail(request, organization_slug, farmer_id):
    party = get_object_or_404(
        _party_scope(
            Farmer.objects.filter(organization=request.organization, deleted_at__isnull=True),
            request.membership,
        ),
        pk=farmer_id,
    )
    return render(
        request,
        "parties/party_detail.html",
        _party_profile_context(
            party=party,
            kind="farmer",
            request=request,
        ),
    )


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER)
@require_http_methods(["GET", "POST"])
def customer_create(request, organization_slug):
    org = request.organization
    form = CustomerForm(request.POST or None, organization=org, membership=request.membership)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if request.membership.role not in OWNER_ROLES and not data.get("branch"):
            form.add_error("branch", "Select a branch assigned to your staff account.")
        elif data.get("branch") and not can_access_branch(request.membership, data["branch"]):
            form.add_error("branch", "You are not assigned to this branch.")
        else:
            customer = form.save(commit=False)
            customer.organization = org
            customer.save()
            record_event(
                actor=request.user,
                organization=org,
                action="customer.created",
                target=customer,
                request=request,
            )
            messages.success(request, f"Customer {customer.full_name} created.")
            return redirect("parties:customers", organization_slug=organization_slug)
    return render(request, "parties/customer_form.html", {"organization": org, "form": form})


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.BRANCH_MANAGER,
    Membership.Role.SUPPORT,
)
def farmer_list_placeholder(request, organization_slug):
    return redirect("parties:farmers", organization_slug=organization_slug)


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER)
@require_http_methods(["GET", "POST"])
def farmer_create(request, organization_slug):
    org = request.organization
    form = FarmerForm(request.POST or None, organization=org, membership=request.membership)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if request.membership.role not in OWNER_ROLES and not data.get("branch"):
            form.add_error("branch", "Select a branch assigned to your staff account.")
        elif data.get("branch") and not can_access_branch(request.membership, data["branch"]):
            form.add_error("branch", "You are not assigned to this branch.")
        else:
            farmer = form.save(commit=False)
            farmer.organization = org
            farmer.save()
            record_event(
                actor=request.user,
                organization=org,
                action="farmer.created",
                target=farmer,
                request=request,
            )
            messages.success(request, f"Farmer {farmer.full_name} created.")
            return redirect("parties:farmers", organization_slug=organization_slug)
    return render(request, "parties/farmer_form.html", {"organization": org, "form": form})
