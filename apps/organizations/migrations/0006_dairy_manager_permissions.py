import uuid

from django.db import migrations, models


PERMISSIONS = [
    ("dashboard.view", "View dashboard", "Access organisation dashboard metrics."),
    ("collections.view", "View milk collections", "View milk collection records."),
    ("collections.create", "Record milk collections", "Create milk collection records."),
    ("collections.approve", "Approve milk collections", "Approve or reject submitted collections."),
    ("parties.view", "View farmers and customers", "View farmer and customer profiles."),
    ("parties.manage", "Manage farmers and customers", "Create and update farmer and customer profiles."),
    ("finance.view", "View financial records", "View payments, balances and statements."),
    ("finance.manage", "Manage payments and accounts", "Record and manage financial transactions."),
    ("inventory.view", "View inventory", "View stock and inventory records."),
    ("inventory.manage", "Manage inventory", "Create and manage inventory movements."),
    ("staff.manage", "Manage organisation staff", "Invite, update and suspend organisation staff."),
    ("reports.view", "View reports", "Access organisation reports."),
    ("exports.create", "Create data exports", "Generate organisation data exports."),
    ("settings.manage", "Manage organisation settings", "Change organisation configuration."),
]


def create_permission_catalog(apps, schema_editor):
    Permission = apps.get_model("organizations", "OrganizationPermission")
    for key, name, description in PERMISSIONS:
        Permission.objects.get_or_create(key=key, defaults={"name": name, "description": description})


class Migration(migrations.Migration):
    dependencies = [("organizations", "0005_tenant_relationship_integrity")]

    operations = [
        migrations.CreateModel(
            name="OrganizationPermission",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=64, unique=True, choices=[
                    ("dashboard.view", "View dashboard"),
                    ("collections.view", "View milk collections"),
                    ("collections.create", "Record milk collections"),
                    ("collections.approve", "Approve milk collections"),
                    ("parties.view", "View farmers and customers"),
                    ("parties.manage", "Manage farmers and customers"),
                    ("finance.view", "View financial records"),
                    ("finance.manage", "Manage payments and accounts"),
                    ("inventory.view", "View inventory"),
                    ("inventory.manage", "Manage inventory"),
                    ("staff.manage", "Manage organisation staff"),
                    ("reports.view", "View reports"),
                    ("exports.create", "Create data exports"),
                    ("settings.manage", "Manage organisation settings"),
                ])),
                ("name", models.CharField(max_length=100)),
                ("description", models.CharField(max_length=255, blank=True)),
            ],
            options={"ordering": ["key"]},
        ),
        migrations.AddField(
            model_name="membership",
            name="permissions",
            field=models.ManyToManyField(blank=True, related_name="memberships", to="organizations.organizationpermission"),
        ),
        migrations.AddField(
            model_name="staffinvitation",
            name="permissions",
            field=models.ManyToManyField(blank=True, related_name="staff_invitations", to="organizations.organizationpermission"),
        ),
        migrations.AlterField(
            model_name="membership",
            name="role",
            field=models.CharField(max_length=32, choices=[
                ("owner", "Dairy owner"),
                ("admin", "Organisation admin"),
                ("dairy_manager", "Dairy manager"),
                ("branch_manager", "Branch manager"),
                ("collection_operator", "Milk collection operator"),
                ("quality_officer", "Quality officer"),
                ("accountant", "Accountant"),
                ("inventory_manager", "Inventory manager"),
                ("support", "Customer support"),
            ]),
        ),
        migrations.AlterField(
            model_name="staffinvitation",
            name="role",
            field=models.CharField(max_length=32, choices=[
                ("owner", "Dairy owner"),
                ("admin", "Organisation admin"),
                ("dairy_manager", "Dairy manager"),
                ("branch_manager", "Branch manager"),
                ("collection_operator", "Milk collection operator"),
                ("quality_officer", "Quality officer"),
                ("accountant", "Accountant"),
                ("inventory_manager", "Inventory manager"),
                ("support", "Customer support"),
            ]),
        ),
        migrations.RunPython(create_permission_catalog, migrations.RunPython.noop),
    ]
