import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from organizations.models import Organisation, Branch


class TenantModel(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Customer(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='customer_profile')
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='customers')
    name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=32)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    village = models.CharField(max_length=100, blank=True)
    ward = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organisation', 'phone_number'], name='unique_customer_phone_per_org')]
        indexes = [models.Index(fields=['organisation', 'branch']), models.Index(fields=['organisation', 'name'])]

    def __str__(self):
        return self.name


class Farmer(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='farmer_profile')
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='farmers')
    name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=32)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organisation', 'phone_number'], name='unique_farmer_phone_per_org')]


class StaffMember(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='staff_profiles')
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='staff')
    employee_code = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organisation', 'employee_code'], name='unique_staff_code_per_org')]


class PricingConfiguration(TenantModel):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='pricing_configs')
    snf_rate = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(Decimal('0'))])
    fat_rate = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(Decimal('0'))])
    lacto_rate = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(Decimal('0'))])
    effective_from = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['branch', 'effective_from'], name='unique_pricing_per_branch_date')]
        indexes = [models.Index(fields=['organisation', 'branch', 'effective_from'])]


class MilkCollection(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='collections')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='collections')
    farmer = models.ForeignKey(Farmer, on_delete=models.SET_NULL, null=True, blank=True, related_name='collections')
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='recorded_collections')
    milk_liters = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    snf = models.DecimalField(max_digits=8, decimal_places=3, validators=[MinValueValidator(Decimal('0'))])
    fat = models.DecimalField(max_digits=8, decimal_places=3, validators=[MinValueValidator(Decimal('0'))])
    lacto = models.DecimalField(max_digits=8, decimal_places=3, validators=[MinValueValidator(Decimal('0'))])
    milk_rate = models.DecimalField(max_digits=12, decimal_places=4)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    collection_date = models.DateField(db_index=True)
    correction_reason = models.TextField(blank=True)
    is_void = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['organisation', 'collection_date']),
            models.Index(fields=['organisation', 'customer']),
            models.Index(fields=['organisation', 'branch']),
        ]


class Payment(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='payments')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, null=True, blank=True, related_name='payments')
    farmer = models.ForeignKey(Farmer, on_delete=models.PROTECT, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateField(db_index=True)
    reference = models.CharField(max_length=100, blank=True)
    method = models.CharField(max_length=30, default='cash')
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=['organisation', 'payment_date']), models.Index(fields=['organisation', 'customer'])]


class Expense(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='expenses')
    category = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    expense_date = models.DateField(db_index=True)
    vendor = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    notes = models.TextField(blank=True)


class Supplier(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)


class InventoryItem(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='inventory_items')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    sku = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    unit = models.CharField(max_length=30, default='unit')
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0'))
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organisation', 'branch', 'sku'], name='unique_inventory_sku_per_branch')]


class StockMovement(TenantModel):
    class Movement(models.TextChoices):
        IN = 'in', 'Stock In'
        OUT = 'out', 'Stock Out'
        ADJUSTMENT = 'adjustment', 'Adjustment'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='movements')
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=Movement.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    movement_date = models.DateField(db_index=True)
    notes = models.TextField(blank=True)


class SupportTicket(TenantModel):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In Progress'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED = 'closed', 'Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='support_tickets')


class Notification(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
