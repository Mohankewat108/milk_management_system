from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.collections.models import MilkCollection
from apps.collections.services import create_collection
from apps.organizations.models import Branch, Organization
from apps.parties.models import Farmer
from apps.pricing.models import PricingConfiguration

User = get_user_model()


class CollectionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="operator", email="operator@example.test", password="LongDemoPass!123"
        )
        self.org = Organization.objects.create(
            owner=self.user, name="Dairy A", slug="dairy-a", is_demo=True
        )
        self.branch = Branch.objects.create(
            organization=self.org, code="MAIN", name="Main"
        )
        self.farmer = Farmer.objects.create(
            organization=self.org, branch=self.branch, code="F001", full_name="Test Farmer"
        )
        self.pricing = PricingConfiguration.objects.create(
            organization=self.org, version=1,
            snf_rate=Decimal("5.0000"), fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"), effective_from=datetime(2026, 1, 1).date(),
            is_approved=True, created_by=self.user,
        )

    def test_collection_uses_pricing_snapshot_and_decimal_total(self):
        entry = create_collection(
            organization=self.org, branch=self.branch, actor=self.user,
            collected_at=datetime(2026, 11, 18, 6, 0, tzinfo=dt_timezone.utc),
            quantity_litres="2.500", snf="8.0", fat="4.0", lactose="4.5",
            farmer=self.farmer,
        )
        self.assertEqual(entry.status, MilkCollection.Status.SUBMITTED)
        self.assertEqual(entry.milk_rate, Decimal("72.50"))
        self.assertEqual(entry.total_amount, Decimal("181.25"))
        self.assertEqual(entry.pricing_snapshot["version"], 1)

    def test_party_from_another_organisation_is_rejected(self):
        other = Organization.objects.create(
            owner=self.user, name="Dairy B", slug="dairy-b", is_demo=True
        )
        foreign_farmer = Farmer.objects.create(
            organization=other, code="F002", full_name="Foreign Farmer"
        )
        with self.assertRaises(ValidationError):
            create_collection(
                organization=self.org, branch=self.branch, actor=self.user,
                collected_at=datetime(2026, 11, 18, 6, 0, tzinfo=dt_timezone.utc),
                quantity_litres="1", snf="8", fat="4", lactose="4",
                farmer=foreign_farmer,
            )

    def test_lactometer_and_rate_components_are_saved_in_snapshot(self):
        entry = create_collection(
            organization=self.org, branch=self.branch, actor=self.user,
            collected_at=datetime(2026, 11, 18, 7, 0, tzinfo=dt_timezone.utc),
            quantity_litres="2.000", snf="8.0", fat="4.0", lactose="4.5",
            farmer=self.farmer, lactometer_reading="29.5",
            milk_temperature_c="5.50", sample_reference="SAMPLE-001",
            quality_test_method="Digital analyser",
        )
        self.assertEqual(entry.lactometer_reading, Decimal("29.500"))
        self.assertEqual(entry.milk_temperature_c, Decimal("5.50"))
        self.assertEqual(entry.tested_by, self.user)
        self.assertEqual(entry.pricing_snapshot["snf_component"], "40.00")
        self.assertEqual(entry.pricing_snapshot["fat_component"], "28.00")
        self.assertEqual(entry.pricing_snapshot["lactose_component"], "4.50")
        self.assertEqual(entry.pricing_snapshot["effective_from"], "2026-01-01")
