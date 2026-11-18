from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.services import record_event
from apps.collections.models import MilkCollection
from apps.finance.models import Expense, Payment
from apps.inventory.models import InventoryItem
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids
from apps.parties.models import Customer, Farmer

from .models import ExportJob, ImportBatch, SavedExportTemplate, ScheduledExport
from .services import MODULE_ROLES


def _require_owner_admin(membership):
    if membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        raise PermissionDenied


@login_required
@organization_access()
@require_POST
def save_export_template(request, organization_slug):
    module = request.POST.get("module", "")
    file_format = request.POST.get("file_format", "xlsx")
    if module not in MODULE_ROLES or request.membership.role not in MODULE_ROLES[module]:
        raise PermissionDenied
    if file_format not in {"csv", "xlsx", "pdf"}:
        messages.error(request, "Choose CSV, Excel or PDF.")
        return redirect("data_exports:centre", organization_slug=organization_slug)
    name = request.POST.get("name", "").strip()[:100]
    if not name:
        messages.error(request, "Enter a name for this export template.")
        return redirect("data_exports:centre", organization_slug=organization_slug)
    filters = {key: request.POST.get(key, "") for key in ("branch", "status", "from", "to")}
    template = SavedExportTemplate.objects.filter(organization=request.organization, name=name).first()
    if template and template.created_by_id != request.user.pk and request.membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        raise PermissionDenied
    created = template is None
    if created:
        template = SavedExportTemplate(organization=request.organization, name=name, created_by=request.user)
    template.module = module
    template.file_format = file_format
    template.filters = filters
    template.is_shared = request.POST.get("is_shared") == "on"
    template.save()
    record_event(actor=request.user, organization=request.organization,
                 action="export_template.created" if created else "export_template.updated",
                 target=template, request=request)
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
    if module not in MODULE_ROLES or frequency not in ScheduledExport.Frequency.values or file_format not in {"csv", "xlsx", "pdf"}:
        messages.error(request, "Choose a valid module, schedule and file format.")
        return redirect("data_exports:centre", organization_slug=organization_slug)
    if request.membership.role not in MODULE_ROLES[module]:
        raise PermissionDenied
    filters = {key: request.POST.get(key, "") for key in ("branch", "status", "from", "to")}
    now = timezone.now()
    first_run = now + (timedelta(days=1) if frequency == "daily" else timedelta(days=7) if frequency == "weekly" else timedelta(days=30))
    schedule = ScheduledExport.objects.create(
        organization=request.organization, created_by=request.user,
        name=request.POST.get("name", f"{module.title()} {frequency}")[:100],
        module=module, frequency=frequency, file_format=file_format,
        filters=filters, next_run_at=first_run,
    )
    record_event(actor=request.user, organization=request.organization,
                 action="export_schedule.created", target=schedule, request=request)
    messages.success(request, "Scheduled export created. Ensure the scheduler command runs periodically.")
    return redirect("data_exports:centre", organization_slug=organization_slug)


@login_required
@organization_access()
@require_POST
def toggle_schedule(request, organization_slug, schedule_id):
    schedule = get_object_or_404(ScheduledExport, pk=schedule_id, organization=request.organization)
    if schedule.created_by_id != request.user.pk and request.membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        raise PermissionDenied
    schedule.is_active = not schedule.is_active
    schedule.save(update_fields=["is_active", "updated_at"])
    record_event(actor=request.user, organization=request.organization,
                 action="export_schedule.toggled", target=schedule, changes={"is_active": schedule.is_active}, request=request)
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
        organization=request.organization, uploaded_by=request.user,
        module=module, file=upload,
    )
    record_event(actor=request.user, organization=request.organization,
                 action="import.uploaded", target=batch, request=request)
    messages.success(request, "CSV uploaded. Run the import worker to validate and process it.")
    return redirect("data_exports:centre", organization_slug=organization_slug)


