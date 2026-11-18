from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Branch, Organization
from apps.parties.models import Customer, Farmer
from apps.pricing.models import PricingConfiguration


class MilkCollection(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REVERSED = "reversed", "Reversed"

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="milk_collections")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="milk_collections")
    reference = models.CharField(max_length=40)
    farmer = models.ForeignKey(Farmer, on_delete=models.PROTECT, null=True, blank=True, related_name="collections")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, null=True, blank=True, related_name="collections")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_milk_collections")
    collected_at = models.DateTimeField(db_index=True)
    quantity_litres = models.DecimalField(max_digits=12, decimal_places=3)
    snf = models.DecimalField(max_digits=7, decimal_places=3)
    fat = models.DecimalField(max_digits=7, decimal_places=3)
    lactose = models.DecimalField(max_digits=7, decimal_places=3)
    milk_rate = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    pricing = models.ForeignKey(PricingConfiguration, on_delete=models.PROTECT, related_name="collections")
    pricing_snapshot = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "reference"], name="uniq_collection_ref_org"),
            models.CheckConstraint(condition=Q(quantity_litres__gt=0), name="collection_quantity_positive"),
            models.CheckConstraint(
                condition=(Q(farmer__isnull=False, customer__isnull=True) | Q(farmer__isnull=True, customer__isnull=False)),
                name="collection_exactly_one_party",
            ),
            models.CheckConstraint(
                condition=Q(snf__gte=0) & Q(fat__gte=0) & Q(lactose__gte=0),
                name="collection_quality_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "collected_at"]),
            models.Index(fields=["organization", "branch", "status"]),
        ]

    def __str__(self) -> str:
        return self.reference
