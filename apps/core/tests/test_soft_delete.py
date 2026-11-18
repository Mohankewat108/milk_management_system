from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.finance.models import Expense, Payment
from apps.inventory.models import InventoryItem, Supplier
from apps.organizations.models import Branch, Organization
from apps.parties.models import Customer
from apps.core.soft_delete import restore_record, soft_delete_record


User = get_user_model()


class CentralSoftDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="trash-owner", email="trash-owner@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.user, name="Trash Dairy", slug="trash-dairy",
        )
        self.branch = Branch.objects.create(
            organization=self.organization, code="MAIN", name="Main",
        )
        self.customer = Customer.objects.create(
            organization=self.organization, branch=self.branch,
            code="C001", full_name="Test Customer",
        )

    def test_customer_can_be_soft_deleted_and_restored(self):
        soft_delete_record(key="customer", record=self.customer, actor=self.user)
        self.customer.refresh_from_db()
        self.assertIsNotNone(self.customer.deleted_at)
        self.assertEqual(self.customer.deleted_by, self.user)
        restore_record(record=self.customer)
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.deleted_at)
        self.assertTrue(self.customer.is_active)

    def test_supplier_can_be_soft_deleted_and_restored(self):
        supplier = Supplier.objects.create(
            organization=self.organization, code="SUP1", name="Milk Equipment",
        )
        soft_delete_record(key="supplier", record=supplier, actor=self.user)
        supplier.refresh_from_db()
        self.assertTrue(supplier.is_active)
        restore_record(record=supplier)
        supplier.refresh_from_db()
        self.assertTrue(supplier.is_active)
        self.assertIsNone(supplier.deleted_at)

    def test_zero_stock_item_without_movement_can_be_trashed(self):
        item = InventoryItem.objects.create(
            organization=self.organization, branch=self.branch,
            code="ITEM1", name="Empty Can", current_stock=0,
        )
        soft_delete_record(key="inventory_item", record=item, actor=self.user)
        item.refresh_from_db()
        self.assertIsNotNone(item.deleted_at)
        self.assertFalse(item.is_active)

    def test_inventory_item_with_stock_cannot_be_trashed(self):
        item = InventoryItem.objects.create(
            organization=self.organization, branch=self.branch,
            code="ITEM2", name="Full Can", current_stock=5,
        )
        with self.assertRaises(ValidationError):
            soft_delete_record(key="inventory_item", record=item, actor=self.user)

    def test_completed_payment_cannot_be_trashed(self):
        payment = Payment.objects.create(
            organization=self.organization, branch=self.branch,
            reference="PAY-TEST", direction=Payment.Direction.INCOMING,
            customer=self.customer, amount="10.00", currency="NPR",
            method=Payment.Method.CASH, status=Payment.Status.COMPLETED,
            recorded_by=self.user,
        )
        with self.assertRaises(ValidationError):
            soft_delete_record(key="payment", record=payment, actor=self.user)

    def test_branch_with_operational_history_cannot_be_trashed(self):
        # The customer is attached to the branch; branch deletion would orphan
        # an active operational master record.
        with self.assertRaises(ValidationError):
            soft_delete_record(key="branch", record=self.branch, actor=self.user)
