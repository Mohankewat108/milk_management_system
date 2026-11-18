from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Branch, Organization


class PricingConfiguration(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="pricing_configurations")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True, related_name="pricing_configurations")
    version = models.PositiveIntegerField()
    snf_rate = models.DecimalField(max_digits=12, decimal_places=4)
    fat_rate = models.DecimalField(max_digits=12, decimal_places=4)
    lactose_rate = models.DecimalField(max_digits=12, decimal_places=4)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_pricing_configurations")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "version"], name="uniq_pricing_version_org"),
            models.CheckConstraint(condition=Q(effective_to__isnull=True) | Q(effective_to__gte=models.F("effective_from")), name="pricing_effective_range_valid"),
            models.CheckConstraint(condition=Q(snf_rate__gte=0) & Q(fat_rate__gte=0) & Q(lactose_rate__gte=0), name="pricing_rates_nonnegative"),
        ]
        ordering = ["-effective_from", "-version"]

    def __str__(self) -> str:
        return f"{self.organization.name} · v{self.version}"
