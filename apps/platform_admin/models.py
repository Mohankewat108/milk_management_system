from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Organization


class SubscriptionPlan(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=40, unique=True)
    description = models.TextField(blank=True)
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2)
    annual_price = models.DecimalField(max_digits=12, decimal_places=2)
    max_branches = models.PositiveIntegerField(default=1)
    max_staff = models.PositiveIntegerField(default=5)
    max_customers = models.PositiveIntegerField(default=100)
    features = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["monthly_price"]


class Subscription(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIAL)
    starts_at = models.DateField()
    ends_at = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["organization", "status"]), models.Index(fields=["status", "ends_at"])]
