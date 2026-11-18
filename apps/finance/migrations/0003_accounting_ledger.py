# Generated for the immutable double-entry ledger foundation.
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0002_soft_delete"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=20)),
                ("name", models.CharField(max_length=120)),
                ("account_type", models.CharField(choices=[("asset","Asset"),("liability","Liability"),("equity","Equity"),("income","Income"),("expense","Expense")], max_length=12)),
                ("normal_balance", models.CharField(choices=[("debit","Debit"),("credit","Credit")], max_length=6)),
                ("is_system", models.BooleanField(default=False)),
                ("allow_manual_entries", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="accounts", to="organizations.organization")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="children", to="finance.account")),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="AccountingPeriod",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=24)),
                ("name", models.CharField(max_length=100)),
                ("starts_on", models.DateField()),
                ("ends_on", models.DateField()),
                ("status", models.CharField(choices=[("open","Open"),("closed","Closed")], default="open", max_length=8)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="accounting_periods", to="organizations.organization")),
            ],
            options={"ordering": ["-starts_on"]},
        ),
        migrations.CreateModel(
            name="JournalEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reference", models.CharField(max_length=48)),
                ("entry_date", models.DateField(db_index=True)),
                ("description", models.CharField(max_length=240)),
                ("source_type", models.CharField(blank=True, max_length=40)),
                ("source_id", models.CharField(blank=True, max_length=64)),
                ("idempotency_key", models.CharField(blank=True, max_length=100)),
                ("status", models.CharField(choices=[("draft","Draft"),("posted","Posted")], db_index=True, default="draft", max_length=8)),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journal_entries", to="organizations.branch")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_journal_entries", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journal_entries", to="organizations.organization")),
                ("period", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journal_entries", to="finance.accountingperiod")),
                ("posted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="posted_journal_entries", to=settings.AUTH_USER_MODEL)),
                ("reversal_of", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reversal", to="finance.journalentry")),
            ],
            options={"ordering": ["-entry_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="JournalLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("line_number", models.PositiveSmallIntegerField()),
                ("description", models.CharField(blank=True, max_length=240)),
                ("debit", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("credit", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journal_lines", to="finance.account")),
                ("entry", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="finance.journalentry")),
            ],
            options={"ordering": ["line_number"]},
        ),
        migrations.AddConstraint("account", models.UniqueConstraint(fields=("organization","code"), name="uniq_account_code_org")),
        migrations.AddIndex("account", models.Index(fields=["organization","account_type","is_active"], name="fin_acc_org_type_active")),
        migrations.AddConstraint("accountingperiod", models.UniqueConstraint(fields=("organization","code"), name="uniq_acct_period_org_code")),
        migrations.AddConstraint("accountingperiod", models.CheckConstraint(condition=models.Q(("ends_on__gte", models.F("starts_on"))), name="acct_period_valid_dates")),
        migrations.AddConstraint("journalentry", models.UniqueConstraint(fields=("organization","reference"), name="uniq_journal_ref_org")),
        migrations.AddConstraint("journalentry", models.UniqueConstraint(condition=~models.Q(("idempotency_key","")), fields=("organization","idempotency_key"), name="uniq_journal_idem_org")),
        migrations.AddIndex("journalentry", models.Index(fields=["organization","entry_date","status"], name="fin_jrn_org_date_status")),
        migrations.AddIndex("journalentry", models.Index(fields=["organization","source_type","source_id"], name="fin_jrn_org_source")),
        migrations.AddConstraint("journalline", models.UniqueConstraint(fields=("entry","line_number"), name="uniq_journal_line_no")),
        migrations.AddConstraint("journalline", models.CheckConstraint(condition=models.Q(("debit__gte",0),("credit__gte",0)), name="jline_nonnegative")),
        migrations.AddConstraint("journalline", models.CheckConstraint(condition=(models.Q(("debit__gt",0),("credit",0)) | models.Q(("debit",0),("credit__gt",0))), name="jline_one_side_only")),
    ]
