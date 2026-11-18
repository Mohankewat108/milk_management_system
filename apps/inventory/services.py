from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import InventoryItem, StockMovement


INCREASING_MOVEMENTS = {
    StockMovement.Kind.PURCHASE,
    StockMovement.Kind.TRANSFER_IN,
    StockMovement.Kind.RETURN,
}
DECREASING_MOVEMENTS = {
    StockMovement.Kind.USAGE,
    StockMovement.Kind.TRANSFER_OUT,
}


@transaction.atomic
def move_stock(*, item_id, organization, actor, kind, quantity, reason, reference=""):
    item = InventoryItem.objects.select_for_update().get(
        pk=item_id, organization=organization, is_active=True
    )
    if item.branch.organization_id != organization.id:
        raise ValidationError("The item branch does not belong to this organisation.")
    amount = Decimal(str(quantity))
    if amount <= 0:
        raise ValidationError("Movement quantity must be greater than zero.")
    if kind in INCREASING_MOVEMENTS:
        delta = amount
    elif kind in DECREASING_MOVEMENTS:
        delta = -amount
    elif kind == StockMovement.Kind.ADJUSTMENT:
        raise ValidationError("Use an explicit positive or negative adjustment amount.")
    else:
        raise ValidationError("Unsupported stock movement type.")

    new_balance = item.current_stock + delta
    if new_balance < 0:
        raise ValidationError("This movement would make stock negative.")
    item.current_stock = new_balance
    item.save(update_fields=["current_stock", "updated_at"])
    return StockMovement.objects.create(
        organization=organization,
        item=item,
        kind=kind,
        quantity_delta=delta,
        reason=reason,
        reference=reference,
        created_by=actor,
    )


@transaction.atomic
def adjust_stock(*, item_id, organization, actor, signed_delta, reason, reference=""):
    item = InventoryItem.objects.select_for_update().get(
        pk=item_id, organization=organization, is_active=True
    )
    delta = Decimal(str(signed_delta))
    if delta == 0:
        raise ValidationError("Adjustment quantity cannot be zero.")
    new_balance = item.current_stock + delta
    if new_balance < 0:
        raise ValidationError("This adjustment would make stock negative.")
    item.current_stock = new_balance
    item.save(update_fields=["current_stock", "updated_at"])
    return StockMovement.objects.create(
        organization=organization,
        item=item,
        kind=StockMovement.Kind.ADJUSTMENT,
        quantity_delta=delta,
        reason=reason,
        reference=reference,
        created_by=actor,
    )
