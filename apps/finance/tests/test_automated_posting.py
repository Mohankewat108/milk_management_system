from datetime import UTC, date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.collections.services import approve_collection, create_collection
from apps.finance.ledger_services import create_accounting_period
from apps.finance.models import Account, JournalEntry, LedgerConfiguration, Payment
from apps.finance.services import approve_expense, complete_payment, record_expense, record_payment
from apps.organizations.models import Branch, Membership, Organization
from apps.parties.models import Customer, Farmer
from apps.pricing.models import PricingConfiguration

User = get_user_model()


class AutomatedLedgerPostingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ledger-workflow-owner",
            email="ledger-workflow@example.test",
            password="LongDemoPass!123",
        )
        self.org = Organization.objects.create(
            owner=self.user,
            name="Posting Dairy",
            slug="posting-dairy",
            is_demo=True,
        )
        self.branch = Branch.objects.create(
            organization=self.org,
            code="MAIN",
            name="Main",
        )
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.OWNER,
        )
        self.period = create_accounting_period(
            organization=self.org,
            code="FY2026",
            name="FY 2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        self.accounts = {}
        definitions = [
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
        ]
        for key, code, account_type, normal_balance in definitions:
            self.accounts[key] = Account.objects.create(
                organization=self.org,
                code=code,
                name=key.replace("_", " ").title(),
                account_type=account_type,
                normal_balance=normal_balance,
            )
        self.config = LedgerConfiguration.objects.create(
            organization=self.org,
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
        )

    def journal_for(self, source_type, source_id):
        return JournalEntry.objects.get(
            organization=self.org,
            source_type=source_type,
            source_id=str(source_id),
        )

    def test_approved_expense_posts_expense_and_cash_credit_once(self):
        expense = record_expense(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            category="Utilities",
            description="Electricity",
            amount="125.50",
            expense_date=date(2026, 11, 19),
            method=Payment.Method.CASH,
        )
        self.assertEqual(JournalEntry.objects.count(), 0)
        approve_expense(expense_id=expense.pk, organization=self.org, actor=self.user)
        journal = self.journal_for("expense", expense.pk)
        self.assertEqual(journal.status, JournalEntry.Status.POSTED)
        self.assertEqual(
            journal.lines.get(account=self.accounts["expense"]).debit, Decimal("125.50")
        )
        self.assertEqual(journal.lines.get(account=self.accounts["cash"]).credit, Decimal("125.50"))

    def test_customer_receipt_posts_cash_debit_and_receivable_credit(self):
        customer = Customer.objects.create(
            organization=self.org,
            code="C-001",
            full_name="Customer One",
        )
        payment = record_payment(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            direction=Payment.Direction.INCOMING,
            amount="250.00",
            method=Payment.Method.BANK,
            customer=customer,
        )
        completed = complete_payment(
            payment_id=payment.pk,
            organization=self.org,
            actor=self.user,
        )
        journal = self.journal_for("payment", payment.pk)
        self.assertEqual(completed.status, Payment.Status.COMPLETED)
        self.assertEqual(journal.lines.get(account=self.accounts["bank"]).debit, Decimal("250.00"))
        self.assertEqual(
            journal.lines.get(account=self.accounts["receivable"]).credit, Decimal("250.00")
        )

    def test_farmer_payout_posts_farmer_payable_debit_and_bank_credit(self):
        farmer = Farmer.objects.create(
            organization=self.org,
            branch=self.branch,
            code="F-001",
            full_name="Farmer One",
        )
        payment = record_payment(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            direction=Payment.Direction.OUTGOING,
            amount="75.00",
            method=Payment.Method.BANK,
            farmer=farmer,
        )
        complete_payment(payment_id=payment.pk, organization=self.org, actor=self.user)
        journal = self.journal_for("payment", payment.pk)
        self.assertEqual(
            journal.lines.get(account=self.accounts["farmer_payable"]).debit,
            Decimal("75.00"),
        )
        self.assertEqual(journal.lines.get(account=self.accounts["bank"]).credit, Decimal("75.00"))

    def test_approved_farmer_collection_posts_procurement_and_farmer_payable(self):
        farmer = Farmer.objects.create(
            organization=self.org,
            branch=self.branch,
            code="F-002",
            full_name="Farmer Two",
        )
        pricing = PricingConfiguration.objects.create(
            organization=self.org,
            version=1,
            snf_rate=Decimal("5.0000"),
            fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=date(2026, 1, 1),
            is_approved=True,
            created_by=self.user,
        )
        collection = create_collection(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            collected_at=datetime(2026, 11, 19, 6, 0, tzinfo=UTC),
            quantity_litres="2.000",
            snf="8.0",
            fat="4.0",
            lactose="4.5",
            farmer=farmer,
        )
        approve_collection(
            collection_id=collection.pk,
            organization=self.org,
            actor=self.user,
        )
        journal = self.journal_for("milk_collection", collection.pk)
        self.assertEqual(
            journal.lines.get(account=self.accounts["procurement"]).debit, collection.total_amount
        )
        self.assertEqual(
            journal.lines.get(account=self.accounts["farmer_payable"]).credit,
            collection.total_amount,
        )

    def test_unconfigured_ledger_preserves_existing_workflow_without_silent_post(self):
        self.config.is_enabled = False
        self.config.save(update_fields=["is_enabled", "updated_at"])
        expense = record_expense(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            category="Utilities",
            description="Unconfigured expense",
            amount="10.00",
            expense_date=date(2026, 11, 19),
            method=Payment.Method.CASH,
        )
        approve_expense(expense_id=expense.pk, organization=self.org, actor=self.user)
        self.assertFalse(JournalEntry.objects.exists())
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.APPROVED)

    def test_customer_collection_sales_rule_requires_explicit_opt_in(self):
        customer = Customer.objects.create(
            organization=self.org,
            code="C-SELL",
            full_name="Milk Supplier Customer",
        )
        self.config.enable_customer_sales_posting = True
        self.config.save(update_fields=["enable_customer_sales_posting", "updated_at"])
        PricingConfiguration.objects.create(
            organization=self.org,
            version=1,
            snf_rate=Decimal("5.0000"),
            fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=date(2026, 1, 1),
            is_approved=True,
            created_by=self.user,
        )
        collection = create_collection(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            collected_at=datetime(2026, 11, 19, 6, 0, tzinfo=UTC),
            quantity_litres="1.000",
            snf="8.0",
            fat="4.0",
            lactose="4.5",
            customer=customer,
        )
        approve_collection(
            collection_id=collection.pk,
            organization=self.org,
            actor=self.user,
        )
        journal = self.journal_for("customer_milk_sale", collection.pk)
        self.assertEqual(
            journal.lines.get(account=self.accounts["receivable"]).debit,
            collection.total_amount,
        )
        self.assertEqual(
            journal.lines.get(account=self.accounts["revenue"]).credit,
            collection.total_amount,
        )

    def test_posting_failure_rolls_back_expense_approval(self):
        expense = record_expense(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            category="Utilities",
            description="Expense in closed period",
            amount="25.00",
            expense_date=date(2026, 11, 19),
            method=Payment.Method.CASH,
        )
        self.period.status = self.period.Status.CLOSED
        self.period.save(update_fields=["status", "updated_at"])
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            approve_expense(
                expense_id=expense.pk,
                organization=self.org,
                actor=self.user,
            )
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PENDING)
        self.assertFalse(JournalEntry.objects.exists())
