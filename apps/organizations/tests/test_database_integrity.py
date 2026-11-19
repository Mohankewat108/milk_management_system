from datetime import UTC, date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.collections.models import MilkCollection
from apps.finance.models import (
    Account,
    AccountingPeriod,
    Expense,
    JournalEntry,
    JournalLine,
    LedgerConfiguration,
    Payment,
)
from apps.inventory.models import InventoryItem, StockMovement, Supplier
from apps.organizations.models import (
    Branch,
    BranchAssignment,
    Membership,
    Organization,
    StaffInvitation,
)
from apps.parties.models import Customer, Farmer
from apps.pricing.models import PricingConfiguration, QualityConfiguration

User = get_user_model()


class DatabaseIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="integrity-owner",
            email="integrity-owner@example.test",
            password="LongDemoPass!123",
        )
        self.org = Organization.objects.create(
            owner=self.user, name="Integrity A", slug="integrity-a"
        )
        self.other_org = Organization.objects.create(
            owner=self.user, name="Integrity B", slug="integrity-b"
        )
        self.branch = Branch.objects.create(organization=self.org, code="A", name="Branch A")
        self.other_branch = Branch.objects.create(
            organization=self.other_org, code="B", name="Branch B"
        )
        self.membership = Membership.objects.create(
            user=self.user, organization=self.org, role=Membership.Role.OWNER
        )
        self.farmer = Farmer.objects.create(
            organization=self.org, branch=self.branch, code="F-1", full_name="Farmer One"
        )
        self.other_farmer = Farmer.objects.create(
            organization=self.other_org,
            branch=self.other_branch,
            code="F-2",
            full_name="Farmer Two",
        )
        self.customer = Customer.objects.create(
            organization=self.org, code="C-1", full_name="Customer One"
        )
        self.pricing = self._pricing(self.org, 1)
        self.other_pricing = self._pricing(self.other_org, 1)

    def _pricing(self, organization, version):
        return PricingConfiguration.objects.create(
            organization=organization,
            version=version,
            snf_rate=Decimal("5.0000"),
            fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=date(2026, 1, 1),
            is_approved=True,
            created_by=self.user,
        )

    def _account(self, organization, code):
        return Account.objects.create(
            organization=organization,
            code=code,
            name=f"Account {code}",
            account_type=Account.AccountType.ASSET,
            normal_balance=Account.NormalBalance.DEBIT,
        )

    def test_foreign_branch_cannot_be_saved_on_tenant_party(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Farmer.objects.create(
                organization=self.org,
                branch=self.other_branch,
                code="F-3",
                full_name="Cross-tenant farmer",
            )

    def test_tenant_owned_configuration_and_expense_reject_foreign_branch(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PricingConfiguration.objects.create(
                organization=self.org,
                branch=self.other_branch,
                version=2,
                snf_rate=Decimal("5.0000"),
                fat_rate=Decimal("7.0000"),
                lactose_rate=Decimal("1.0000"),
                effective_from=date(2027, 1, 1),
                created_by=self.user,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Expense.objects.create(
                organization=self.org,
                branch=self.other_branch,
                reference="CROSS-EXPENSE",
                category="operations",
                description="Cross-tenant branch",
                amount=Decimal("10.00"),
                currency="NPR",
                expense_date=date(2026, 11, 19),
                recorded_by=self.user,
            )

    def test_branch_invitation_cannot_reference_another_tenant_branch(self):
        invitation = StaffInvitation.objects.create(
            organization=self.org,
            invited_by=self.user,
            email="invitee@example.test",
            role=Membership.Role.COLLECTION_OPERATOR,
            token_hash="a" * 64,
            expires_at=datetime(2026, 12, 1, tzinfo=UTC),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            invitation.branches.add(self.other_branch)

    def test_foreign_party_and_pricing_cannot_be_saved_on_collection(self):
        base = {
            "organization": self.org,
            "branch": self.branch,
            "recorded_by": self.user,
            "collected_at": datetime(2026, 11, 19, 6, tzinfo=UTC),
            "quantity_litres": Decimal("1.000"),
            "snf": Decimal("8.000"),
            "fat": Decimal("4.000"),
            "lactose": Decimal("4.500"),
            "milk_rate": Decimal("72.50"),
            "total_amount": Decimal("72.50"),
            "pricing_snapshot": {},
        }
        with self.assertRaises(IntegrityError), transaction.atomic():
            MilkCollection.objects.create(
                **base,
                reference="CROSS-PARTY",
                farmer=self.other_farmer,
                pricing=self.pricing,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MilkCollection.objects.create(
                **base,
                reference="CROSS-PRICE",
                farmer=self.farmer,
                pricing=self.other_pricing,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MilkCollection.objects.create(
                **{**base, "total_amount": Decimal("71.00")},
                reference="WRONG-TOTAL",
                farmer=self.farmer,
                pricing=self.pricing,
            )

    def test_foreign_party_cannot_be_saved_on_payment(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(
                organization=self.org,
                branch=self.branch,
                reference="CROSS-PAYMENT",
                direction=Payment.Direction.OUTGOING,
                farmer=self.other_farmer,
                amount=Decimal("10.00"),
                currency="NPR",
                method=Payment.Method.CASH,
                recorded_by=self.user,
            )

    def test_payment_direction_must_match_party_type(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(
                organization=self.org,
                branch=self.branch,
                reference="WRONG-DIRECTION",
                direction=Payment.Direction.OUTGOING,
                customer=self.customer,
                amount=Decimal("10.00"),
                currency="NPR",
                method=Payment.Method.CASH,
                recorded_by=self.user,
            )

    def test_branch_assignments_and_ledger_lines_are_tenant_consistent(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BranchAssignment.objects.create(membership=self.membership, branch=self.other_branch)

        period = AccountingPeriod.objects.create(
            organization=self.org,
            code="FY-26",
            name="Fiscal 2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        entry = JournalEntry.objects.create(
            organization=self.org,
            branch=self.branch,
            period=period,
            reference="J-1",
            entry_date=date(2026, 11, 19),
            description="Tenant integrity check",
            created_by=self.user,
        )
        foreign_account = self._account(self.other_org, "B-100")
        with self.assertRaises(IntegrityError), transaction.atomic():
            JournalLine.objects.create(
                entry=entry,
                account=foreign_account,
                line_number=1,
                debit=Decimal("10.00"),
            )

    def test_journal_cannot_be_posted_unbalanced_or_outside_its_period(self):
        period = AccountingPeriod.objects.create(
            organization=self.org,
            code="FY-26",
            name="Fiscal 2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            JournalEntry.objects.create(
                organization=self.org,
                branch=self.branch,
                period=period,
                reference="INVALID-POSTED",
                entry_date=date(2026, 11, 19),
                description="Unbalanced entry",
                created_by=self.user,
                status=JournalEntry.Status.POSTED,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            JournalEntry.objects.create(
                organization=self.org,
                branch=self.branch,
                period=period,
                reference="OUTSIDE-PERIOD",
                entry_date=date(2027, 1, 1),
                description="Out-of-period entry",
                created_by=self.user,
            )

    def test_ledger_configuration_rejects_foreign_control_account(self):
        valid_accounts = [self._account(self.org, f"A-{index}") for index in range(10)]
        valid_accounts[0] = self._account(self.other_org, "FOREIGN-CASH")
        field_names = (
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
        with self.assertRaises(IntegrityError), transaction.atomic():
            LedgerConfiguration.objects.create(
                organization=self.org,
                **dict(zip(field_names, valid_accounts, strict=True)),
            )

    def test_overlapping_accounting_periods_and_schedules_are_rejected(self):
        AccountingPeriod.objects.create(
            organization=self.org,
            code="FY-26",
            name="Fiscal 2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            AccountingPeriod.objects.create(
                organization=self.org,
                code="FY-26-2",
                name="Overlapping fiscal period",
                starts_on=date(2026, 12, 1),
                ends_on=date(2027, 11, 30),
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            self._pricing(self.org, 2)

        QualityConfiguration.objects.create(
            organization=self.org,
            branch=self.branch,
            version=1,
            snf_min=Decimal("0"),
            snf_max=Decimal("10"),
            fat_min=Decimal("0"),
            fat_max=Decimal("10"),
            lactose_min=Decimal("0"),
            lactose_max=Decimal("10"),
            effective_from=date(2026, 1, 1),
            is_approved=True,
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            QualityConfiguration.objects.create(
                organization=self.org,
                branch=self.branch,
                version=2,
                snf_min=Decimal("0"),
                snf_max=Decimal("10"),
                fat_min=Decimal("0"),
                fat_max=Decimal("10"),
                lactose_min=Decimal("0"),
                lactose_max=Decimal("10"),
                effective_from=date(2026, 12, 1),
                is_approved=True,
                created_by=self.user,
            )

    def test_inventory_movement_updates_balance_and_reversal_is_integral(self):
        item = InventoryItem.objects.create(
            organization=self.org,
            branch=self.branch,
            code="I-1",
            name="Feed",
            current_stock=Decimal("0.000"),
        )
        movement = StockMovement.objects.create(
            organization=self.org,
            item=item,
            kind=StockMovement.Kind.PURCHASE,
            quantity_delta=Decimal("2.000"),
            reason="Direct model write",
            created_by=self.user,
        )
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("2.000"))

        movement.delete()
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("0.000"))

    def test_inventory_supplier_and_movement_must_match_tenant_and_balance(self):
        supplier = Supplier.objects.create(
            organization=self.other_org, code="S-1", name="Foreign supplier"
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            InventoryItem.objects.create(
                organization=self.org,
                branch=self.branch,
                supplier=supplier,
                code="CROSS-SUPPLIER",
                name="Invalid item",
            )

        foreign_item = InventoryItem.objects.create(
            organization=self.other_org,
            branch=self.other_branch,
            code="FOREIGN-ITEM",
            name="Foreign item",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            StockMovement.objects.create(
                organization=self.org,
                item=foreign_item,
                kind=StockMovement.Kind.PURCHASE,
                quantity_delta=Decimal("1.000"),
                reason="Cross-tenant movement",
                created_by=self.user,
            )

        local_item = InventoryItem.objects.create(
            organization=self.org,
            branch=self.branch,
            code="EMPTY-ITEM",
            name="Empty item",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            StockMovement.objects.create(
                organization=self.org,
                item=local_item,
                kind=StockMovement.Kind.USAGE,
                quantity_delta=Decimal("-1.000"),
                reason="Overdraw",
                created_by=self.user,
            )

    def test_database_rejects_negative_inventory_and_invalid_payment_values(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            InventoryItem.objects.create(
                organization=self.org,
                branch=self.branch,
                code="NEGATIVE",
                name="Invalid stock",
                current_stock=Decimal("-1.000"),
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(
                organization=self.org,
                branch=self.branch,
                reference="NEGATIVE-PAYMENT",
                direction=Payment.Direction.INCOMING,
                customer=self.customer,
                amount=Decimal("-1.00"),
                currency="NPR",
                method=Payment.Method.CASH,
                recorded_by=self.user,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MilkCollection.objects.create(
                organization=self.org,
                branch=self.branch,
                reference="ZERO-QUANTITY",
                farmer=self.farmer,
                recorded_by=self.user,
                collected_at=datetime(2026, 11, 19, 6, tzinfo=UTC),
                quantity_litres=Decimal("0.000"),
                snf=Decimal("8.000"),
                fat=Decimal("4.000"),
                lactose=Decimal("4.500"),
                milk_rate=Decimal("72.50"),
                total_amount=Decimal("0.00"),
                pricing=self.pricing,
                pricing_snapshot={},
            )
