from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Branch, Organization


class InventoryItem(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="inventory_items")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="inventory_items")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    unit = models.CharField(max_length=20, default="unit")
    current_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    reorder_level = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    purchase_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="uniq_inventory_code_org")]
        indexes = [models.Index(fields=["organization", "branch", "is_active"])]


class StockMovement(UUIDModel, TimeStampedModel):
    class Kind(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        USAGE = "usage", "Usage"
        TRANSFER_IN = "transfer_in", "Transfer in"
        TRANSFER_OUT = "transfer_out", "Transfer out"
        ADJUSTMENT = "adjustment", "Adjustment"
        RETURN = "return", "Return"

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="stock_movements")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=3)
    reason = models.CharField(max_length=240)
    reference = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_movements")
