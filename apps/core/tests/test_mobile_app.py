from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.organizations.models import Membership, Organization
from apps.parties.models import Customer, Farmer

User = get_user_model()


class MobileAppTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mobile-owner",
            email="mobile-owner@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.user,
            name="Mobile Test Dairy",
            slug="mobile-test-dairy",
        )

    def test_mobile_home_requires_authentication(self):
        response = self.client.get(reverse("mobile_app"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_owner_sees_existing_dairy_modules(self):
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("mobile_app"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Milk collection")
        self.assertContains(response, "Farmers")
        self.assertContains(response, "Payments")
        self.assertContains(response, "Reports")

    def test_mobile_home_hides_modules_without_permissions(self):
        membership = Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.SUPPORT,
        )
        membership.branch_assignments.all().delete()
        self.client.force_login(self.user)
        response = self.client.get(reverse("mobile_app"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Farmers")
        self.assertNotContains(response, "Milk collection")
        self.assertNotContains(response, "Payments")

    def test_farmer_accounts_are_sent_to_farmer_portal(self):
        Farmer.objects.create(
            organization=self.organization,
            branch=None,
            user=self.user,
            full_name="Mobile Farmer",
            code="MF-001",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("mobile_app"))
        self.assertRedirects(response, reverse("farmer_portal:home"))

    def test_customer_accounts_are_sent_to_customer_portal(self):
        Customer.objects.create(
            organization=self.organization,
            branch=None,
            user=self.user,
            full_name="Mobile Customer",
            code="MC-001",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("mobile_app"))
        self.assertRedirects(response, reverse("customer_portal:home"))

    def test_manifest_is_valid_and_installable(self):
        response = self.client.get(reverse("mobile_manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["start_url"], "/app/")
        self.assertEqual(response.json()["display"], "standalone")

    def test_service_worker_never_caches_private_business_routes(self):
        response = self.client.get(reverse("mobile_service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/business/", response.content)
        self.assertIn(b"/accounts/", response.content)
        self.assertIn("no-cache", response["Cache-Control"])

    def test_offline_screen_renders(self):
        response = self.client.get(reverse("mobile_offline"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You are currently offline")
