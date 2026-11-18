from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Branch, Organization


class Customer(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="customers")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="customers")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_profile")
    code = models.CharField(max_length=40)
    full_name = models.CharField(max_length=180)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    village = models.CharField(max_length=100, blank=True)
    ward = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="deleted_customers")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="uniq_customer_code_org")]
        indexes = [models.Index(fields=["organization", "full_name"]), models.Index(fields=["organization", "is_active"])]

    def __str__(self) -> str:
        return f"{self.code} · {self.full_name}"


class Farmer(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="farmers")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="farmers")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="farmer_profile")
    code = models.CharField(max_length=40)
    full_name = models.CharField(max_length=180)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    bank_account_name = models.CharField(max_length=160, blank=True)
    bank_account_number = models.CharField(max_length=80, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="deleted_farmers")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="uniq_farmer_code_org")]
        indexes = [models.Index(fields=["organization", "full_name"]), models.Index(fields=["organization", "is_active"])]

    def __str__(self) -> str:
        return f"{self.code} · {self.full_name}"
