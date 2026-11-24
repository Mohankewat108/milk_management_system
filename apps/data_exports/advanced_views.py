from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, F, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.services import record_event
from apps.collections.models import MilkCollection
from apps.finance.models import (
    Expense,
    JournalEntry,
    JournalLine,
    LedgerConfiguration,
    Payment,
)
from apps.inventory.models import InventoryItem, StockMovement
from apps.organizations.decorators import organization_access
from apps.organizations.models import Branch, Membership
from apps.organizations.permissions import accessible_branch_ids, has_organization_permission
from apps.parties.models import Customer, Farmer

from .models import ImportBatch, SavedExportTemplate, ScheduledExport
from .services import MODULE_ROLES, can_export_module

COLLECTION_STATUS_CHOICES = MilkCollection.Status.choices


def _require_owner_admin(membership):
    if membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        raise PermissionDenied


def _require_reports_access(membership):
    if membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.BRANCH_MANAGER,
        Membership.Role.ACCOUNTANT,
    } and not (
        membership.role == Membership.Role.DAIRY_MANAGER
        and has_organization_permission(membership, "reports.view")
    ):
        raise PermissionDenied


def _organization_timezone(organization):
    try:
        return ZoneInfo(organization.timezone or timezone.get_current_timezone_name())
    except ZoneInfoNotFoundError:
        return timezone.get_current_timezone()


