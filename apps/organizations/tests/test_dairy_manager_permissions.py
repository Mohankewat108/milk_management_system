from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.organizations.models import (
    Branch,
    BranchAssignment,
    Membership,
    Organization,
    OrganizationPermission,
)
from apps.organizations.permissions import accessible_branch_ids, can_access_branch

User = get_user_model()


class DairyManagerPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="dairy-owner", email="owner@manager-test.example", password="LongDemoPass!123"
        )
        self.manager_user = User.objects.create_user(
            username="dairy-manager",
            email="manager@manager-test.example",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.owner, name="Manager Dairy", slug="manager-dairy"
        )
        Membership.objects.create(
            user=self.owner, organization=self.organization, role=Membership.Role.OWNER
        )
        self.manager = Membership.objects.create(
            user=self.manager_user,
            organization=self.organization,
            role=Membership.Role.DAIRY_MANAGER,
        )
        self.branch_a = Branch.objects.create(
            organization=self.organization, code="A", name="Branch A"
        )
        self.branch_b = Branch.objects.create(
            organization=self.organization, code="B", name="Branch B"
        )
        BranchAssignment.objects.create(membership=self.manager, branch=self.branch_a)

    def grant(self, key):
        permission = OrganizationPermission.objects.get(key=key)
        self.manager.permissions.add(permission)
        return permission

    def test_dairy_manager_is_always_limited_to_assigned_branches(self):
        self.grant("dashboard.view")
        self.client.force_login(self.manager_user)

        response = self.client.get(
            reverse("business:dashboard", kwargs={"organization_slug": self.organization.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["branch_count"], 1)
        self.assertEqual(accessible_branch_ids(self.manager), [self.branch_a.pk])
        self.assertTrue(can_access_branch(self.manager, self.branch_a))
        self.assertFalse(can_access_branch(self.manager, self.branch_b))

    def test_dairy_manager_without_dashboard_permission_is_denied(self):
        self.client.force_login(self.manager_user)

        response = self.client.get(
            reverse("business:dashboard", kwargs={"organization_slug": self.organization.slug})
        )

        self.assertEqual(response.status_code, 404)

    def test_dairy_manager_needs_explicit_collection_view_permission(self):
        self.client.force_login(self.manager_user)
        url = reverse("collections:list", kwargs={"organization_slug": self.organization.slug})

        denied = self.client.get(url)
        self.assertEqual(denied.status_code, 404)

        self.grant("collections.view")
        allowed = self.client.get(url)
        self.assertEqual(allowed.status_code, 200)

    def test_dairy_manager_cannot_access_another_organisation(self):
        other_owner = User.objects.create_user(
            username="other-dairy-owner",
            email="other-owner@manager-test.example",
            password="LongDemoPass!123",
        )
        other = Organization.objects.create(
            owner=other_owner, name="Other Dairy", slug="other-manager-dairy"
        )
        Membership.objects.create(
            user=other_owner, organization=other, role=Membership.Role.OWNER
        )
        self.grant("dashboard.view")
        self.client.force_login(self.manager_user)

        response = self.client.get(
            reverse("business:dashboard", kwargs={"organization_slug": other.slug})
        )

        self.assertEqual(response.status_code, 404)
