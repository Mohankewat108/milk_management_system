from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.finance.ledger_services import (
    create_accounting_period,
    post_journal_entry,
    reverse_journal_entry,
)
from apps.finance.models import Account, JournalEntry
from apps.organizations.models import Branch, Membership, Organization

User = get_user_model()


class DoubleEntryLedgerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ledger-owner",
            email="ledger@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.user, name="Ledger Dairy", slug="ledger-dairy"
        )
        self.branch = Branch.objects.create(
            organization=self.organization, code="MAIN", name="Main"
        )
        Membership.objects.create(
            user=self.user, organization=self.organization, role=Membership.Role.OWNER
        )
        self.period = create_accounting_period(
            organization=self.organization,
            code="FY26",
            name="Financial year 2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        self.cash = Account.objects.create(
            organization=self.organization,
            code="1000",
            name="Cash",
            account_type=Account.AccountType.ASSET,
            normal_balance=Account.NormalBalance.DEBIT,
        )
        self.sales = Account.objects.create(
            organization=self.organization,
            code="4000",
            name="Sales",
            account_type=Account.AccountType.INCOME,
            normal_balance=Account.NormalBalance.CREDIT,
        )

    def post_sale(self, *, key="sale-001"):
        return post_journal_entry(
            organization=self.organization,
            branch=self.branch,
            actor=self.user,
            entry_date=date(2026, 11, 19),
            description="Counter milk sale",
            source_type="test",
            source_id="sale-001",
            idempotency_key=key,
            lines=[
                {"account": self.cash, "debit": Decimal("150.00"), "credit": 0},
                {"account": self.sales, "debit": 0, "credit": Decimal("150.00")},
            ],
        )

    def test_posts_balanced_journal_with_two_lines(self):
        entry = self.post_sale()
        self.assertEqual(entry.status, JournalEntry.Status.POSTED)
        self.assertEqual(entry.lines.count(), 2)
        self.assertEqual(
            sum((line.debit for line in entry.lines.all()), Decimal("0.00")),
            sum((line.credit for line in entry.lines.all()), Decimal("0.00")),
        )
        self.assertIsNotNone(entry.posted_at)
        self.assertEqual(entry.posted_by, self.user)

    def test_unbalanced_journal_is_rejected(self):
        with self.assertRaises(ValidationError):
            post_journal_entry(
                organization=self.organization,
                branch=self.branch,
                actor=self.user,
                entry_date=date(2026, 11, 19),
                description="Unbalanced",
                lines=[
                    {"account": self.cash, "debit": "100.00", "credit": 0},
                    {"account": self.sales, "debit": 0, "credit": "90.00"},
                ],
            )
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_foreign_tenant_account_is_rejected(self):
        other = Organization.objects.create(
            owner=self.user, name="Other Ledger", slug="other-ledger"
        )
        foreign_account = Account.objects.create(
            organization=other,
            code="1000",
            name="Foreign cash",
            account_type=Account.AccountType.ASSET,
            normal_balance=Account.NormalBalance.DEBIT,
        )
        with self.assertRaises(ValidationError):
            post_journal_entry(
                organization=self.organization,
                branch=self.branch,
                actor=self.user,
                entry_date=date(2026, 11, 19),
                description="Cross tenant",
                lines=[
                    {"account": self.cash, "debit": "10", "credit": 0},
                    {"account": foreign_account, "debit": 0, "credit": "10"},
                ],
            )
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_idempotency_key_does_not_duplicate_posted_journal(self):
        first = self.post_sale()
        second = self.post_sale()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(JournalEntry.objects.count(), 1)

    def test_reversal_posts_opposite_lines_and_preserves_original(self):
        original = self.post_sale()
        reversal = reverse_journal_entry(
            entry_id=original.pk,
            organization=self.organization,
            actor=self.user,
            reversal_date=date(2026, 11, 20),
            reason="Incorrect source transaction",
        )
        original.refresh_from_db()
        self.assertEqual(original.status, JournalEntry.Status.POSTED)
        self.assertEqual(reversal.reversal_of_id, original.pk)
        self.assertEqual(
            sum((line.debit for line in reversal.lines.all()), Decimal("0.00")),
            Decimal("150.00"),
        )
        self.assertEqual(
            sum((line.credit for line in reversal.lines.all()), Decimal("0.00")),
            Decimal("150.00"),
        )
        with self.assertRaises(ValidationError):
            reverse_journal_entry(
                entry_id=original.pk,
                organization=self.organization,
                actor=self.user,
                reversal_date=date(2026, 11, 20),
                reason="Second reversal",
            )

    def test_closed_period_rejects_posting(self):
        self.period.status = self.period.Status.CLOSED
        self.period.save(update_fields=["status", "updated_at"])
        with self.assertRaises(ValidationError):
            self.post_sale()

    def test_posted_journal_and_lines_are_immutable(self):
        from django.core.exceptions import ValidationError

        entry = self.post_sale()
        entry.description = "Attempted tampering"
        with self.assertRaises(ValidationError):
            entry.save()
        line = entry.lines.first()
        line.description = "Attempted line tampering"
        with self.assertRaises(ValidationError):
            line.save()
        with self.assertRaises(ValidationError):
            line.delete()
        with self.assertRaises(ValidationError):
            entry.delete()
