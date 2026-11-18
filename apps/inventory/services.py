from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import InventoryItem, StockMovement


@transaction.atomic
def move_stock(*, item_id, organization, actor, kind, quantity_delta, reason, reference=""):
    item = InventoryItem.objects.select_for_update().get(pk=item_id, organization=organization)
    delta = Decimal(str(quantity_delta))
    if delta == 0:
        raise ValidationError("Stock movement quantity cannot be zero.")
    new_balance = item.current_stock + delta
    if new_balance < 0:
        raise ValidationError("This movement would make stock negative.")
    item.current_stock = new_balance
    item.save(update_fields=["current_stock", "updated_at"])
    return StockMovement.objects.create(
        organization=organization, item=item, kind=kind, quantity_delta=delta,
        reason=reason, reference=reference, created_by=actor,
    )
