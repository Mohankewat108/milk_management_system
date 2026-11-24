from datetime import UTC, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.collections.models import MilkCollection
from apps.collections.services import create_collection
from apps.organizations.models import Branch, BranchAssignment, Membership, Organization
from apps.parties.models import Farmer
from apps.pricing.models import PricingConfiguration

User = get_user_model()


class CollectionWorkspaceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="workspace-owner",
            email="workspace-owner@example.test",
            password="StrongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.owner, name="Workspace Dairy", slug="workspace-dairy"
        )
        self.branch = Branch.objects.create(
            organization=self.organization, code="MAIN", name="Main Branch"
        )
        Membership.objects.create(
            user=self.owner, organization=self.organization, role=Membership.Role.OWNER
        )
        self.farmer = Farmer.objects.create(
            organization=self.organization,
            branch=self.branch,
            code="F001",
            full_name="Avery Farmer",
        )
        PricingConfiguration.objects.create(
            organization=self.organization,
            version=1,
            snf_rate=Decimal("5.0000"),
            fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=datetime(2026, 1, 1).date(),
            is_approved=True,
            created_by=self.owner,
        )
        self.url = reverse(
            "collections:list", kwargs={"organization_slug": self.organization.slug}
        )
        self.client.force_login(self.owner)

    def test_workspace_renders_entry_and_records_together(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="collection-entry-panel"')
        self.assertContains(response, 'name="quantity_litres"')
        self.assertContains(response, "Collection records")

    def test_integrated_form_creates_collection_and_redirects_to_workspace(self):
        response = self.client.post(
            self.url,
            {
                "idempotency_key": "integrated-workspace-request",
                "branch": str(self.branch.pk),
                "party_type": "farmer",
                "farmer": str(self.farmer.pk),
                "customer": "",
                "collected_at": "2026-11-24T06:00",
                "quantity_litres": "2.500",
                "snf": "8.000",
                "fat": "4.000",
                "lactose": "4.500",
                "lactometer_reading": "",
                "milk_temperature_c": "",
                "sample_reference": "",
                "quality_test_method": "",
                "notes": "",
            },
        )

        self.assertRedirects(response, self.url)
        self.assertEqual(MilkCollection.objects.filter(organization=self.organization).count(), 1)

    def test_branch_and_party_filters_restrict_records_and_persist_in_pagination(self):
        create_collection(
            organization=self.organization,
            branch=self.branch,
            actor=self.owner,
            collected_at=datetime(2026, 11, 24, 6, tzinfo=UTC),
            quantity_litres="2.500",
            snf="8.000",
            fat="4.000",
            lactose="4.500",
            farmer=self.farmer,
        )

        response = self.client.get(
            self.url, {"branch": str(self.branch.pk), "party": "Avery"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual(response.context["branch_filter"], str(self.branch.pk))
        self.assertEqual(response.context["party_filter"], "Avery")
        self.assertIn("branch=", response.context["filter_querystring"])
        self.assertIn("party=Avery", response.context["filter_querystring"])

    def test_view_only_quality_officer_cannot_submit_collection(self):
        viewer = User.objects.create_user(
            username="workspace-viewer",
            email="workspace-viewer@example.test",
            password="StrongDemoPass!123",
        )
        membership = Membership.objects.create(
            user=viewer,
            organization=self.organization,
            role=Membership.Role.QUALITY_OFFICER,
        )
        BranchAssignment.objects.create(membership=membership, branch=self.branch)
        self.client.force_login(viewer)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="collection-entry-panel"')

        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MilkCollection.objects.filter(organization=self.organization).count(), 0)
