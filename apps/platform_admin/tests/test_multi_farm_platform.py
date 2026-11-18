from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.organizations.models import Branch, Membership, Organization
from apps.parties.models import Customer


User = get_user_model()


class PlatformMultiFarmTests(TestCase):
    def setUp(self):
        self.platform_owner = User.objects.create_superuser(
            username="platform-root",
            email="platform@example.test",
            password="VeryStrongPlatformPass!2026",
        )
        self.farm_owner = User.objects.create_user(
            username="farm-owner",
            email="farm.owner@example.test",
            password="VeryStrongFarmPass!2026",
        )

    def test_platform_owner_can_create_multiple_farms_for_same_owner(self):
        self.client.force_login(self.platform_owner)
        url = reverse("platform:organization_create")
        for farm_name in ("Himalayan Dairy", "Green Valley Milk"):
            response = self.client.post(url, {
                "owner": str(self.farm_owner.pk),
                "name": farm_name,
                "legal_name": "",
                "registration_number": "",
                "business_type": "Dairy farm",
                "email": "",
                "phone": "",
                "country": "Nepal",
                "currency": "NPR",
                "timezone": "Asia/Kathmandu",
                "address": "Parasi, Nepal",
            })
            self.assertRedirects(response, reverse("platform:dashboard"))

        farms = Organization.objects.filter(owner=self.farm_owner)
        self.assertEqual(farms.count(), 2)
        self.assertEqual(
            Membership.objects.filter(
                user=self.farm_owner,
                organization__in=farms,
                role=Membership.Role.OWNER,
                status=Membership.Status.ACTIVE,
            ).count(),
            2,
        )
        self.assertEqual(Branch.objects.filter(organization__in=farms, code="MAIN").count(), 2)

    def test_non_platform_user_cannot_create_farms_from_platform(self):
        self.client.force_login(self.farm_owner)
        response = self.client.get(reverse("platform:organization_create"))
        self.assertEqual(response.status_code, 302)

    def test_customers_are_separate_records_per_farm(self):
        first = Organization.objects.create(
            owner=self.farm_owner, name="First Dairy", slug="first-dairy"
        )
        second = Organization.objects.create(
            owner=self.farm_owner, name="Second Dairy", slug="second-dairy"
        )
        Customer.objects.create(
            organization=first, code="C001", full_name="Customer One"
        )
        Customer.objects.create(
            organization=first, code="C002", full_name="Customer Two"
        )
        Customer.objects.create(
            organization=second, code="C001", full_name="Customer Three"
        )
        self.assertEqual(first.customers.count(), 2)
        self.assertEqual(second.customers.count(), 1)
        self.assertNotEqual(first.pk, second.pk)
