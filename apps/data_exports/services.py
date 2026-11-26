import csv
import io
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F, Q
from django.utils import timezone

from apps.collections.models import MilkCollection
from apps.finance.models import Expense, Payment
from apps.inventory.models import InventoryItem, Supplier
from apps.organizations.models import Branch, Membership
from apps.organizations.permissions import accessible_branch_ids, has_organization_permission
from apps.parties.models import Customer, Farmer

MAX_SYNC_EXPORT_ROWS = 20000

MODULE_ROLES = {
    "farmers": {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.BRANCH_MANAGER,
        Membership.Role.SUPPORT,
    },
    "customers": {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.BRANCH_MANAGER,
        Membership.Role.SUPPORT,
    },
    "collections": {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.BRANCH_MANAGER,
        Membership.Role.COLLECTION_OPERATOR,
        Membership.Role.QUALITY_OFFICER,
    },
    "payments": {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ACCOUNTANT},
    "expenses": {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ACCOUNTANT},
    "inventory": {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.INVENTORY_MANAGER},
    "suppliers": {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.INVENTORY_MANAGER},
    "reports": {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.BRANCH_MANAGER,
        Membership.Role.ACCOUNTANT,
    },
}


def can_export_module(membership, module):
    """Return whether a member may export a module under current role/capability grants."""
    if module not in MODULE_ROLES:
        return False
    if membership.role in MODULE_ROLES[module]:
        return True
    return membership.role == Membership.Role.DAIRY_MANAGER and has_organization_permission(
        membership, "exports.create"
    )


