from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.permissions import require_actor_branch_access

from .models import Account, AccountingPeriod, JournalEntry, JournalLine


@transaction.atomic
def create_default_chart_of_accounts(*, organization):
    """Create the standard starter accounts once; never overwrite tenant edits."""
    definitions = [
        ("1000", "Cash on hand", Account.AccountType.ASSET, Account.NormalBalance.DEBIT),
        ("1010", "Bank account", Account.AccountType.ASSET, Account.NormalBalance.DEBIT),
        ("1100", "Accounts receivable", Account.AccountType.ASSET, Account.NormalBalance.DEBIT),
        ("1200", "Milk inventory", Account.AccountType.ASSET, Account.NormalBalance.DEBIT),
        ("2000", "Accounts payable", Account.AccountType.LIABILITY, Account.NormalBalance.CREDIT),
        ("2100", "Farmer milk payable", Account.AccountType.LIABILITY, Account.NormalBalance.CREDIT),
        ("3000", "Owner equity", Account.AccountType.EQUITY, Account.NormalBalance.CREDIT),
        ("4000", "Milk sales revenue", Account.AccountType.INCOME, Account.NormalBalance.CREDIT),
        ("5000", "Milk procurement expense", Account.AccountType.EXPENSE, Account.NormalBalance.DEBIT),
        ("6000", "Operating expenses", Account.AccountType.EXPENSE, Account.NormalBalance.DEBIT),
    ]
    created = []
    for code, name, account_type, normal_balance in definitions:
        account, was_created = Account.objects.get_or_create(
            organization=organization, code=code,
            defaults={
                "name": name, "account_type": account_type,
                "normal_balance": normal_balance, "is_system": True,
                "allow_manual_entries": True,
            },
        )
        if was_created:
            created.append(account)
    return created


@transaction.atomic
def create_accounting_period(*, organization, code, name, starts_on, ends_on):
    if ends_on < starts_on:
        raise ValidationError("Accounting period end date must be on or after its start date.")
    overlap = AccountingPeriod.objects.select_for_update().filter(
        organization=organization, starts_on__lte=ends_on, ends_on__gte=starts_on
    )
    if overlap.exists():
        raise ValidationError("Accounting periods for an organisation cannot overlap.")
    return AccountingPeriod.objects.create(
        organization=organization, code=code, name=name,
        starts_on=starts_on, ends_on=ends_on,
    )


@transaction.atomic
def post_journal_entry(
    *, organization, branch, actor, entry_date, description, lines,
    source_type="", source_id="", idempotency_key="", reference=None, reversal_of=None,
):
    """Create and post an immutable, balanced journal in one database transaction.

    Each line is a mapping with account, debit, credit and optional description.
    Amounts are expressed in the organisation's base currency.
    """
    require_actor_branch_access(actor=actor, organization=organization, branch=branch)
    if branch.organization_id != organization.id:
        raise ValidationError("The branch must belong to the selected organisation.")
    if not branch.is_active:
        raise ValidationError("Cannot post to an inactive branch.")
    if len(lines) < 2:
        raise ValidationError("A journal must contain at least two lines.")

    if idempotency_key:
        existing = JournalEntry.objects.filter(
            organization=organization, idempotency_key=idempotency_key
        ).first()
        if existing:
            if existing.status == JournalEntry.Status.POSTED:
                return existing
            raise ValidationError("An entry with this idempotency key is already being processed.")

    period = AccountingPeriod.objects.select_for_update().filter(
        organization=organization, starts_on__lte=entry_date, ends_on__gte=entry_date
    ).first()
    if period is None:
        raise ValidationError("Create an accounting period covering the journal date first.")
    if period.status != AccountingPeriod.Status.OPEN:
        raise ValidationError("The accounting period is closed.")

    normalized = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for number, item in enumerate(lines, start=1):
        account = item.get("account")
        if not isinstance(account, Account) or account.organization_id != organization.id:
            raise ValidationError("Every journal account must belong to this organisation.")
        if not account.is_active or not account.allow_manual_entries:
            raise ValidationError(f"Account {account.code} does not accept journal entries.")
        debit = Decimal(str(item.get("debit", 0))).quantize(Decimal("0.01"))
        credit = Decimal(str(item.get("credit", 0))).quantize(Decimal("0.01"))
        if debit < 0 or credit < 0 or (debit > 0) == (credit > 0):
            raise ValidationError("Each line must contain one positive debit or one positive credit.")
        total_debit += debit
        total_credit += credit
        normalized.append({
            "account": account, "line_number": number,
            "debit": debit, "credit": credit,
            "description": item.get("description", "")[:240],
        })
    if total_debit <= 0 or total_debit != total_credit:
        raise ValidationError("Journal debits and credits must be equal and greater than zero.")

    entry = JournalEntry.objects.create(
        organization=organization, branch=branch, period=period,
        reference=reference or f"JRN-{uuid4().hex[:12].upper()}",
        entry_date=entry_date, description=description,
        source_type=source_type, source_id=str(source_id),
        idempotency_key=idempotency_key, created_by=actor, reversal_of=reversal_of,
    )
    JournalLine.objects.bulk_create([
        JournalLine(entry=entry, **line) for line in normalized
    ])
    entry.status = JournalEntry.Status.POSTED
    entry.posted_by = actor
    entry.posted_at = timezone.now()
    entry.save(update_fields=["status", "posted_by", "posted_at", "updated_at"])
    return entry


