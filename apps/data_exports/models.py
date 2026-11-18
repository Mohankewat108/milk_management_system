from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Organization


class ExportJob(UUIDModel, TimeStampedModel):
    class Module(models.TextChoices):
        FARMERS = "farmers", "Farmers"
        CUSTOMERS = "customers", "Customers"
        COLLECTIONS = "collections", "Milk collections"
        PAYMENTS = "payments", "Payments"
        EXPENSES = "expenses", "Expenses"
        INVENTORY = "inventory", "Inventory"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="export_jobs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="export_jobs")
    module = models.CharField(max_length=24, choices=Module.choices, db_index=True)
    file_format = models.CharField(max_length=8, default="csv")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.COMPLETED, db_index=True)
    record_count = models.PositiveIntegerField(default=0)
    file_size = models.PositiveBigIntegerField(default=0)
    file = models.FileField(upload_to="private_exports/%Y/%m/", blank=True)
    filters = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "created_at"], name="dex_exp_org_created_idx"), models.Index(fields=["organization", "status"], name="dex_exp_org_status_idx")]

    def __str__(self):
        return f"{self.get_module_display()} · {self.created_at:%Y-%m-%d}"
