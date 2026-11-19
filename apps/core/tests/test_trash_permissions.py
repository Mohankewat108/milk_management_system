from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.inventory.models import InventoryItem
from apps.organizations.models import Branch, BranchAssignment, Membership, Organization

User = get_user_model()


class TrashDeleteRoleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="trash-role-owner",
            email="trash-role-owner@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.owner,
            name="Trash Role Dairy",
            slug="trash-role-dairy",
        )
        self.branch = Branch.objects.create(
            organization=self.organization,
            code="MAIN",
            name="Main",
        )
        self.item = InventoryItem.objects.create(
            organization=self.organization,
            branch=self.branch,
            code="ITEM-001",
            name="Empty milk can",
            current_stock="0.000",
        )

    def test_assigned_inventory_manager_can_trash_inventory_item(self):
        manager = User.objects.create_user(
            username="trash-inventory-manager",
            email="trash-inventory-manager@example.test",
            password="LongDemoPass!123",
        )
        membership = Membership.objects.create(
            user=manager,
            organization=self.organization,
            role=Membership.Role.INVENTORY_MANAGER,
        )
        BranchAssignment.objects.create(membership=membership, branch=self.branch)
        self.client.force_login(manager)

        response = self.client.post(
            reverse(
                "business:trash_delete",
                kwargs={
                    "organization_slug": self.organization.slug,
                    "model_key": "inventory_item",
                    "object_id": self.item.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.deleted_at)

    def test_role_not_allowed_for_inventory_item_cannot_trash_it(self):
        support = User.objects.create_user(
            username="trash-support",
            email="trash-support@example.test",
            password="LongDemoPass!123",
        )
        membership = Membership.objects.create(
            user=support,
            organization=self.organization,
            role=Membership.Role.SUPPORT,
        )
        BranchAssignment.objects.create(membership=membership, branch=self.branch)
        self.client.force_login(support)

        response = self.client.post(
            reverse(
                "business:trash_delete",
                kwargs={
                    "organization_slug": self.organization.slug,
                    "model_key": "inventory_item",
                    "object_id": self.item.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.deleted_at)