@transaction.atomic
def reverse_journal_entry(*, entry_id, organization, actor, reversal_date, reason):
    """Post an equal-and-opposite journal; the original entry is never changed."""
    original = JournalEntry.objects.select_for_update().filter(
        pk=entry_id, organization=organization, status=JournalEntry.Status.POSTED
    ).first()
    if original is None:
        raise ValidationError("Only a posted journal in this organisation can be reversed.")
    if hasattr(original, "reversal"):
        raise ValidationError("This journal has already been reversed.")
    original_lines = list(original.lines.select_related("account").all())
    if not original_lines:
        raise ValidationError("The original journal has no lines to reverse.")
    reversed_lines = [
        {
            "account": line.account,
            "debit": line.credit,
            "credit": line.debit,
            "description": f"Reversal: {line.description}"[:240],
        }
        for line in original_lines
    ]
    return post_journal_entry(
        organization=organization, branch=original.branch, actor=actor,
        entry_date=reversal_date, description=f"Reversal of {original.reference}: {reason}"[:240],
        lines=reversed_lines, source_type="journal_reversal", source_id=original.pk,
        idempotency_key=f"reverse:{original.pk}", reference=f"REV-{uuid4().hex[:12].upper()}",
        reversal_of=original,
    )


def _enabled_ledger_configuration(organization):
    from .models import LedgerConfiguration
    try:
        configuration = LedgerConfiguration.objects.select_related(
            "cash_account", "bank_account", "mobile_wallet_account",
            "online_clearing_account", "other_payment_account",
            "receivables_account", "farmer_payable_account",
            "procurement_expense_account", "sales_revenue_account",
            "default_expense_account",
        ).get(organization=organization, is_enabled=True)
    except LedgerConfiguration.DoesNotExist:
        return None
    account_fields = (
        "cash_account", "bank_account", "mobile_wallet_account",
        "online_clearing_account", "other_payment_account",
        "receivables_account", "farmer_payable_account",
        "procurement_expense_account", "sales_revenue_account",
        "default_expense_account",
    )
    for field in account_fields:
        account = getattr(configuration, field)
        if account.organization_id != organization.id or not account.is_active:
            raise ValidationError(f"Ledger mapping {field} must reference an active account in this organisation.")
    return configuration


def _payment_asset_account(configuration, method):
    from .models import Payment
    return {
        Payment.Method.CASH: configuration.cash_account,
        Payment.Method.BANK: configuration.bank_account,
        Payment.Method.MOBILE: configuration.mobile_wallet_account,
        Payment.Method.ONLINE: configuration.online_clearing_account,
        Payment.Method.OTHER: configuration.other_payment_account,
    }[method]


