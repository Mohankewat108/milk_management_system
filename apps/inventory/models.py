from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Branch, Organization


class Supplier(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="suppliers"
    )
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=180)
    contact_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    tax_number = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uniq_supplier_code_org")
        ]
        indexes = [models.Index(fields=["organization", "is_active"])]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class InventoryItem(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="inventory_items"
    )
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="inventory_items")
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="items"
    )
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80, blank=True)
    unit = models.CharField(max_length=20, default="unit")
    current_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    reorder_level = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    purchase_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="uniq_inventory_code_org"
            ),
            models.CheckConstraint(
                condition=models.Q(current_stock__gte=0), name="inventory_stock_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(reorder_level__gte=0), name="inventory_reorder_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(purchase_price__gte=0), name="inventory_price_nonnegative"
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "branch", "is_active"]),
            models.Index(fields=["organization", "current_stock"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class StockMovement(UUIDModel, TimeStampedModel):
    class Kind(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        USAGE = "usage", "Usage"
        TRANSFER_IN = "transfer_in", "Transfer in"
        TRANSFER_OUT = "transfer_out", "Transfer out"
        ADJUSTMENT = "adjustment", "Adjustment"
        RETURN = "return", "Return"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="stock_movements"
    )
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=3)
    reason = models.CharField(max_length=240)
    reference = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_movements"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["item", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(quantity_delta__gt=0, kind__in=["purchase", "transfer_in", "return"])
                    | models.Q(quantity_delta__lt=0, kind__in=["usage", "transfer_out"])
                    | (models.Q(kind="adjustment") & ~models.Q(quantity_delta=0))
                ),
                name="stock_movement_kind_sign",
            ),
        ]
