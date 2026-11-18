from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import F
from django.db.models.lookups import LessThanOrEqual
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids

from .forms import InventoryItemForm, StockMovementForm, SupplierForm
from .models import InventoryItem, StockMovement, Supplier
from .services import move_stock


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.INVENTORY_MANAGER)
def item_list(request, organization_slug):
    organization = request.organization
    items = InventoryItem.objects.filter(organization=organization, is_active=True).select_related("branch", "supplier")
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None:
        items = items.filter(branch_id__in=branch_ids)
    items = items.annotate(is_low=LessThanOrEqual(F("current_stock"), F("reorder_level"))).order_by("name")
    return render(request, "inventory/items.html", {"organization": organization, "items": items})


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.INVENTORY_MANAGER)
@require_http_methods(["GET", "POST"])
def item_create(request, organization_slug):
    organization = request.organization
    form = InventoryItemForm(
        request.POST or None, organization=organization, membership=request.membership
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.organization = organization
        item.save()
        record_event(actor=request.user, organization=organization, action="inventory.item_created",
                     target=item, request=request)
        messages.success(request, f"Inventory item {item.name} created.")
        return redirect("inventory:items", organization_slug=organization_slug)
    return render(request, "inventory/item_form.html", {"organization": organization, "form": form})


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.INVENTORY_MANAGER)
@require_http_methods(["GET", "POST"])
def movement_create(request, organization_slug):
    organization = request.organization
    form = StockMovementForm(
        request.POST or None, organization=organization, membership=request.membership
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            movement = move_stock(
                item_id=data["item"].pk,
                organization=organization,
                actor=request.user,
                kind=data["kind"],
                quantity=data["quantity"],
                reason=data["reason"],
                reference=data["reference"],
            )
        except (ValidationError, InventoryItem.DoesNotExist) as exc:
            form.add_error(None, exc)
        else:
            record_event(actor=request.user, organization=organization,
                         action="inventory.stock_moved", target=movement, request=request)
            messages.success(request, "Stock movement recorded.")
            return redirect("inventory:items", organization_slug=organization_slug)
    return render(request, "inventory/movement_form.html", {"organization": organization, "form": form})


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN)
@require_http_methods(["GET", "POST"])
def supplier_list(request, organization_slug):
    organization = request.organization
    form = SupplierForm(request.POST or None, organization=organization)
    if request.method == "POST" and form.is_valid():
        supplier = form.save(commit=False)
        supplier.organization = organization
        supplier.save()
        record_event(actor=request.user, organization=organization, action="supplier.created",
                     target=supplier, request=request)
        messages.success(request, f"Supplier {supplier.name} created.")
        return redirect("inventory:suppliers", organization_slug=organization_slug)
    suppliers = Supplier.objects.filter(organization=organization).order_by("name")
    return render(request, "inventory/suppliers.html", {
        "organization": organization, "form": form, "suppliers": suppliers,
    })
