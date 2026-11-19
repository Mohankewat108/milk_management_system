from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Branch, Organization
from apps.parties.models import Customer, Farmer


class Payment(UUIDModel, TimeStampedModel):
    class Direction(models.TextChoices):
        INCOMING = "incoming", "Incoming"
        OUTGOING = "outgoing", "Outgoing"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank_transfer", "Bank transfer"
        MOBILE = "mobile_wallet", "Mobile wallet"
        ONLINE = "online", "Online"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REVERSED = "reversed", "Reversed"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="payments"
    )
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="payments")
    reference = models.CharField(max_length=48)
    direction = models.CharField(max_length=12, choices=Direction.choices)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, null=True, blank=True, related_name="payments"
    )
    farmer = models.ForeignKey(
        Farmer, on_delete=models.PROTECT, null=True, blank=True, related_name="payments"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    method = models.CharField(max_length=20, choices=Method.choices)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    transaction_reference = models.CharField(max_length=120, blank=True)
    idempotency_key = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_payments"
    )

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"], name="uniq_payment_reference_org"
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                condition=~Q(idempotency_key=""),
                name="uniq_payment_idem_org",
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
            models.CheckConstraint(
                condition=(
                    Q(customer__isnull=False, farmer__isnull=True)
                    | Q(customer__isnull=True, farmer__isnull=False)
                ),
                name="payment_exactly_one_party",
            ),
            models.CheckConstraint(
                condition=(
                    Q(customer__isnull=False, farmer__isnull=True, direction="incoming")
                    | Q(customer__isnull=True, farmer__isnull=False, direction="outgoing")
                ),
                name="payment_direction_matches_party",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "paid_at"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self) -> str:
        return self.reference


class Expense(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="expenses"
    )
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="expenses")
    reference = models.CharField(max_length=48)
    category = models.CharField(max_length=80)
    description = models.CharField(max_length=240)
    supplier_name = models.CharField(max_length=180, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    expense_date = models.DateField(db_index=True)
    method = models.CharField(
        max_length=20, choices=Payment.Method.choices, default=Payment.Method.CASH
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_expenses"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_expenses",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"], name="uniq_expense_reference_org"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="expense_amount_positive"),
        ]
        indexes = [
            models.Index(fields=["organization", "expense_date"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self) -> str:
        return self.reference


class Account(UUIDModel, TimeStampedModel):
    """Tenant-owned chart-of-accounts entry."""

    class AccountType(models.TextChoices):
        ASSET = "asset", "Asset"
        LIABILITY = "liability", "Liability"
        EQUITY = "equity", "Equity"
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    class NormalBalance(models.TextChoices):
        DEBIT = "debit", "Debit"
        CREDIT = "credit", "Credit"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="accounts"
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=120)
    account_type = models.CharField(max_length=12, choices=AccountType.choices)
    normal_balance = models.CharField(max_length=6, choices=NormalBalance.choices)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    is_system = models.BooleanField(default=False)
    allow_manual_entries = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uniq_account_code_org"),
        ]
        indexes = [
            models.Index(
                fields=["organization", "account_type", "is_active"], name="fin_acc_org_type_active"
            )
        ]

    def __str__(self):
        return f"{self.code} · {self.name}"


class AccountingPeriod(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="accounting_periods"
    )
    code = models.CharField(max_length=24)
    name = models.CharField(max_length=100)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-starts_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="uniq_acct_period_org_code"
            ),
            models.CheckConstraint(
                condition=Q(ends_on__gte=models.F("starts_on")), name="acct_period_valid_dates"
            ),
        ]

    def __str__(self):
        return self.name


class JournalEntry(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="journal_entries"
    )
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="journal_entries")
    period = models.ForeignKey(
        AccountingPeriod, on_delete=models.PROTECT, related_name="journal_entries"
    )
    reference = models.CharField(max_length=48)
    entry_date = models.DateField(db_index=True)
    description = models.CharField(max_length=240)
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.CharField(max_length=64, blank=True)
    idempotency_key = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_journal_entries"
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="posted_journal_entries",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    reversal_of = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversal"
    )

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"], name="uniq_journal_ref_org"
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                condition=~Q(idempotency_key=""),
                name="uniq_journal_idem_org",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "entry_date", "status"], name="fin_jrn_org_date_status"
            ),
            models.Index(
                fields=["organization", "source_type", "source_id"], name="fin_jrn_org_source"
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and JournalEntry.objects.filter(pk=self.pk, status=self.Status.POSTED).exists():
            raise ValidationError(
                "Posted journal entries are immutable; create a reversal instead."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.pk and JournalEntry.objects.filter(pk=self.pk, status=self.Status.POSTED).exists():
            raise ValidationError(
                "Posted journal entries cannot be deleted; create a reversal instead."
            )
        return super().delete(*args, **kwargs)

    def __str__(self):
        return self.reference


class JournalLine(UUIDModel, TimeStampedModel):
    entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="journal_lines")
    line_number = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=240, blank=True)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["line_number"]
        constraints = [
            models.UniqueConstraint(fields=["entry", "line_number"], name="uniq_journal_line_no"),
            models.CheckConstraint(
                condition=Q(debit__gte=0) & Q(credit__gte=0), name="jline_nonnegative"
            ),
            models.CheckConstraint(
                condition=(Q(debit__gt=0, credit=0) | Q(debit=0, credit__gt=0)),
                name="jline_one_side_only",
            ),
            models.CheckConstraint(condition=Q(line_number__gt=0), name="jline_number_positive"),
        ]

    def save(self, *args, **kwargs):
        if JournalEntry.objects.filter(
            pk=self.entry_id, status=JournalEntry.Status.POSTED
        ).exists():
            raise ValidationError("Lines on a posted journal are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if JournalEntry.objects.filter(
            pk=self.entry_id, status=JournalEntry.Status.POSTED
        ).exists():
            raise ValidationError("Lines on a posted journal cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.entry.reference} · {self.line_number}"


class LedgerConfiguration(UUIDModel, TimeStampedModel):
    """Organisation-specific control accounts used by automated source posting."""

    organization = models.OneToOneField(
        Organization, on_delete=models.PROTECT, related_name="ledger_configuration"
    )
    cash_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    bank_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    mobile_wallet_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    online_clearing_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    other_payment_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    receivables_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    farmer_payable_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    procurement_expense_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="+"
    )
    sales_revenue_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    default_expense_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    is_enabled = models.BooleanField(default=False)
    enable_farmer_collection_posting = models.BooleanField(default=False)
    enable_customer_sales_posting = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        account_fields = (
            "cash_account",
            "bank_account",
            "mobile_wallet_account",
            "online_clearing_account",
            "other_payment_account",
            "receivables_account",
            "farmer_payable_account",
            "procurement_expense_account",
            "sales_revenue_account",
            "default_expense_account",
        )
        errors = {}
        for field in account_fields:
            account = getattr(self, field, None)
            if account and account.organization_id != self.organization_id:
                errors[field] = "The account must belong to this organisation."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Ledger configuration · {self.organization}"
