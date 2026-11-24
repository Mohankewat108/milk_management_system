from datetime import UTC, date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.collections.models import MilkCollection
from apps.collections.services import approve_collection, create_collection, reverse_collection
from apps.finance.ledger_services import create_accounting_period
from apps.finance.models import Account, JournalEntry, LedgerConfiguration
from apps.organizations.models import Branch, Membership, Organization
from apps.parties.models import Customer, Farmer
from apps.pricing.models import PricingConfiguration

User = get_user_model()


class CollectionReversalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="collection-reversal-owner",
            email="collection-reversal-owner@example.test",
            password="StrongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.user,
            name="Reversal Dairy",
            slug="reversal-dairy",
            is_demo=True,
        )
        self.branch = Branch.objects.create(
            organization=self.organization,
            code="MAIN",
            name="Main",
        )
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        self.period = create_accounting_period(
            organization=self.organization,
            code="FY2026",
            name="FY 2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        self.accounts = {}
        definitions = (
            ("cash", "1000", Account.AccountType.ASSET, Account.NormalBalance.DEBIT),
            ("bank", "1010", Account.AccountType.ASSET, Account.NormalBalance.DEBIT),
            ("mobile", "1020", Account.AccountType.ASSET, Account.NormalBalance.DEBIT),
            ("online", "1030", Account.AccountType.ASSET, Account.NormalBalance.DEBIT),
            ("other", "1040", Account.AccountType.ASSET, Account.NormalBalance.DEBIT),
            ("receivable", "1100", Account.AccountType.ASSET, Account.NormalBalance.DEBIT),
            ("farmer_payable", "2100", Account.AccountType.LIABILITY, Account.NormalBalance.CREDIT),
            ("procurement", "5000", Account.AccountType.EXPENSE, Account.NormalBalance.DEBIT),
            ("revenue", "4000", Account.AccountType.INCOME, Account.NormalBalance.CREDIT),
            ("expense", "6000", Account.AccountType.EXPENSE, Account.NormalBalance.DEBIT),
        )
        for key, code, account_type, normal_balance in definitions:
            self.accounts[key] = Account.objects.create(
                organization=self.organization,
                code=code,
                name=key.replace("_", " ").title(),
                account_type=account_type,
                normal_balance=normal_balance,
            )
        self.ledger = LedgerConfiguration.objects.create(
            organization=self.organization,
            cash_account=self.accounts["cash"],
            bank_account=self.accounts["bank"],
            mobile_wallet_account=self.accounts["mobile"],
            online_clearing_account=self.accounts["online"],
            other_payment_account=self.accounts["other"],
            receivables_account=self.accounts["receivable"],
            farmer_payable_account=self.accounts["farmer_payable"],
            procurement_expense_account=self.accounts["procurement"],
            sales_revenue_account=self.accounts["revenue"],
            default_expense_account=self.accounts["expense"],
            is_enabled=True,
            enable_farmer_collection_posting=True,
            enable_customer_sales_posting=True,
        )
        PricingConfiguration.objects.create(
            organization=self.organization,
            version=1,
            snf_rate=Decimal("5.0000"),
            fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=date(2026, 1, 1),
            is_approved=True,
            created_by=self.user,
        )

    def _approved_collection(self, *, party):
        values = {"farmer": party} if isinstance(party, Farmer) else {"customer": party}
        entry = create_collection(
            organization=self.organization,
            branch=self.branch,
            actor=self.user,
            collected_at=datetime(2026, 11, 20, 6, 0, tzinfo=UTC),
            quantity_litres="2.000",
            snf="8.0",
            fat="4.0",
            lactose="4.5",
            **values,
        )
        return approve_collection(
            collection_id=entry.pk,
            organization=self.organization,
            actor=self.user,
        )

    def _assert_journal_reversed(self, *, source_type, collection):
        original = JournalEntry.objects.get(
            organization=self.organization,
            source_type=source_type,
            source_id=str(collection.pk),
        )
        reversal = JournalEntry.objects.get(reversal_of=original)
        self.assertEqual(original.status, JournalEntry.Status.POSTED)
        self.assertEqual(reversal.status, JournalEntry.Status.POSTED)
        self.assertEqual(
            sum((line.debit for line in original.lines.all()), Decimal("0.00")),
            sum((line.credit for line in reversal.lines.all()), Decimal("0.00")),
        )
        self.assertEqual(
            sum((line.credit for line in original.lines.all()), Decimal("0.00")),
            sum((line.debit for line in reversal.lines.all()), Decimal("0.00")),
        )

    def test_reversing_approved_farmer_collection_posts_journal_reversal(self):
        farmer = Farmer.objects.create(
            organization=self.organization,
            branch=self.branch,
            code="F-REV",
            full_name="Farmer to Reverse",
        )
        collection = self._approved_collection(party=farmer)

        reversed_entry = reverse_collection(
            collection_id=collection.pk,
            organization=self.organization,
            actor=self.user,
            reason="Incorrect measured quantity",
        )

        self.assertEqual(reversed_entry.status, MilkCollection.Status.REVERSED)
        self._assert_journal_reversed(source_type="milk_collection", collection=collection)
        self.assertEqual(JournalEntry.objects.count(), 2)

        # Retrying the same business action must not create another journal.
        reverse_collection(
            collection_id=collection.pk,
            organization=self.organization,
            actor=self.user,
            reason="Incorrect measured quantity",
        )
        self.assertEqual(JournalEntry.objects.count(), 2)

    def test_reversing_approved_customer_collection_reverses_sales_journal(self):
        customer = Customer.objects.create(
            organization=self.organization,
            branch=self.branch,
            code="C-REV",
            full_name="Customer to Reverse",
        )
        collection = self._approved_collection(party=customer)

        reversed_entry = reverse_collection(
            collection_id=collection.pk,
            organization=self.organization,
            actor=self.user,
            reason="Duplicate customer milk sale",
        )

        self.assertEqual(reversed_entry.status, MilkCollection.Status.REVERSED)
        self._assert_journal_reversed(source_type="customer_milk_sale", collection=collection)
        self.assertEqual(JournalEntry.objects.count(), 2)

    def test_closed_accounting_period_keeps_collection_and_journal_unchanged(self):
        farmer = Farmer.objects.create(
            organization=self.organization,
            branch=self.branch,
            code="F-CLOSED",
            full_name="Closed Period Farmer",
        )
        collection = self._approved_collection(party=farmer)
        self.period.status = self.period.Status.CLOSED
        self.period.save(update_fields=["status", "updated_at"])

        with self.assertRaises(ValidationError):
            reverse_collection(
                collection_id=collection.pk,
                organization=self.organization,
                actor=self.user,
                reason="Wrong collection entered",
            )

        collection.refresh_from_db()
        self.assertEqual(collection.status, MilkCollection.Status.APPROVED)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertFalse(JournalEntry.objects.filter(reversal_of__isnull=False).exists())
