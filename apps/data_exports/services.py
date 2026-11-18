import csv
import io
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.collections.models import MilkCollection
from apps.finance.models import Expense, Payment
from apps.inventory.models import InventoryItem, Supplier
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids
from apps.parties.models import Customer, Farmer


MAX_SYNC_EXPORT_ROWS = 20000

MODULE_ROLES = {
    "farmers": {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER, Membership.Role.SUPPORT},
    "customers": {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER, Membership.Role.SUPPORT},
    "collections": {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER, Membership.Role.COLLECTION_OPERATOR, Membership.Role.QUALITY_OFFICER},
    "payments": {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ACCOUNTANT},
    "expenses": {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ACCOUNTANT},
    "inventory": {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.INVENTORY_MANAGER},
    "suppliers": {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.INVENTORY_MANAGER},
}


def _scoped_queryset(module, organization, membership, params):
    branch_ids = accessible_branch_ids(membership)
    branch_id = params.get("branch", "").strip()
    if branch_id:
        if branch_ids is not None and str(branch_id) not in {str(value) for value in branch_ids}:
            raise PermissionDenied("You are not allowed to export this branch.")

    if module == "farmers":
        qs = Farmer.objects.filter(organization=organization, deleted_at__isnull=True).select_related("branch", "user")
        date_field = "created_at__date"
    elif module == "customers":
        qs = Customer.objects.filter(organization=organization, deleted_at__isnull=True).select_related("branch", "user")
        date_field = "created_at__date"
    elif module == "collections":
        qs = MilkCollection.objects.filter(organization=organization).select_related("branch", "farmer", "customer", "recorded_by", "tested_by")
        date_field = "collected_at__date"
    elif module == "payments":
        qs = Payment.objects.filter(organization=organization, deleted_at__isnull=True).select_related("branch", "farmer", "customer", "recorded_by")
        date_field = "paid_at__date"
    elif module == "expenses":
        qs = Expense.objects.filter(organization=organization, deleted_at__isnull=True).select_related("branch", "recorded_by", "approved_by")
        date_field = "expense_date"
    elif module == "inventory":
        qs = InventoryItem.objects.filter(organization=organization, deleted_at__isnull=True).select_related("branch", "supplier")
        date_field = "created_at__date"
    elif module == "suppliers":
        qs = Supplier.objects.filter(organization=organization, deleted_at__isnull=True)
        date_field = "created_at__date"
    else:
        raise ValidationError("Unsupported export category.")

    if branch_ids is not None and module != "suppliers":
        qs = qs.filter(branch_id__in=branch_ids)
    if branch_id and module != "suppliers":
        qs = qs.filter(branch_id=branch_id)
    if params.get("status"):
        if module in {"farmers", "customers"}:
            if params["status"] in {"active", "inactive"}:
                qs = qs.filter(is_active=(params["status"] == "active"))
        elif hasattr(qs.model, "status"):
            qs = qs.filter(status=params["status"])
    if params.get("from"):
        try:
            date_from = date.fromisoformat(params["from"])
        except ValueError as exc:
            raise ValidationError("Start date must use YYYY-MM-DD.") from exc
        qs = qs.filter(**{f"{date_field}__gte": date_from})
    if params.get("to"):
        try:
            date_to = date.fromisoformat(params["to"])
        except ValueError as exc:
            raise ValidationError("End date must use YYYY-MM-DD.") from exc
        qs = qs.filter(**{f"{date_field}__lte": date_to})
    if params.get("from") and params.get("to") and params["from"] > params["to"]:
        raise ValidationError("Start date must be on or before end date.")
    selected = [value for value in params.getlist("selected") if value]
    if selected:
        qs = qs.filter(pk__in=selected)
    return qs.order_by("pk")


def _party_name(party):
    return party.full_name if party else ""


