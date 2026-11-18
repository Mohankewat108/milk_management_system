import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0003_accounting_ledger")]

    operations = [
        migrations.CreateModel(
            name="LedgerConfiguration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_enabled", models.BooleanField(default=False)),
                ("enable_farmer_collection_posting", models.BooleanField(default=False)),
                ("enable_customer_sales_posting", models.BooleanField(default=False)),
                ("bank_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="finance.account")),
                ("cash_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="finance.account")),
                ("default_expense_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="finance.account")),
                ("farmer_payable_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="finance.account")),
                ("mobile_wallet_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="finance.account")),
                ("online_clearing_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="finance.account")),
                ("other_payment_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="finance.account")),
                ("procurement_expense_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="finance.account")),
                ("receivables_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="finance.account")),
                ("sales_revenue_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="finance.account")),
                ("organization", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="ledger_configuration", to="organizations.organization")),
            ],
        ),
    ]
