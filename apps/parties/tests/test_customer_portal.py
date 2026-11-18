from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.organizations.models import Branch, Organization
from apps.parties.models import Customer

User = get_user_model()


class CustomerPortalAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="portal-owner", email="owner@portal.test", password="Strong-password-123"
        )
        self.customer_user = User.objects.create_user(
            username="portal-customer", email="customer@portal.test", password="Strong-password-123"
        )
        self.other_user = User.objects.create_user(
            username="other-customer", email="other@portal.test", password="Strong-password-123"
        )
        self.organization = Organization.objects.create(
            owner=self.owner, name="Portal Dairy", slug="portal-dairy", is_demo=True
        )
        self.branch = Branch.objects.create(
            organization=self.organization, code="MAIN", name="Main Branch"
        )
        self.customer = Customer.objects.create(
            organization=self.organization, branch=self.branch, user=self.customer_user,
            code="C001", full_name="Portal Customer", email="customer@portal.test",
        )

    def test_customer_can_open_own_portal(self):
        self.client.force_login(self.customer_user)
        response = self.client.get(reverse("customer_portal:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portal Customer")
        self.assertContains(response, "C001")

    def test_unlinked_or_different_user_cannot_open_customer_portal(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("customer_portal:home"))
        self.assertEqual(response.status_code, 403)

    def test_customer_can_download_csv_statement(self):
        self.client.force_login(self.customer_user)
        response = self.client.get(reverse("customer_portal:statement_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("customer-statement-C001", response["Content-Disposition"])
        self.assertIn(b"Collection date", response.content)
        self.assertIn(b"Completed payments", response.content)
