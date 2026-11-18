import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
        ("parties", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StaffInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("first_name", models.CharField(blank=True, max_length=150)),
                ("last_name", models.CharField(blank=True, max_length=150)),
                ("role", models.CharField(choices=[("owner", "Dairy owner"), ("admin", "Organisation admin"), ("branch_manager", "Branch manager"), ("collection_operator", "Milk collection operator"), ("quality_officer", "Quality officer"), ("accountant", "Accountant"), ("inventory_manager", "Inventory manager"), ("support", "Customer support")], max_length=32)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("branches", models.ManyToManyField(blank=True, related_name="staff_invitations", to="organizations.branch")),
                ("invited_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sent_staff_invitations", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="staff_invitations", to="organizations.organization")),
            ],
            options={"ordering": ["-created_at"], "indexes": [models.Index(fields=["organization", "email", "created_at"], name="org_staffinv_org_email_idx")]},
        ),
    ]