@transaction.atomic
def post_approved_expense(*, expense, actor):
    """Post expense debit and payment-source credit; safe to retry."""
    configuration = _enabled_ledger_configuration(expense.organization)
    if configuration is None:
        return None
    if expense.status != "approved":
        raise ValidationError("Only approved expenses can be posted.")
    cash_account = _payment_asset_account(configuration, expense.method)
    return post_journal_entry(
        organization=expense.organization, branch=expense.branch, actor=actor,
        entry_date=expense.expense_date, description=f"Expense {expense.reference}: {expense.description}",
        source_type="expense", source_id=expense.pk,
        idempotency_key=f"expense:{expense.pk}:approved",
        lines=[
            {"account": configuration.default_expense_account, "debit": expense.amount, "credit": 0},
            {"account": cash_account, "debit": 0, "credit": expense.amount},
        ],
    )


@transaction.atomic
def post_completed_payment(*, payment, actor):
    """Post customer receipt or farmer payout to the configured control accounts."""
    configuration = _enabled_ledger_configuration(payment.organization)
    if configuration is None:
        return None
    from .models import Payment
    if payment.status != Payment.Status.COMPLETED:
        raise ValidationError("Only completed payments can be posted.")
    asset_account = _payment_asset_account(configuration, payment.method)
    if payment.direction == Payment.Direction.INCOMING and payment.customer_id:
        lines = [
            {"account": asset_account, "debit": payment.amount, "credit": 0},
            {"account": configuration.receivables_account, "debit": 0, "credit": payment.amount},
        ]
        description = f"Customer receipt {payment.reference}"
    elif payment.direction == Payment.Direction.OUTGOING and payment.farmer_id:
        lines = [
            {"account": configuration.farmer_payable_account, "debit": payment.amount, "credit": 0},
            {"account": asset_account, "debit": 0, "credit": payment.amount},
        ]
        description = f"Farmer payout {payment.reference}"
    else:
        raise ValidationError("Payment direction and party do not match a supported posting rule.")
    return post_journal_entry(
        organization=payment.organization, branch=payment.branch, actor=actor,
        entry_date=(payment.paid_at or timezone.now()).date(), description=description,
        source_type="payment", source_id=payment.pk,
        idempotency_key=f"payment:{payment.pk}:completed", lines=lines,
    )


@transaction.atomic
def post_approved_farmer_collection(*, collection, actor):
    """Recognise approved farmer milk as procurement expense and farmer payable."""
    configuration = _enabled_ledger_configuration(collection.organization)
    if configuration is None or not configuration.enable_farmer_collection_posting:
        return None
    from apps.collections.models import MilkCollection
    if collection.status != MilkCollection.Status.APPROVED or not collection.farmer_id:
        raise ValidationError("Only approved farmer collections can be posted.")
    return post_journal_entry(
        organization=collection.organization, branch=collection.branch, actor=actor,
        entry_date=collection.collected_at.date(),
        description=f"Farmer milk procurement {collection.reference}",
        source_type="milk_collection", source_id=collection.pk,
        idempotency_key=f"milk-collection:{collection.pk}:approved",
        lines=[
            {"account": configuration.procurement_expense_account, "debit": collection.total_amount, "credit": 0},
            {"account": configuration.farmer_payable_account, "debit": 0, "credit": collection.total_amount},
        ],
    )


@transaction.atomic
def post_approved_customer_collection_sale(*, collection, actor):
    """Optional sale posting; enabled only after the dairy confirms customer-collection semantics."""
    configuration = _enabled_ledger_configuration(collection.organization)
    if configuration is None or not configuration.enable_customer_sales_posting:
        return None
    from apps.collections.models import MilkCollection
    if collection.status != MilkCollection.Status.APPROVED or not collection.customer_id:
        raise ValidationError("Only approved customer collections can be posted as sales.")
    return post_journal_entry(
        organization=collection.organization, branch=collection.branch, actor=actor,
        entry_date=collection.collected_at.date(),
        description=f"Customer milk sale {collection.reference}",
        source_type="customer_milk_sale", source_id=collection.pk,
        idempotency_key=f"customer-milk-sale:{collection.pk}:approved",
        lines=[
            {"account": configuration.receivables_account, "debit": collection.total_amount, "credit": 0},
            {"account": configuration.sales_revenue_account, "debit": 0, "credit": collection.total_amount},
        ],
    )
