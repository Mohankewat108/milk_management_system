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