def _parse_report_period(request, organization):
    """Return validated inclusive dates in the organisation's local timezone."""
    today = timezone.localdate(timezone.now(), _organization_timezone(organization))
    period = request.GET.get("period", "custom").strip().lower()
    raw_start = request.GET.get("from", "").strip()
    raw_end = request.GET.get("to", "").strip()
    month_value = request.GET.get("month", "").strip()

    if period == "today":
        return today, today, period, ""
    if period == "yesterday":
        day = today - timedelta(days=1)
        return day, day, period, ""
    if period == "last_7_days":
        return today - timedelta(days=6), today, period, ""
    if period == "last_30_days":
        return today - timedelta(days=29), today, period, ""
    if period == "this_month":
        return today.replace(day=1), today, period, ""
    if period == "previous_month":
        first_this = today.replace(day=1)
        last_previous = first_this - timedelta(days=1)
        return last_previous.replace(day=1), last_previous, period, ""
    if period in {"this_quarter", "previous_quarter"}:
        quarter = (today.month - 1) // 3
        first_month = quarter * 3 + 1
        if period == "this_quarter":
            return date(today.year, first_month, 1), today, period, ""
        first_current = date(today.year, first_month, 1)
        last_previous = first_current - timedelta(days=1)
        previous_first = date(last_previous.year, ((last_previous.month - 1) // 3) * 3 + 1, 1)
        return previous_first, last_previous, period, ""
    if period in {"this_year", "previous_year"}:
        year = today.year if period == "this_year" else today.year - 1
        period_end = today if period == "this_year" else date(year, 12, 31)
        return date(year, 1, 1), period_end, period, ""
    if month_value:
        try:
            parsed_month = date.fromisoformat(f"{month_value}-01")
        except ValueError as exc:
            raise ValueError("Choose a valid reporting month.") from exc
        next_month = (
            date(parsed_month.year + 1, 1, 1)
            if parsed_month.month == 12
            else date(parsed_month.year, parsed_month.month + 1, 1)
        )
        return parsed_month, next_month - timedelta(days=1), "month", month_value

    try:
        start = date.fromisoformat(raw_start) if raw_start else None
        end = date.fromisoformat(raw_end) if raw_end else None
    except ValueError as exc:
        raise ValueError("Dates must use YYYY-MM-DD.") from exc
    if start and end and start > end:
        raise ValueError("Start date must be on or before end date.")
    return start, end, "custom", ""


def _safe_ratio(numerator, denominator):
    if not denominator:
        return None
    return numerator / denominator


def _milk_aggregate(queryset):
    return queryset.aggregate(
        records=Count("id"),
        litres=Sum("quantity_litres"),
        value=Sum("total_amount"),
        average_fat=Avg("fat"),
        average_snf=Avg("snf"),
        average_lactose=Avg("lactose"),
        average_temperature=Avg("milk_temperature_c"),
        average_lactometer=Avg("lactometer_reading"),
        weighted_fat=Sum(F("fat") * F("quantity_litres")),
        weighted_snf=Sum(F("snf") * F("quantity_litres")),
        weighted_lactose=Sum(F("lactose") * F("quantity_litres")),
        farmers=Count("farmer_id", distinct=True),
        customers=Count("customer_id", distinct=True),
    )


def _round_weighted(total, litres):
    return _safe_ratio(total, litres)


@login_required
@organization_access()
@require_POST
def save_export_template(request, organization_slug):
    module = request.POST.get("module", "")
    file_format = request.POST.get("file_format", "xlsx")
    if not can_export_module(request.membership, module):
        raise PermissionDenied
    if file_format not in {"csv", "xlsx", "pdf"}:
        messages.error(request, "Choose CSV, Excel or PDF.")
        return redirect("data_exports:centre", organization_slug=organization_slug)
    name = request.POST.get("name", "").strip()[:100]
    if not name:
        messages.error(request, "Enter a name for this export template.")
        return redirect("data_exports:centre", organization_slug=organization_slug)
    filters = {key: request.POST.get(key, "") for key in ("branch", "status", "from", "to")}
    template = SavedExportTemplate.objects.filter(
        organization=request.organization, name=name
    ).first()
    if (
        template
        and template.created_by_id != request.user.pk
        and request.membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}
    ):
        raise PermissionDenied
    created = template is None
    if created:
        template = SavedExportTemplate(
            organization=request.organization, name=name, created_by=request.user
        )
    template.module = module
    template.file_format = file_format
    template.filters = filters
    template.is_shared = request.POST.get("is_shared") == "on"
    template.save()
    record_event(
        actor=request.user,
        organization=request.organization,
        action="export_template.created" if created else "export_template.updated",
        target=template,
        request=request,
    )
    messages.success(request, "Export template saved.")
    return redirect("data_exports:centre", organization_slug=organization_slug)


@login_required
@organization_access()
@require_POST
def create_schedule(request, organization_slug):
    _require_owner_admin(request.membership)
    module = request.POST.get("module", "")
    frequency = request.POST.get("frequency", "weekly")
    file_format = request.POST.get("file_format", "xlsx")
    if (
        module not in MODULE_ROLES
        or frequency not in ScheduledExport.Frequency.values
        or file_format not in {"csv", "xlsx", "pdf"}
    ):
        messages.error(request, "Choose a valid module, schedule and file format.")
        return redirect("data_exports:centre", organization_slug=organization_slug)
    if request.membership.role not in MODULE_ROLES[module]:
        raise PermissionDenied
    filters = {key: request.POST.get(key, "") for key in ("branch", "status", "from", "to")}
    now = timezone.now()
    first_run = now + (
        timedelta(days=1)
        if frequency == "daily"
        else timedelta(days=7)
        if frequency == "weekly"
        else timedelta(days=30)
    )
    schedule = ScheduledExport.objects.create(
        organization=request.organization,
        created_by=request.user,
        name=request.POST.get("name", f"{module.title()} {frequency}")[:100],
        module=module,
        frequency=frequency,
        file_format=file_format,
        filters=filters,
        next_run_at=first_run,
    )
    record_event(
        actor=request.user,
        organization=request.organization,
        action="export_schedule.created",
        target=schedule,
        request=request,
    )
    messages.success(
        request, "Scheduled export created. Ensure the scheduler command runs periodically."
    )
    return redirect("data_exports:centre", organization_slug=organization_slug)


@login_required
@organization_access()
@require_POST
def toggle_schedule(request, organization_slug, schedule_id):
    schedule = get_object_or_404(ScheduledExport, pk=schedule_id, organization=request.organization)
    if schedule.created_by_id != request.user.pk and request.membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }:
        raise PermissionDenied
    schedule.is_active = not schedule.is_active
    schedule.save(update_fields=["is_active", "updated_at"])
    record_event(
        actor=request.user,
        organization=request.organization,
        action="export_schedule.toggled",
        target=schedule,
        changes={"is_active": schedule.is_active},
        request=request,
    )
    return redirect("data_exports:centre", organization_slug=organization_slug)


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN)
@require_POST
def upload_import(request, organization_slug):
    module = request.POST.get("module", "")
    upload = request.FILES.get("file")
    if module not in {"farmers", "customers"} or not upload:
        messages.error(request, "Choose Farmers or Customers and upload a CSV file.")
        return redirect("data_exports:centre", organization_slug=organization_slug)
    if not upload.name.lower().endswith(".csv") or upload.size > 10 * 1024 * 1024:
        messages.error(request, "Upload a CSV file no larger than 10 MB.")
        return redirect("data_exports:centre", organization_slug=organization_slug)
    batch = ImportBatch.objects.create(
        organization=request.organization,
        uploaded_by=request.user,
        module=module,
        file=upload,
    )
    record_event(
        actor=request.user,
        organization=request.organization,
        action="import.uploaded",
        target=batch,
        request=request,
    )
    messages.success(request, "CSV uploaded. Run the import worker to validate and process it.")
    return redirect("data_exports:centre", organization_slug=organization_slug)


