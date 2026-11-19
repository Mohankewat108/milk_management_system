from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.inventory.models import InventoryItem, StockMovement
from apps.inventory.services import adjust_stock, move_stock
from apps.organizations.models import Branch, BranchAssignment, Membership, Organization

User = get_user_model()


class InventoryMovementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="inventory-user", email="inventory@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.user, name="Inventory Dairy", slug="inventory-dairy"
        )
        self.branch = Branch.objects.create(
            organization=self.organization, code="MAIN", name="Main"
        )
        Membership.objects.create(
            user=self.user, organization=self.organization, role=Membership.Role.OWNER
        )
        self.item = InventoryItem.objects.create(
            organization=self.organization, branch=self.branch,
            code="CAN-01", name="Milk can",
        )

    def test_purchase_and_usage_keep_stock_ledger_balanced(self):
        purchase = move_stock(
            item_id=self.item.pk, organization=self.organization, actor=self.user,
            kind=StockMovement.Kind.PURCHASE, quantity="10.000", reason="Opening purchase",
        )
        usage = move_stock(
            item_id=self.item.pk, organization=self.organization, actor=self.user,
            kind=StockMovement.Kind.USAGE, quantity="3.000", reason="Daily use",
        )
        self.item.refresh_from_db()
        self.assertEqual(purchase.quantity_delta, Decimal("10.000"))
        self.assertEqual(usage.quantity_delta, Decimal("-3.000"))
        self.assertEqual(self.item.current_stock, Decimal("7.000"))

    def test_stock_writes_require_assigned_branch(self):
        other_branch = Branch.objects.create(
            organization=self.organization, code="SECOND", name="Second"
        )
        staff = User.objects.create_user(
            username="inventory-staff", email="inventory-staff@example.test",
            password="LongDemoPass!123",
        )
        membership = Membership.objects.create(
            user=staff, organization=self.organization,
            role=Membership.Role.INVENTORY_MANAGER,
        )
        BranchAssignment.objects.create(membership=membership, branch=other_branch)

        with self.assertRaises(PermissionDenied):
            move_stock(
                item_id=self.item.pk, organization=self.organization, actor=staff,
                kind=StockMovement.Kind.PURCHASE, quantity="5", reason="Wrong branch",
            )
        with self.assertRaises(PermissionDenied):
            adjust_stock(
                item_id=self.item.pk, organization=self.organization, actor=staff,
                signed_delta="2", reason="Wrong branch",
            )

        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("0.000"))
        self.assertEqual(self.item.movements.count(), 0)

    def test_stock_writes_reject_actor_without_membership(self):
        outsider = User.objects.create_user(
            username="inventory-outsider", email="inventory-outsider@example.test",
            password="LongDemoPass!123",
        )
        with self.assertRaises(PermissionDenied):
            move_stock(
                item_id=self.item.pk, organization=self.organization, actor=outsider,
                kind=StockMovement.Kind.PURCHASE, quantity="5", reason="No membership",
            )
        with self.assertRaises(PermissionDenied):
            adjust_stock(
                item_id=self.item.pk, organization=self.organization, actor=outsider,
                signed_delta="2", reason="No membership",
            )

    def test_negative_stock_is_rejected(self):
        with self.assertRaises(ValidationError):
            move_stock(
                item_id=self.item.pk, organization=self.organization, actor=self.user,
                kind=StockMovement.Kind.USAGE, quantity="1", reason="Not in stock",
            )
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("0.000"))

    def test_stock_item_cannot_be_moved_from_another_tenant(self):
        other = Organization.objects.create(
            owner=self.user, name="Other Inventory", slug="other-inventory"
        )
        foreign_branch = Branch.objects.create(
            organization=other, code="MAIN", name="Other Main"
        )
        foreign_item = InventoryItem.objects.create(
            organization=other, branch=foreign_branch, code="CAN-02", name="Other can"
        )
        with self.assertRaises(InventoryItem.DoesNotExist):
            move_stock(
                item_id=foreign_item.pk, organization=self.organization, actor=self.user,
                kind=StockMovement.Kind.PURCHASE, quantity="2", reason="Cross-tenant attempt",
            )