def _scoped_queryset(module, organization, membership, params, branch_scope=None):
    branch_ids = accessible_branch_ids(membership)
    if branch_ids is not None:
        branch_ids = list(
            Branch.objects.filter(
                organization=organization,
                pk__in=branch_ids,
                is_active=True,
                deleted_at__isnull=True,
            ).values_list("pk", flat=True)
        )
    branch_ids_requested = params.getlist("branch") if hasattr(params, "getlist") else []
    branch_id = params.get("branch", "").strip()
    if branch_id and not branch_ids_requested:
        branch_ids_requested = [branch_id]
    if branch_ids_requested:
        allowed_values = {
            str(value)
            for value in (
                branch_ids
                or Branch.objects.filter(
                    organization=organization, is_active=True, deleted_at__isnull=True
                ).values_list("pk", flat=True)
            )
        }
        if any(str(value) not in allowed_values for value in branch_ids_requested):
            raise PermissionDenied("You are not allowed to export one or more selected branches.")

    if module == "farmers":
        qs = Farmer.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).select_related("branch", "user")
        date_field = "created_at__date"
    elif module == "customers":
        qs = Customer.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).select_related("branch", "user")
        date_field = "created_at__date"
    elif module == "collections":
        qs = MilkCollection.objects.filter(organization=organization).select_related(
            "branch", "farmer", "customer", "recorded_by", "tested_by"
        )
        date_field = "collected_at__date"
    elif module == "payments":
        qs = Payment.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).select_related("branch", "farmer", "customer", "recorded_by")
        date_field = "paid_at__date"
    elif module == "expenses":
        qs = Expense.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).select_related("branch", "recorded_by", "approved_by")
        date_field = "expense_date"
    elif module == "inventory":
        qs = InventoryItem.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).select_related("branch", "supplier")
        date_field = "created_at__date"
    elif module == "suppliers":
        qs = Supplier.objects.filter(organization=organization, deleted_at__isnull=True)
        date_field = "created_at__date"
    elif module == "reports":
        qs = MilkCollection.objects.filter(organization=organization).select_related(
            "branch", "farmer", "customer", "recorded_by", "tested_by"
        )
        date_field = "collected_at__date"
    else:
        raise ValidationError("Unsupported export category.")

    if branch_ids is not None and module != "suppliers":
        qs = qs.filter(branch_id__in=branch_ids)
    if branch_scope is not None and module != "suppliers":
        scope_branch_ids = [value for value in branch_scope if value is not None]
        scope_filter = Q(branch_id__in=scope_branch_ids)
        if None in branch_scope:
            scope_filter |= Q(branch__isnull=True)
        qs = qs.filter(scope_filter)
    # Collection integrity: never export/report an entry if its farmer/customer
    # has since been moved to another branch or has no branch assignment.
    if module in {"collections", "reports"}:
        qs = qs.filter(
            (Q(farmer__isnull=False) & Q(farmer__branch_id=F("branch_id")))
            | (Q(customer__isnull=False) & Q(customer__branch_id=F("branch_id")))
        )
    if branch_ids_requested and module != "suppliers":
        qs = qs.filter(branch_id__in=branch_ids_requested)
    shift = params.get("shift", "").strip()
    if shift in {"morning", "evening"} and module in {"collections", "reports"}:
        qs = qs.filter(shift=shift)
    if params.get("farmer") and module in {"collections", "reports"}:
        qs = qs.filter(farmer_id=params.get("farmer"))
    if params.get("customer") and module in {"collections", "reports"}:
        qs = qs.filter(customer_id=params.get("customer"))
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
        headers = [
            "ID",
            "Code",
            "Name",
            "Phone",
            "Email",
            "Address",
            "Branch",
            "Active",
            "Registered at",
            "Portal account",
        ]
        rows = (
            [
                str(obj.pk),
                obj.code,
                obj.full_name,
                obj.phone,
                obj.email,
                obj.address,
                obj.branch.name if obj.branch else "",
                obj.is_active,
                obj.created_at,
                bool(obj.user_id),
            ]
            for obj in qs.iterator(chunk_size=1000)
        )
        return headers, rows
    if module in {"collections", "reports"}:
        headers = [
            "ID",
            "Reference",
            "Farmer",
            "Customer",
            "Branch",
            "Collected at",
            "Shift",
            "Quantity (L)",
            "FAT",
            "SNF",
            "Lactose",
            "Milk temperature (C)",
            "Rate",
            "Total",
            "Status",
            "Recorded by",
            "Tested by",
        ]
        rows = (
            [
                str(obj.pk),
                obj.reference,
                _party_name(obj.farmer),
                _party_name(obj.customer),
                obj.branch.name,
                obj.collected_at,
                obj.get_shift_display(),
                obj.quantity_litres,
                obj.fat,
                obj.snf,
                obj.lactose,
                obj.milk_temperature_c,
                obj.milk_rate,
                obj.total_amount,
                obj.get_status_display(),
                obj.recorded_by.get_username(),
                obj.tested_by.get_username() if obj.tested_by else "",
            ]
            for obj in qs.iterator(chunk_size=1000)
        )
        return headers, rows
    if module == "payments":
        headers = [
            "ID",
            "Reference",
            "Date",
            "Direction",
            "Farmer",
            "Customer",
            "Branch",
            "Method",
            "Currency",
            "Amount",
            "Status",
            "Transaction reference",
            "Notes",
            "Recorded by",
        ]
        rows = (
            [
                str(obj.pk),
                obj.reference,
                obj.paid_at,
                obj.get_direction_display(),
                _party_name(obj.farmer),
                _party_name(obj.customer),
                obj.branch.name,
                obj.get_method_display(),
                obj.currency,
                obj.amount,
                obj.get_status_display(),
                obj.transaction_reference,
                obj.notes,
                obj.recorded_by.get_username(),
            ]
            for obj in qs.iterator(chunk_size=1000)
        )
        return headers, rows
    if module == "expenses":
        headers = [
            "ID",
            "Reference",
            "Date",
            "Category",
            "Description",
            "Supplier",
            "Branch",
            "Currency",
            "Amount",
            "Method",
            "Status",
            "Recorded by",
            "Approved by",
            "Approved at",
            "Notes",
        ]
        rows = (
            [
                str(obj.pk),
                obj.reference,
                obj.expense_date,
                obj.category,
                obj.description,
                obj.supplier_name,
                obj.branch.name,
                obj.currency,
                obj.amount,
                obj.get_method_display(),
                obj.get_status_display(),
                obj.recorded_by.get_username(),
                obj.approved_by.get_username() if obj.approved_by else "",
                obj.approved_at,
                obj.notes,
            ]
            for obj in qs.iterator(chunk_size=1000)
        )
        return headers, rows
    if module == "suppliers":
        headers = [
            "ID",
            "Code",
            "Name",
            "Contact",
            "Phone",
            "Email",
            "Address",
            "Tax number",
            "Active",
            "Created at",
        ]
        rows = (
            [
                str(obj.pk),
                obj.code,
                obj.name,
                obj.contact_name,
                obj.phone,
                obj.email,
                obj.address,
                obj.tax_number,
                obj.is_active,
                obj.created_at,
            ]
            for obj in qs.iterator(chunk_size=1000)
        )
        return headers, rows
    headers = [
        "ID",
        "Code",
        "Name",
        "Category",
        "Branch",
        "Supplier",
        "Unit",
        "Current stock",
        "Reorder level",
        "Purchase price",
        "Active",
        "Updated at",
    ]
    rows = (
        [
            str(obj.pk),
            obj.code,
            obj.name,
            obj.category,
            obj.branch.name,
            obj.supplier.name if obj.supplier else "",
            obj.unit,
            obj.current_stock,
            obj.reorder_level,
            obj.purchase_price,
            obj.is_active,
            obj.updated_at,
        ]
        for obj in qs.iterator(chunk_size=1000)
    )
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