@login_required
@organization_access()
@require_POST
def bulk_party_action(request, organization_slug, module):
    if module not in {"farmers", "customers"}:
        raise PermissionDenied
    if request.membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER}:
        raise PermissionDenied
    ids = request.POST.getlist("selected")
    if not ids or len(ids) > 500:
        messages.error(request, "Select between 1 and 500 records.")
        return redirect("parties:farmers" if module == "farmers" else "parties:customers", organization_slug=organization_slug)
    model = Farmer if module == "farmers" else Customer
    qs = model.objects.filter(organization=request.organization, deleted_at__isnull=True, pk__in=ids)
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None:
        qs = qs.filter(branch_id__in=branch_ids)
    action = request.POST.get("action")
    if action not in {"activate", "deactivate"}:
        messages.error(request, "Choose activate or deactivate.")
    else:
        changed = qs.update(is_active=(action == "activate"))
        record_event(actor=request.user, organization=request.organization,
                     action=f"{module}.bulk_{action}", changes={"record_count": changed}, request=request)
        messages.success(request, f"{changed} {module} records updated.")
    return redirect("parties:farmers" if module == "farmers" else "parties:customers", organization_slug=organization_slug)


@login_required
@organization_access()
def reports_dashboard(request, organization_slug):
    membership = request.membership
    if membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER, Membership.Role.ACCOUNTANT}:
        raise PermissionDenied
    branch_ids = accessible_branch_ids(membership)
    collections = MilkCollection.objects.filter(organization=request.organization)
    payments = Payment.objects.filter(organization=request.organization, deleted_at__isnull=True)
    expenses = Expense.objects.filter(organization=request.organization, deleted_at__isnull=True)
    inventory = InventoryItem.objects.filter(organization=request.organization, deleted_at__isnull=True)
    if branch_ids is not None:
        collections = collections.filter(branch_id__in=branch_ids)
        payments = payments.filter(branch_id__in=branch_ids)
        expenses = expenses.filter(branch_id__in=branch_ids)
        inventory = inventory.filter(branch_id__in=branch_ids)
    start = request.GET.get("from", "")
    end = request.GET.get("to", "")
    from datetime import date
    try:
        start_date = date.fromisoformat(start) if start else None
        end_date = date.fromisoformat(end) if end else None
        if start_date and end_date and start_date > end_date:
            raise ValueError
    except ValueError:
        messages.error(request, "Choose valid dates with the start date on or before the end date.")
        return redirect("data_exports:reports", organization_slug=organization_slug)
    if start_date:
        collections = collections.filter(collected_at__date__gte=start_date)
        payments = payments.filter(paid_at__date__gte=start_date)
        expenses = expenses.filter(expense_date__gte=start_date)
    if end_date:
        collections = collections.filter(collected_at__date__lte=end_date)
        payments = payments.filter(paid_at__date__lte=end_date)
        expenses = expenses.filter(expense_date__lte=end_date)
    approved = collections.filter(status=MilkCollection.Status.APPROVED)
    context = {
        "organization": request.organization, "date_from": start, "date_to": end,
        "collection_count": approved.count(),
        "milk_litres": approved.aggregate(v=Sum("quantity_litres"))["v"] or 0,
        "milk_value": approved.aggregate(v=Sum("total_amount"))["v"] or 0,
        "average_fat": approved.aggregate(v=Avg("fat"))["v"],
        "payments_total": payments.filter(status=Payment.Status.COMPLETED).aggregate(v=Sum("amount"))["v"] or 0,
        "expenses_total": expenses.filter(status=Expense.Status.APPROVED).aggregate(v=Sum("amount"))["v"] or 0,
        "low_stock_count": inventory.filter(current_stock__lte=models_field("reorder_level")).count(),
        "collection_statuses": collections.values("status").annotate(total=Count("id")).order_by("status"),
        "monthly_collections": approved.annotate(month=TruncMonth("collected_at")).values("month").annotate(litres=Sum("quantity_litres"), value=Sum("total_amount"), records=Count("id")).order_by("month"),
    }
    return render(request, "data_exports/reports.html", context)


def models_field(name):
    from django.db.models import F
    return F(name)


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN)
def import_sample(request, organization_slug, module):
    if module not in {"farmers", "customers"}:
        raise PermissionDenied
    response = HttpResponse(
        "code,full_name,phone,email,address,branch_code\r\nF-1001,Example Farmer,9800000000,farmer@example.com,Parasi,MAIN\r\n",
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="' + module + '-import-template.csv"'
    response["Cache-Control"] = "private, no-store"
    return response