@login_required
@organization_access()
@require_POST
def bulk_party_action(request, organization_slug, module):
    if module not in {"farmers", "customers"}:
        raise PermissionDenied
    if request.membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.BRANCH_MANAGER,
    }:
        raise PermissionDenied
    ids = request.POST.getlist("selected")
    if not ids or len(ids) > 500:
        messages.error(request, "Select between 1 and 500 records.")
        return redirect(
            "parties:farmers" if module == "farmers" else "parties:customers",
            organization_slug=organization_slug,
        )
    model = Farmer if module == "farmers" else Customer
    qs = model.objects.filter(
        organization=request.organization, deleted_at__isnull=True, pk__in=ids
    )
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None:
        qs = qs.filter(branch_id__in=branch_ids)
    action = request.POST.get("action")
    if action not in {"activate", "deactivate"}:
        messages.error(request, "Choose activate or deactivate.")
    else:
        changed = qs.update(is_active=(action == "activate"))
        record_event(
            actor=request.user,
            organization=request.organization,
            action=f"{module}.bulk_{action}",
            changes={"record_count": changed},
            request=request,
        )
        messages.success(request, f"{changed} {module} records updated.")
    return redirect(
        "parties:farmers" if module == "farmers" else "parties:customers",
        organization_slug=organization_slug,
    )


