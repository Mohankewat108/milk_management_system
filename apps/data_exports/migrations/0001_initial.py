import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("organizations", "0004_branch_soft_delete"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="ExportJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("module", models.CharField(choices=[("farmers", "Farmers"), ("customers", "Customers"), ("collections", "Milk collections"), ("payments", "Payments"), ("expenses", "Expenses"), ("inventory", "Inventory")], max_length=24, db_index=True)),
                ("file_format", models.CharField(default="csv", max_length=8)),
                ("status", models.CharField(choices=[("completed", "Completed"), ("failed", "Failed"), ("expired", "Expired")], default="completed", max_length=16, db_index=True)),
                ("record_count", models.PositiveIntegerField(default=0)),
                ("file_size", models.PositiveBigIntegerField(default=0)),
                ("file", models.FileField(blank=True, upload_to="private_exports/%Y/%m/")),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("error_message", models.CharField(blank=True, max_length=500)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="export_jobs", to="organizations.organization")),
                ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="export_jobs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"], "indexes": [models.Index(fields=["organization", "created_at"], name="data_exports_organiz_0d9c9f_idx"), models.Index(fields=["organization", "status"], name="data_exports_organiz_8d31b0_idx")]},
        ),
    ]
