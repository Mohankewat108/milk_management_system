from datetime import UTC, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.collections.models import MilkCollection
from apps.finance.models import Payment
from apps.organizations.models import Branch, Organization
from apps.parties.models import Farmer
from apps.pricing.models import PricingConfiguration

User = get_user_model()


class FarmerPortalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="farmer-login",
            email="farmer-login@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.user,
            name="Farmer Portal Dairy",
            slug="farmer-portal-dairy",
        )
        self.branch = Branch.objects.create(
            organization=self.organization,
            code="MAIN",
            name="Main Branch",
        )
        self.farmer = Farmer.objects.create(
            organization=self.organization,
            branch=self.branch,
            user=self.user,
            code="F-100",
            full_name="Portal Farmer",
            is_active=True,
        )
        self.pricing = PricingConfiguration.objects.create(
            organization=self.organization,
            version=1,
            snf_rate=Decimal("5.0000"),
            fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=datetime(2026, 1, 1).date(),
            is_approved=True,
            created_by=self.user,
        )

    def create_collection(self, farmer, reference, status):
        return MilkCollection.objects.create(
            organization=self.organization,
            branch=self.branch,
            reference=reference,
            farmer=farmer,
            recorded_by=self.user,
            collected_at=datetime(2026, 11, 19, 6, 0, tzinfo=UTC),
            quantity_litres=Decimal("3.000"),
            snf=Decimal("8.000"),
            fat=Decimal("4.000"),
            lactose=Decimal("4.500"),
            milk_rate=Decimal("72.50"),
            total_amount=Decimal("217.50"),
            pricing=self.pricing,
            pricing_snapshot={"version": 1},
            status=status,
        )

    def test_farmer_sees_only_own_approved_collections_and_payments(self):
        self.create_collection(self.farmer, "F-APPROVED", MilkCollection.Status.APPROVED)
        self.create_collection(self.farmer, "F-SUBMITTED", MilkCollection.Status.SUBMITTED)
        other_user = User.objects.create_user(
            username="other-farmer",
            email="other-farmer@example.test",
            password="LongDemoPass!123",
        )
        other_farmer = Farmer.objects.create(
            organization=self.organization,
            branch=self.branch,
            user=other_user,
            code="F-200",
            full_name="Other Farmer",
        )
        self.create_collection(other_farmer, "OTHER-APPROVED", MilkCollection.Status.APPROVED)
        Payment.objects.create(
            organization=self.organization,
            branch=self.branch,
            reference="F-PAY-001",
            direction=Payment.Direction.OUTGOING,
            farmer=self.farmer,
            amount=Decimal("100.00"),
            currency=self.organization.currency,
            method=Payment.Method.BANK,
            status=Payment.Status.COMPLETED,
            paid_at=datetime(2026, 11, 19, 12, 0, tzinfo=UTC),
            recorded_by=self.user,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("farmer_portal:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "F-APPROVED")
        self.assertNotContains(response, "F-SUBMITTED")
        self.assertNotContains(response, "OTHER-APPROVED")
        self.assertContains(response, "F-PAY-001")

    def test_farmer_login_redirects_to_farmer_portal(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.email, "password": "LongDemoPass!123"},
        )
        self.assertRedirects(response, reverse("farmer_portal:home"))

    def test_unlinked_account_cannot_open_farmer_portal(self):
        unlinked = User.objects.create_user(
            username="unlinked",
            email="unlinked@example.test",
            password="LongDemoPass!123",
        )
        self.client.force_login(unlinked)
        response = self.client.get(reverse("farmer_portal:home"))
        self.assertEqual(response.status_code, 403)

    def test_inactive_or_soft_deleted_farmer_cannot_open_portal(self):
        self.farmer.is_active = False
        self.farmer.save(update_fields=["is_active", "updated_at"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("farmer_portal:home"))
        self.assertEqual(response.status_code, 403)

    def test_filtered_collection_totals_are_scoped_to_filters(self):
        self.create_collection(self.farmer, "MORNING-A", MilkCollection.Status.APPROVED)
        evening = self.create_collection(self.farmer, "EVENING-B", MilkCollection.Status.APPROVED)
        evening.shift = MilkCollection.Shift.EVENING
        evening.quantity_litres = Decimal("5.000")
        evening.total_amount = Decimal("362.50")
        evening.save(update_fields=["shift", "quantity_litres", "total_amount", "updated_at"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("farmer_portal:home"), {"shift": "morning"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["collection_count"], 1)
        self.assertEqual(response.context["total_litres"], Decimal("3.000"))
        # Lifetime production must not be reduced by the history filter.
        self.assertEqual(response.context["lifetime_summary"]["litres"], Decimal("8.000"))

    def test_csv_export_respects_filters_and_contains_column_headings(self):
        self.create_collection(self.farmer, "CSV-APPROVED", MilkCollection.Status.APPROVED)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("farmer_portal:home"), {"export": "1", "export_format": "csv"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("CSV-APPROVED", response.content.decode("utf-8-sig"))

    def test_pdf_export_returns_pdf_content(self):
        self.create_collection(self.farmer, "PDF-APPROVED", MilkCollection.Status.APPROVED)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("farmer_portal:home"), {"export": "1", "export_format": "pdf"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