@login_required
@organization_access()
def reports_dashboard(request, organization_slug):
    membership = request.membership
    _require_reports_access(membership)
    organization = request.organization
    accessible_ids = accessible_branch_ids(membership)

    available_branches = Branch.objects.filter(
        organization=organization, is_active=True, deleted_at__isnull=True
    ).order_by("name")
    if accessible_ids is not None:
        available_branches = available_branches.filter(pk__in=accessible_ids)
    allowed_ids = {str(value) for value in available_branches.values_list("pk", flat=True)}

    selected_branch_ids = [value for value in request.GET.getlist("branch") if value in allowed_ids]
    branch_params_present = "branch" in request.GET or "all_branches" in request.GET
    all_branches_selected = request.GET.get("all_branches") == "1" or not branch_params_present
    if all_branches_selected:
        selected_branch_ids = list(allowed_ids)

    try:
        start_date, end_date, period, selected_month = _parse_report_period(request, organization)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("data_exports:reports", organization_slug=organization_slug)

    collections = MilkCollection.objects.filter(
        organization=organization, branch_id__in=selected_branch_ids
    )
    payments = Payment.objects.filter(
        organization=organization,
        branch_id__in=selected_branch_ids,
        deleted_at__isnull=True,
    )
    expenses = Expense.objects.filter(
        organization=organization,
        branch_id__in=selected_branch_ids,
        deleted_at__isnull=True,
    )
    inventory = InventoryItem.objects.filter(
        organization=organization,
        branch_id__in=selected_branch_ids,
        deleted_at__isnull=True,
        is_active=True,
    )

    status_filter = request.GET.get("status", "").strip()
    valid_statuses = {choice[0] for choice in MilkCollection.Status.choices}
    if status_filter and status_filter not in valid_statuses:
        status_filter = ""
    if status_filter:
        collections = collections.filter(status=status_filter)

    farmer_id = request.GET.get("farmer", "").strip()
    customer_id = request.GET.get("customer", "").strip()
    farmer = customer = None
    if farmer_id:
        farmer = get_object_or_404(
            Farmer.objects.filter(
                organization=organization,
                deleted_at__isnull=True,
                branch_id__in=selected_branch_ids,
            ),
            pk=farmer_id,
        )
        collections = collections.filter(farmer=farmer)
        payments = payments.filter(farmer=farmer)
    if customer_id:
        customer = get_object_or_404(
            Customer.objects.filter(
                organization=organization,
                deleted_at__isnull=True,
                branch_id__in=selected_branch_ids,
            ),
            pk=customer_id,
        )
        collections = collections.filter(customer=customer)
        payments = payments.filter(customer=customer)

    if start_date:
        start_dt = timezone.make_aware(
            datetime.combine(start_date, time.min), _organization_timezone(organization)
        )
        collections = collections.filter(collected_at__gte=start_dt)
        payments = payments.filter(paid_at__gte=start_dt)
        expenses = expenses.filter(expense_date__gte=start_date)
    if end_date:
        end_exclusive = timezone.make_aware(
            datetime.combine(end_date + timedelta(days=1), time.min),
            _organization_timezone(organization),
        )
        collections = collections.filter(collected_at__lt=end_exclusive)
        payments = payments.filter(paid_at__lt=end_exclusive)
        expenses = expenses.filter(expense_date__lte=end_date)

    approved = collections.filter(status=MilkCollection.Status.APPROVED)
    rejected = collections.filter(status=MilkCollection.Status.REJECTED)
    farmer_approved = approved.filter(farmer__isnull=False)
    customer_approved = approved.filter(customer__isnull=False)
    farmer_totals = _milk_aggregate(farmer_approved)
    customer_totals = _milk_aggregate(customer_approved)
    collection_totals = _milk_aggregate(approved)
    litres = farmer_totals["litres"] or Decimal("0")
    farmer_milk_value = farmer_totals["value"] or Decimal("0")
    customer_litres = customer_totals["litres"] or Decimal("0")
    customer_milk_value = customer_totals["value"] or Decimal("0")
    weighted_fat = _round_weighted(farmer_totals["weighted_fat"], litres)
    weighted_snf = _round_weighted(farmer_totals["weighted_snf"], litres)
    weighted_lactose = _round_weighted(farmer_totals["weighted_lactose"], litres)

    payment_completed = payments.filter(status=Payment.Status.COMPLETED)
    farmer_payments = payment_completed.filter(
        direction=Payment.Direction.OUTGOING, farmer__isnull=False
    )
    customer_receipts = payment_completed.filter(
        direction=Payment.Direction.INCOMING, customer__isnull=False
    )
    pending_payments = payments.filter(status=Payment.Status.PENDING)

    farmer_paid = farmer_payments.aggregate(v=Sum("amount"))["v"] or Decimal("0")
    farmer_balance = None
    ledger_enabled = False
    ledger_configuration = LedgerConfiguration.objects.filter(
        organization=organization, is_enabled=True, enable_farmer_collection_posting=True
    ).select_related("farmer_payable_account").first()
    if ledger_configuration:
        ledger_enabled = True
        payable_account = ledger_configuration.farmer_payable_account
        payable_lines = JournalLine.objects.filter(
            entry__organization=organization,
            entry__status=JournalEntry.Status.POSTED,
            account=payable_account,
            entry__branch_id__in=selected_branch_ids,
        )
        if end_date:
            payable_lines = payable_lines.filter(entry__entry_date__lte=end_date)
        payable_totals = payable_lines.aggregate(debits=Sum("debit"), credits=Sum("credit"))
        farmer_balance = (payable_totals["credits"] or Decimal("0")) - (
            payable_totals["debits"] or Decimal("0")
        )

    approved_expenses = expenses.filter(status=Expense.Status.APPROVED)
    expense_total = approved_expenses.aggregate(v=Sum("amount"))["v"] or Decimal("0")
    low_stock_items = inventory.filter(current_stock__lte=F("reorder_level")).annotate(
        stock_value=F("current_stock") * F("purchase_price")
    )
    out_of_stock_items = inventory.filter(current_stock__lte=0)

    daily_collections = (
        farmer_approved.annotate(day=TruncDate("collected_at"))
        .values("day")
        .annotate(
            records=Count("id"),
            litres=Sum("quantity_litres"),
            value=Sum("total_amount"),
            average_fat=Avg("fat"),
            average_snf=Avg("snf"),
            average_lactose=Avg("lactose"),
            farmers=Count("farmer_id", distinct=True),
        )
        .order_by("day")
    )
    daily_chart_data = [
        {
            "label": row["day"].isoformat(),
            "litres": float(row["litres"] or 0),
            "value": float(row["value"] or 0),
        }
        for row in daily_collections
    ]
    monthly_collections = list(
        farmer_approved.annotate(month=TruncMonth("collected_at"))
        .values("month")
        .annotate(
            records=Count("id"),
            litres=Sum("quantity_litres"),
            value=Sum("total_amount"),
            average_fat=Avg("fat"),
            average_snf=Avg("snf"),
            average_lactose=Avg("lactose"),
            farmers=Count("farmer_id", distinct=True),
        )
        .order_by("month")
    )
    for row in monthly_collections:
        row["average_price"] = _safe_ratio(row["value"], row["litres"])
    monthly_chart_data = [
        {
            "label": row["month"].strftime("%Y-%m"),
            "litres": float(row["litres"] or 0),
            "value": float(row["value"] or 0),
        }
        for row in monthly_collections
    ]
    branch_rows = list(
        farmer_approved.values("branch_id", "branch__name")
        .annotate(
            records=Count("id"),
            litres=Sum("quantity_litres"),
            value=Sum("total_amount"),
            average_fat=Avg("fat"),
            average_snf=Avg("snf"),
            average_lactose=Avg("lactose"),
            farmers=Count("farmer_id", distinct=True),
        )
        .order_by("-litres", "branch__name")
    )
    customer_branch_rows = {
        str(row["branch_id"]): row
        for row in customer_approved.values("branch_id")
        .annotate(
            customer_litres=Sum("quantity_litres"),
            customer_value=Sum("total_amount"),
            customer_count=Count("id"),
            customers=Count("customer_id", distinct=True),
        )
    }
    existing_branch_ids = {str(row["branch_id"]) for row in branch_rows}
    selected_branches = available_branches.filter(pk__in=selected_branch_ids)
    for branch in selected_branches:
        customer_row = customer_branch_rows.get(str(branch.pk), {})
        if str(branch.pk) not in existing_branch_ids:
            branch_rows.append({
                "branch_id": branch.pk,
                "branch__name": branch.name,
                "records": 0,
                "litres": Decimal("0"),
                "value": Decimal("0"),
                "average_fat": None,
                "average_snf": None,
                "average_lactose": None,
                "farmers": 0,
            })
    for row in branch_rows:
        row["average_price"] = _safe_ratio(row["value"], row["litres"])
        row["contribution_pct"] = (
            (row["litres"] / litres * Decimal("100")) if litres else None
        )
        customer_row = customer_branch_rows.get(str(row["branch_id"]), {})
        row["customer_litres"] = customer_row.get("customer_litres") or Decimal("0")
        row["customer_value"] = customer_row.get("customer_value") or Decimal("0")
        row["customer_count"] = customer_row.get("customers") or 0
        row["customer_records"] = customer_row.get("customer_count") or 0
    branch_rows.sort(key=lambda row: (row["litres"] or Decimal("0")), reverse=True)

    farmer_rows = list(
        farmer_approved
        .values("farmer_id", "farmer__code", "farmer__full_name", "branch__name")
        .annotate(
            records=Count("id"),
            litres=Sum("quantity_litres"),
            value=Sum("total_amount"),
            average_fat=Avg("fat"),
            average_snf=Avg("snf"),
            average_lactose=Avg("lactose"),
        )
        .order_by("-litres", "farmer__full_name")[:100]
    )
    for row in farmer_rows:
        row["average_price"] = _safe_ratio(row["value"], row["litres"])
    farmer_leaderboard = farmer_rows

    customer_rows = list(
        customer_approved
        .values("customer_id", "customer__code", "customer__full_name", "branch__name")
        .annotate(
            records=Count("id"),
            litres=Sum("quantity_litres"),
            value=Sum("total_amount"),
            average_fat=Avg("fat"),
            average_snf=Avg("snf"),
            average_lactose=Avg("lactose"),
        )
        .order_by("-litres", "customer__full_name")[:100]
    )
    for row in customer_rows:
        row["average_price"] = _safe_ratio(row["value"], row["litres"])

    branch_movement = StockMovement.objects.filter(
        organization=organization,
        item__branch_id__in=selected_branch_ids,
    )
    if start_date:
        branch_movement = branch_movement.filter(created_at__date__gte=start_date)
    if end_date:
        branch_movement = branch_movement.filter(created_at__date__lte=end_date)

    stock_purchase_quantity = branch_movement.filter(
        kind=StockMovement.Kind.PURCHASE
    ).aggregate(total=Sum("quantity_delta"))["total"] or Decimal("0")
    stock_usage_quantity = branch_movement.filter(
        kind=StockMovement.Kind.USAGE
    ).aggregate(total=Sum("quantity_delta"))["total"] or Decimal("0")
    status_rows = list(
        collections.values("status").annotate(total=Count("id")).order_by("status")
    )
    period_insights = []
    previous_litres = Decimal("0")
    if start_date and end_date:
        duration = (end_date - start_date).days + 1
        previous_start = start_date - timedelta(days=duration)
        previous_end = start_date - timedelta(days=1)
        previous_query = MilkCollection.objects.filter(
            organization=organization,
            branch_id__in=selected_branch_ids,
            farmer__isnull=False,
            status=MilkCollection.Status.APPROVED,
        )
        if farmer:
            previous_query = previous_query.filter(farmer=farmer)
        if customer:
            previous_query = previous_query.none()
        previous_litres = previous_query.filter(
            collected_at__gte=timezone.make_aware(
                datetime.combine(previous_start, time.min), _organization_timezone(organization)
            ),
            collected_at__lt=timezone.make_aware(
                datetime.combine(start_date, time.min), _organization_timezone(organization)
            ),
        ).aggregate(v=Sum("quantity_litres"))["v"] or Decimal("0")
    current_litres = farmer_totals["litres"] or Decimal("0")
    growth_pct = None
    if previous_litres:
        growth_pct = ((current_litres - previous_litres) / previous_litres) * Decimal("100")
    if growth_pct is not None:
        if growth_pct > 0:
            direction = "increased"
        elif growth_pct < 0:
            direction = "decreased"
        else:
            direction = "unchanged"
        period_insights.append({
            "title": f"Milk supply {direction} compared with the previous equal-length period",
            "detail": f"{growth_pct:+.1f}% ? {previous_start} to {previous_end}",
        })
    if branch_rows and litres:
        top_branch = branch_rows[0]
        period_insights.append({
            "title": f"{top_branch['branch__name']} is the highest-volume branch",
            "detail": (
                f"{top_branch['litres']:.2f} L ? "
                f"{top_branch['contribution_pct']:.1f}% of farmer supply"
            ),
        })
    if farmer_rows and len(farmer_rows) > 1:
        period_insights.append({
            "title": "Farmer leaderboard",
            "detail": (
                f"{farmer_rows[0]['farmer__full_name']} leads with "
                f"{farmer_rows[0]['litres']:.2f} L"
            ),
        })
    financial_by_branch = list(
        farmer_approved.values("branch_id", "branch__name")
        .annotate(milk_value=Sum("total_amount"))
        .order_by("-milk_value")
    )
    expense_categories = list(
        approved_expenses.values("category")
        .annotate(total=Sum("amount"), records=Count("id"))
        .order_by("-total")
    )

    context = {
        "organization": organization,
        "available_branches": available_branches,
        "selected_branch_ids": selected_branch_ids,
        "all_branches_selected": all_branches_selected,
        "date_from": start_date.isoformat() if start_date else "",
        "date_to": end_date.isoformat() if end_date else "",
        "period": period,
        "selected_month": selected_month,
        "status_filter": status_filter,
        "collection_status_choices": COLLECTION_STATUS_CHOICES,
        "selected_farmer": farmer,
        "selected_customer": customer,
        "farmers": Farmer.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
            branch_id__in=selected_branch_ids,
        ).order_by("full_name")[:500],
        "customers": Customer.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
            branch_id__in=selected_branch_ids,
        ).order_by("full_name")[:500],
        "collection_count": farmer_totals["records"] or 0,
        "milk_litres": litres,
        "milk_value": farmer_milk_value,
        "average_price": _safe_ratio(farmer_milk_value, litres),
        "average_litres_per_collection": _safe_ratio(litres, farmer_totals["records"]),
        "average_fat": farmer_totals["average_fat"],
        "average_snf": farmer_totals["average_snf"],
        "average_lactose": farmer_totals["average_lactose"],
        "weighted_fat": weighted_fat,
        "weighted_snf": weighted_snf,
        "weighted_lactose": weighted_lactose,
        "average_temperature": collection_totals["average_temperature"],
        "average_lactometer": collection_totals["average_lactometer"],
        "farmers_supplied": farmer_totals["farmers"] or 0,
        "customers_served": customer_totals["customers"] or 0,
        "customer_litres": customer_litres,
        "customer_milk_value": customer_milk_value,
        "customer_collection_count": customer_totals["records"] or 0,
        "payments_total": farmer_paid,
        "customer_receipts": customer_receipts.aggregate(v=Sum("amount"))["v"] or 0,
        "pending_payments": pending_payments.aggregate(v=Sum("amount"))["v"] or 0,
        "expenses_total": expense_total,
        "farmer_milk_value": farmer_milk_value,
        "farmer_paid": farmer_paid,
        "farmer_balance": farmer_balance,
        "ledger_balance_available": ledger_enabled,
        "low_stock_count": low_stock_items.count(),
        "out_of_stock_count": out_of_stock_items.count(),
        "low_stock_value": low_stock_items.aggregate(
            total=Sum(F("current_stock") * F("purchase_price"))
        )["total"] or Decimal("0"),
        "low_stock_items": low_stock_items.select_related("branch")
        .order_by("branch__name", "name")[:50],
        "daily_collections": daily_collections,
        "monthly_collections": monthly_collections,
        "daily_chart_data": daily_chart_data,
        "monthly_chart_data": monthly_chart_data,
        "branch_rows": branch_rows,
        "farmer_rows": farmer_rows,
        "farmer_leaderboard": farmer_leaderboard,
        "customer_rows": customer_rows,
        "collection_statuses": status_rows,
        "financial_by_branch": financial_by_branch,
        "expense_categories": expense_categories,
        "stock_movement_count": branch_movement.count(),
        "purchase_movements": branch_movement.filter(kind=StockMovement.Kind.PURCHASE).count(),
        "usage_movements": branch_movement.filter(kind=StockMovement.Kind.USAGE).count(),
        "stock_purchase_quantity": stock_purchase_quantity,
        "stock_usage_quantity": abs(stock_usage_quantity),
        "approved_count": collection_totals["records"] or 0,
        "submitted_count": collections.filter(status=MilkCollection.Status.SUBMITTED).count(),
        "rejected_count": rejected.count(),
        "period_label": f"{start_date or 'All time'} – {end_date or 'Today'}",
    }
    return render(request, "data_exports/reports.html", context)



@login_required
@organization_access()
@require_POST
def queue_report_export(request, organization_slug):
    from .queue import queue_export

    _require_reports_access(request.membership)
    params = request.POST.copy()
    params.setlist("branch", request.POST.getlist("branch"))
    if request.POST.get("all_branches") == "1":
        params.pop("branch", None)
        params["all_branches"] = "1"
    try:
        job = queue_export(
            module="reports",
            file_format=request.POST.get("file_format", "xlsx").lower(),
            organization=request.organization,
            membership=request.membership,
            actor=request.user,
            filters=params,
        )
    except (PermissionDenied, ValueError) as exc:
        raise PermissionDenied from exc
    messages.success(request, f"Advanced report export queued ({str(job.pk)[:8]}).")
    return redirect("data_exports:reports", organization_slug=organization_slug)

@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN)
def import_sample(request, organization_slug, module):
    if module not in {"farmers", "customers"}:
        raise PermissionDenied
    response = HttpResponse(
        "code,full_name,phone,email,address,branch_code\r\n"
        "F-1001,Example Farmer,9800000000,farmer@example.com,Parasi,MAIN\r\n",
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="' + module + '-import-template.csv"'
    response["Cache-Control"] = "private, no-store"
    return response
