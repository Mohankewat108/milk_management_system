from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.collections.services import create_collection
from apps.organizations.models import Branch, Organization
from apps.parties.models import Farmer
from apps.pricing.models import PricingConfiguration, QualityConfiguration

User = get_user_model()


class QualityProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="quality-user", email="quality@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.user, name="Quality Dairy", slug="quality-dairy"
        )
        self.branch = Branch.objects.create(
            organization=self.organization, code="MAIN", name="Main"
        )
        self.farmer = Farmer.objects.create(
            organization=self.organization, branch=self.branch,
            code="F001", full_name="Quality Farmer",
        )
        self.pricing = PricingConfiguration.objects.create(
            organization=self.organization, version=1,
            snf_rate=Decimal("5"), fat_rate=Decimal("7"), lactose_rate=Decimal("1"),
            effective_from=date(2026, 1, 1), is_approved=True, created_by=self.user,
        )

    def test_configured_quality_range_is_enforced(self):
        QualityConfiguration.objects.create(
            organization=self.organization, version=1,
            snf_min=Decimal("8.0"), snf_max=Decimal("9.0"),
            fat_min=Decimal("3.0"), fat_max=Decimal("5.0"),
            lactose_min=Decimal("4.0"), lactose_max=Decimal("5.0"),
            effective_from=date(2026, 1, 1), is_approved=True, created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            create_collection(
                organization=self.organization, branch=self.branch, actor=self.user,
                collected_at=datetime(2026, 11, 18, 6, tzinfo=dt_timezone.utc),
                quantity_litres="5", snf="9.5", fat="4.0", lactose="4.5",
                farmer=self.farmer,
            )

    def test_no_quality_profile_is_explicitly_snapshotted(self):
        entry = create_collection(
            organization=self.organization, branch=self.branch, actor=self.user,
            collected_at=datetime(2026, 11, 18, 6, tzinfo=dt_timezone.utc),
            quantity_litres="5", snf="8.5", fat="4.0", lactose="4.5",
            farmer=self.farmer,
        )
        self.assertEqual(
            entry.pricing_snapshot["quality_profile"],
            {"configured": False},
        )
