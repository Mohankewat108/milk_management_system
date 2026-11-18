import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_exports", "0001_initial"),
        ("organizations", "0004_branch_soft_delete"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),

        migrations.AlterField(
            model_name="exportjob", name="module",
            field=models.CharField(choices=[("farmers", "Farmers"), ("customers", "Customers"), ("collections", "Milk collections"), ("payments", "Payments"), ("expenses", "Expenses"), ("inventory", "Inventory"), ("suppliers", "Suppliers")], db_index=True, max_length=24),
        ),
        migrations.AlterField(
            model_name="savedexporttemplate", name="module",
            field=models.CharField(choices=[("farmers", "Farmers"), ("customers", "Customers"), ("collections", "Milk collections"), ("payments", "Payments"), ("expenses", "Expenses"), ("inventory", "Inventory"), ("suppliers", "Suppliers")], max_length=24),
        ),
        migrations.AlterField(
            model_name="scheduledexport", name="module",
            field=models.CharField(choices=[("farmers", "Farmers"), ("customers", "Customers"), ("collections", "Milk collections"), ("payments", "Payments"), ("expenses", "Expenses"), ("inventory", "Inventory"), ("suppliers", "Suppliers")], max_length=24),
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="exportjob", name="status",
            field=models.CharField(choices=[("queued", "Queued"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed"), ("expired", "Expired")], db_index=True, default="queued", max_length=16),
        ),
        migrations.AddField(
            model_name="exportjob", name="notification_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="exportjob",
            index=models.Index(fields=["status", "created_at"], name="dex_exp_status_created_idx"),
        ),
        migrations.CreateModel(
            name="SavedExportTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100)),
                ("module", models.CharField(choices=[("farmers", "Farmers"), ("customers", "Customers"), ("collections", "Milk collections"), ("payments", "Payments"), ("expenses", "Expenses"), ("inventory", "Inventory")], max_length=24)),
                ("file_format", models.CharField(default="xlsx", max_length=8)),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("is_shared", models.BooleanField(default=False)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="saved_export_templates", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="export_templates", to="organizations.organization")),
            ],
            options={"ordering": ["name"], "constraints": [models.UniqueConstraint(fields=("organization", "name"), name="uniq_export_template_org_name")]},
        ),
        migrations.CreateModel(
            name="ScheduledExport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100)),
                ("module", models.CharField(choices=[("farmers", "Farmers"), ("customers", "Customers"), ("collections", "Milk collections"), ("payments", "Payments"), ("expenses", "Expenses"), ("inventory", "Inventory")], max_length=24)),
                ("file_format", models.CharField(default="xlsx", max_length=8)),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("frequency", models.CharField(choices=[("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")], max_length=12)),
                ("next_run_at", models.DateTimeField(db_index=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("recipients", models.JSONField(blank=True, default=list)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="scheduled_exports", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scheduled_exports", to="organizations.organization")),
            ],
            options={"ordering": ["next_run_at"], "indexes": [models.Index(fields=["is_active", "next_run_at"], name="dex_schedule_due_idx")]},
        ),
        migrations.CreateModel(
            name="ImportBatch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("module", models.CharField(choices=[("farmers", "Farmers"), ("customers", "Customers")], max_length=24)),
                ("file", models.FileField(upload_to="private_imports/%Y/%m/")),
                ("status", models.CharField(choices=[("uploaded", "Uploaded"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")], db_index=True, default="uploaded", max_length=16)),
                ("total_rows", models.PositiveIntegerField(default=0)),
                ("imported_rows", models.PositiveIntegerField(default=0)),
                ("failed_rows", models.PositiveIntegerField(default=0)),
                ("row_errors", models.JSONField(blank=True, default=list)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="import_batches", to="organizations.organization")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="data_imports", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"], "indexes": [models.Index(fields=["organization", "created_at"], name="dex_import_org_created_idx")]},
        ),
    ]
