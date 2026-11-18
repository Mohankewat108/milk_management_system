from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.collections.models import MilkCollection
from apps.organizations.models import Branch, BranchAssignment, Membership, Organization
from apps.parties.models import Customer, Farmer
from apps.pricing.models import PricingConfiguration

User = get_user_model()


class PartyProfileTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="profile-owner", email="profile-owner@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.owner, name="Profile Dairy", slug="profile-dairy", is_demo=True,
        )
        self.branch = Branch.objects.create(
            organization=self.organization, code="MAIN", name="Main Branch",
        )
        self.membership = Membership.objects.get(user=self.owner, organization=self.organization)
        self.customer = Customer.objects.create(
            organization=self.organization, branch=self.branch,
            code="C001", full_name="Test Customer", phone="9800000000",
        )
        self.farmer = Farmer.objects.create(
            organization=self.organization, branch=self.branch,
            code="F001", full_name="Test Farmer",
        )
        self.pricing = PricingConfiguration.objects.create(
            organization=self.organization, version=1,
            snf_rate=Decimal("5.0000"), fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=datetime(2026, 1, 1).date(),
            is_approved=True, created_by=self.owner,
        )

    def _collection(self, party, status, reference, day):
        kwargs = {"customer": party} if isinstance(party, Customer) else {"farmer": party}
        return MilkCollection.objects.create(
            organization=self.organization, branch=self.branch,
            reference=reference, recorded_by=self.owner,
            collected_at=datetime(2026, 11, day, 6, 0, tzinfo=dt_timezone.utc),
            quantity_litres=Decimal("2.500"), snf=Decimal("8.000"),
            fat=Decimal("4.000"), lactose=Decimal("4.500"),
            milk_rate=Decimal("72.50"), total_amount=Decimal("181.25"),
            pricing=self.pricing, pricing_snapshot={"version": 1},
            status=status, **kwargs,
        )

    def test_customer_profile_sums_only_approved_collections(self):
        self._collection(self.customer, MilkCollection.Status.APPROVED, "C-APP", 18)
        self._collection(self.customer, MilkCollection.Status.SUBMITTED, "C-SUB", 17)
        self._collection(self.customer, MilkCollection.Status.REVERSED, "C-REV", 16)
        self.client.force_login(self.owner)
        url = reverse("parties:customer_detail", args=[self.organization.slug, self.customer.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["metrics"]["lifetime_litres"], Decimal("2.500"))
        self.assertEqual(response.context["metrics"]["lifetime_value"], Decimal("181.25"))
        self.assertEqual(response.context["status_summary"]["submitted"], 1)
        self.assertEqual(response.context["status_summary"]["reversed"], 1)

    def test_farmer_profile_is_separate_and_scoped(self):
        self._collection(self.farmer, MilkCollection.Status.APPROVED, "F-APP", 18)
        self.client.force_login(self.owner)
        url = reverse("parties:farmer_detail", args=[self.organization.slug, self.farmer.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["kind"], "farmer")
        self.assertEqual(response.context["metrics"]["lifetime_litres"], Decimal("2.500"))

    def test_foreign_tenant_party_uuid_is_not_resolvable(self):
        other = Organization.objects.create(
            owner=self.owner, name="Other Dairy", slug="other-dairy", is_demo=True,
        )
        foreign = Customer.objects.create(
            organization=other, code="C-FOREIGN", full_name="Foreign Customer",
        )
        self.client.force_login(self.owner)
        url = reverse("parties:customer_detail", args=[self.organization.slug, foreign.pk])
        self.assertEqual(self.client.get(url).status_code, 404)


    def test_branch_restricted_user_cannot_open_other_branch_party(self):
        other_branch = Branch.objects.create(
            organization=self.organization, code="REMOTE", name="Remote Branch",
        )
        remote_customer = Customer.objects.create(
            organization=self.organization, branch=other_branch,
            code="C-REMOTE", full_name="Remote Customer",
        )
        staff = User.objects.create_user(
            username="branch-staff", email="branch-staff@example.test",
            password="LongDemoPass!123",
        )
        membership = Membership.objects.create(
            user=staff, organization=self.organization,
            role=Membership.Role.BRANCH_MANAGER,
            status=Membership.Status.ACTIVE,
        )
        BranchAssignment.objects.create(membership=membership, branch=self.branch)
        self.client.force_login(staff)
        url = reverse("parties:customer_detail", args=[self.organization.slug, remote_customer.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_farmer_list_search_and_owner_directory_profile_link(self):
        self.client.force_login(self.owner)
        url = reverse("parties:farmers", args=[self.organization.slug])
        response = self.client.get(url, {"q": "F001", "status": "active"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse(
            "parties:farmer_detail", args=[self.organization.slug, self.farmer.pk]
        ))

    def test_search_supports_email_and_filters_inactive_customers(self):
        self.customer.email = "find-me@example.test"
        self.customer.is_active = False
        self.customer.save()
        self.client.force_login(self.owner)
        url = reverse("parties:customers", args=[self.organization.slug])
        response = self.client.get(url, {"q": "find-me@example.test", "status": "inactive"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [self.customer])
