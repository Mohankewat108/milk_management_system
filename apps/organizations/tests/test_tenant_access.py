from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.organizations.models import Membership, Organization

User = get_user_model()


class TenantAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tenant-a-owner", email="owner-a@example.test", password="LongDemoPass!123"
        )
        self.org_a = Organization.objects.create(
            owner=self.user, name="Tenant A", slug="tenant-a", is_demo=True
        )
        Membership.objects.create(
            user=self.user, organization=self.org_a, role=Membership.Role.OWNER
        )
        self.org_b_owner = User.objects.create_user(
            username="tenant-b-owner", email="owner-b@example.test", password="LongDemoPass!123"
        )
        self.org_b = Organization.objects.create(
            owner=self.org_b_owner, name="Tenant B", slug="tenant-b", is_demo=True
        )
        Membership.objects.create(
            user=self.org_b_owner, organization=self.org_b, role=Membership.Role.OWNER
        )

    def test_member_can_access_own_workspace(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("business:dashboard", kwargs={"organization_slug": self.org_a.slug})
        )
        self.assertEqual(response.status_code, 200)

    def test_member_cannot_access_another_tenant_workspace_by_slug(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("business:dashboard", kwargs={"organization_slug": self.org_b.slug})
        )
        self.assertEqual(response.status_code, 404)

    def test_suspended_membership_cannot_access_workspace(self):
        Membership.objects.filter(user=self.user, organization=self.org_a).update(
            status=Membership.Status.SUSPENDED
        )
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("business:dashboard", kwargs={"organization_slug": self.org_a.slug})
        )
        self.assertEqual(response.status_code, 404)
