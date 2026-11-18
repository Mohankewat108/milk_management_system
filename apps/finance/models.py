from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Branch, Organization
from apps.parties.models import Customer, Farmer


class Payment(UUIDModel, TimeStampedModel):
    class Direction(models.TextChoices):
        INCOMING = "incoming", "Incoming"
        OUTGOING = "outgoing", "Outgoing"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank_transfer", "Bank transfer"
        MOBILE = "mobile_wallet", "Mobile wallet"
        ONLINE = "online", "Online"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REVERSED = "reversed", "Reversed"

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="payments")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="payments")
    reference = models.CharField(max_length=48)
    direction = models.CharField(max_length=12, choices=Direction.choices)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, null=True, blank=True, related_name="payments")
    farmer = models.ForeignKey(Farmer, on_delete=models.PROTECT, null=True, blank=True, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    method = models.CharField(max_length=20, choices=Method.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    transaction_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_payments")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "reference"], name="uniq_payment_reference_org"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
            models.CheckConstraint(
                condition=(Q(customer__isnull=False, farmer__isnull=True) | Q(customer__isnull=True, farmer__isnull=False)),
                name="payment_exactly_one_party",
            ),
        ]
        indexes = [models.Index(fields=["organization", "paid_at"]), models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return self.reference


class Expense(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="expenses")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="expenses")
    reference = models.CharField(max_length=48)
    category = models.CharField(max_length=80)
    description = models.CharField(max_length=240)
    supplier_name = models.CharField(max_length=180, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    expense_date = models.DateField(db_index=True)
    method = models.CharField(max_length=20, choices=Payment.Method.choices, default=Payment.Method.CASH)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_expenses")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_expenses")
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "reference"], name="uniq_expense_reference_org"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="expense_amount_positive"),
        ]
        indexes = [models.Index(fields=["organization", "expense_date"]), models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return self.reference
