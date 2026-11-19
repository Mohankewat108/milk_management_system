from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Organization

from .storage import private_storage


class ExportJob(UUIDModel, TimeStampedModel):
    class Module(models.TextChoices):
        FARMERS = "farmers", "Farmers"
        CUSTOMERS = "customers", "Customers"
        COLLECTIONS = "collections", "Milk collections"
        PAYMENTS = "payments", "Payments"
        EXPENSES = "expenses", "Expenses"
        INVENTORY = "inventory", "Inventory"
        SUPPLIERS = "suppliers", "Suppliers"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="export_jobs"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="export_jobs"
    )
    module = models.CharField(max_length=24, choices=Module.choices, db_index=True)
    file_format = models.CharField(max_length=8, default="csv")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True
    )
    record_count = models.PositiveIntegerField(default=0)
    file_size = models.PositiveBigIntegerField(default=0)
    file = models.FileField(upload_to="private_exports/%Y/%m/", blank=True, storage=private_storage)
    filters = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    error_message = models.CharField(max_length=500, blank=True)
    notification_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"], name="dex_exp_org_created_idx"),
            models.Index(fields=["organization", "status"], name="dex_exp_org_status_idx"),
            models.Index(fields=["status", "created_at"], name="dex_exp_status_created_idx"),
        ]

    def __str__(self):
        return f"{self.get_module_display()} · {self.created_at:%Y-%m-%d}"


class SavedExportTemplate(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="export_templates"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="saved_export_templates"
    )
    name = models.CharField(max_length=100)
    module = models.CharField(max_length=24, choices=ExportJob.Module.choices)
    file_format = models.CharField(max_length=8, default="xlsx")
    filters = models.JSONField(default=dict, blank=True)
    is_shared = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="uniq_export_template_org_name"
            )
        ]


class ScheduledExport(UUIDModel, TimeStampedModel):
    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="scheduled_exports"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="scheduled_exports"
    )
    name = models.CharField(max_length=100)
    module = models.CharField(max_length=24, choices=ExportJob.Module.choices)
    file_format = models.CharField(max_length=8, default="xlsx")
    filters = models.JSONField(default=dict, blank=True)
    frequency = models.CharField(max_length=12, choices=Frequency.choices)
    next_run_at = models.DateTimeField(db_index=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    recipients = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["next_run_at"]
        indexes = [models.Index(fields=["is_active", "next_run_at"], name="dex_schedule_due_idx")]


class ImportBatch(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="import_batches"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="data_imports"
    )
    module = models.CharField(
        max_length=24, choices=[("farmers", "Farmers"), ("customers", "Customers")]
    )
    file = models.FileField(upload_to="private_imports/%Y/%m/", storage=private_storage)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.UPLOADED, db_index=True
    )
    total_rows = models.PositiveIntegerField(default=0)
    imported_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    row_errors = models.JSONField(default=list, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"], name="dex_import_org_created_idx")
        ]