def _rows(module, qs):
    if module in {"farmers", "customers"}:
        headers = ["ID", "Code", "Name", "Phone", "Email", "Address", "Branch", "Active", "Registered at", "Portal account"]
        rows = ([str(obj.pk), obj.code, obj.full_name, obj.phone, obj.email, obj.address,
                 obj.branch.name if obj.branch else "", obj.is_active, obj.created_at, bool(obj.user_id)]
                for obj in qs.iterator(chunk_size=1000))
        return headers, rows
    if module == "collections":
        headers = ["ID", "Reference", "Farmer", "Customer", "Branch", "Collected at", "Quantity (L)", "FAT", "SNF", "Lactose", "Milk temperature (C)", "Rate", "Total", "Status", "Recorded by", "Tested by"]
        rows = ([str(obj.pk), obj.reference, _party_name(obj.farmer), _party_name(obj.customer), obj.branch.name,
                 obj.collected_at, obj.quantity_litres, obj.fat, obj.snf, obj.lactose, obj.milk_temperature_c,
                 obj.milk_rate, obj.total_amount, obj.get_status_display(), obj.recorded_by.get_username(),
                 obj.tested_by.get_username() if obj.tested_by else ""]
                for obj in qs.iterator(chunk_size=1000))
        return headers, rows
    if module == "payments":
        headers = ["ID", "Reference", "Date", "Direction", "Farmer", "Customer", "Branch", "Method", "Currency", "Amount", "Status", "Transaction reference", "Notes", "Recorded by"]
        rows = ([str(obj.pk), obj.reference, obj.paid_at, obj.get_direction_display(), _party_name(obj.farmer),
                 _party_name(obj.customer), obj.branch.name, obj.get_method_display(), obj.currency, obj.amount,
                 obj.get_status_display(), obj.transaction_reference, obj.notes, obj.recorded_by.get_username()]
                for obj in qs.iterator(chunk_size=1000))
        return headers, rows
    if module == "expenses":
        headers = ["ID", "Reference", "Date", "Category", "Description", "Supplier", "Branch", "Currency", "Amount", "Method", "Status", "Recorded by", "Approved by", "Approved at", "Notes"]
        rows = ([str(obj.pk), obj.reference, obj.expense_date, obj.category, obj.description, obj.supplier_name,
                 obj.branch.name, obj.currency, obj.amount, obj.get_method_display(), obj.get_status_display(),
                 obj.recorded_by.get_username(), obj.approved_by.get_username() if obj.approved_by else "",
                 obj.approved_at, obj.notes]
                for obj in qs.iterator(chunk_size=1000))
        return headers, rows
    if module == "suppliers":
        headers = ["ID", "Code", "Name", "Contact", "Phone", "Email", "Address", "Tax number", "Active", "Created at"]
        rows = ([str(obj.pk), obj.code, obj.name, obj.contact_name, obj.phone, obj.email,
                 obj.address, obj.tax_number, obj.is_active, obj.created_at]
                for obj in qs.iterator(chunk_size=1000))
        return headers, rows
    headers = ["ID", "Code", "Name", "Category", "Branch", "Supplier", "Unit", "Current stock", "Reorder level", "Purchase price", "Active", "Updated at"]
    rows = ([str(obj.pk), obj.code, obj.name, obj.category, obj.branch.name,
             obj.supplier.name if obj.supplier else "", obj.unit, obj.current_stock,
             obj.reorder_level, obj.purchase_price, obj.is_active, obj.updated_at]
            for obj in qs.iterator(chunk_size=1000))
    return headers, rows


def _safe_cell(value):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        if isinstance(value, datetime) and timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + value
    return value


def build_csv(module, queryset):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    headers, rows = _rows(module, queryset)
    writer.writerow(headers)
    count = 0
    for row in rows:
        count += 1
        if count > MAX_SYNC_EXPORT_ROWS:
            raise ValidationError("This export is larger than the safe instant-export limit. Background exports will be available in a later phase.")
        writer.writerow([_safe_cell(value) for value in row])
    return "\ufeff" + buffer.getvalue(), count


def export_queryset(*, module, organization, membership, params):
    if module not in MODULE_ROLES or membership.role not in MODULE_ROLES[module]:
        raise PermissionDenied("You do not have permission to export this category.")
    return _scoped_queryset(module, organization, membership, params)