def _export_totals(module):
    return {"count": 0, "sums": {}, "value_counts": {}, "stock_value": Decimal("0")}


def _numeric_columns(module):
    # Column indexes are based on the export row schema returned by _rows().
    return {
        "collections": {
            7: "Quantity (L)",
            8: "FAT",
            9: "SNF",
            10: "Lactose",
            11: "Milk temperature (C)",
            12: "Rate",
            13: "Total amount",
        },
        "reports": {
            7: "Quantity (L)",
            8: "FAT",
            9: "SNF",
            10: "Lactose",
            11: "Milk temperature (C)",
            12: "Rate",
            13: "Total amount",
        },
        "payments": {9: "Amount"},
        "expenses": {8: "Amount"},
        "inventory": {7: "Current stock", 8: "Reorder level", 9: "Purchase price"},
    }.get(module, {})


def _accumulate_export_totals(module, row, totals):
    totals["count"] += 1
    for index in _numeric_columns(module):
        value = row[index]
        if value in (None, ""):
            continue
        totals["sums"][index] = totals["sums"].get(index, Decimal("0")) + Decimal(str(value))
        totals["value_counts"][index] = totals["value_counts"].get(index, 0) + 1
    if module == "inventory":
        totals["stock_value"] += Decimal(str(row[7] or 0)) * Decimal(str(row[9] or 0))


def _export_summary_rows(module, headers, totals):
    count = totals["count"]
    averages = [""] * len(headers)
    grand_total = [""] * len(headers)
    averages[0] = "AVERAGE"
    grand_total[0] = f"GRAND TOTAL — {count} RECORDS"

    for index in _numeric_columns(module):
        total = totals["sums"].get(index, Decimal("0"))
        field_count = totals["value_counts"].get(index, 0)
        averages[index] = (total / field_count).quantize(Decimal("0.01")) if field_count else ""

    if module in {"collections", "reports"}:
        grand_total[7] = totals["sums"].get(7, Decimal("0"))
        grand_total[13] = totals["sums"].get(13, Decimal("0"))
    elif module == "payments":
        grand_total[9] = totals["sums"].get(9, Decimal("0"))
    elif module == "expenses":
        grand_total[8] = totals["sums"].get(8, Decimal("0"))
    elif module == "inventory":
        grand_total[7] = totals["sums"].get(7, Decimal("0"))
        grand_total[9] = totals["stock_value"]
        grand_total[0] = f"TOTAL STOCK VALUE — {count} ITEMS"
    elif module in {"farmers", "customers", "suppliers"}:
        grand_total[0] = f"TOTAL RECORDS — {count}"

    return [grand_total, averages]


def build_csv(module, queryset):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    headers, rows = _rows(module, queryset)
    writer.writerow(headers)
    count = 0
    totals = _export_totals(module)
    for row in rows:
        count += 1
        if count > MAX_SYNC_EXPORT_ROWS:
            raise ValidationError(
                "This export is larger than the safe instant-export limit. "
                "Background exports will be available in a later phase."
            )
        _accumulate_export_totals(module, row, totals)
        writer.writerow([_safe_cell(value) for value in row])
    for summary_row in _export_summary_rows(module, headers, totals):
        writer.writerow([_safe_cell(value) for value in summary_row])
    return "\ufeff" + buffer.getvalue(), count


def export_queryset(*, module, organization, membership, params, branch_scope=None):
    if not can_export_module(membership, module):
        raise PermissionDenied("You do not have permission to export this category.")
    return _scoped_queryset(module, organization, membership, params, branch_scope=branch_scope)
