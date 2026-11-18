from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.organizations.models import Branch, Organization
from apps.pricing.models import PricingConfiguration
from apps.pricing.services import pricing_for_collection

User = get_user_model()


class OrganizationWideRateTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="rate-owner", email="owner@dairy.test", password="A-strong-test-password-123"
        )
        self.organization = Organization.objects.create(
            owner=self.owner, name="Common Dairy", slug="common-dairy", is_demo=True
        )
        self.branch_a = Branch.objects.create(organization=self.organization, code="A", name="Branch A")
        self.branch_b = Branch.objects.create(organization=self.organization, code="B", name="Branch B")
        self.common = PricingConfiguration.objects.create(
            organization=self.organization, version=1,
            snf_rate=Decimal("5.00"), fat_rate=Decimal("7.00"), lactose_rate=Decimal("1.00"),
            effective_from=date(2026, 1, 1), effective_to=date(2026, 1, 31),
            is_approved=True, created_by=self.owner, approved_by=self.owner,
        )

    def test_same_common_rate_is_used_for_every_branch(self):
        self.assertEqual(
            pricing_for_collection(organization=self.organization, branch=self.branch_a, collection_date=date(2026, 1, 15)),
            self.common,
        )
        self.assertEqual(
            pricing_for_collection(organization=self.organization, branch=self.branch_b, collection_date=date(2026, 1, 15)),
            self.common,
        )

    def test_new_dated_rate_applies_only_on_its_effective_dates(self):
        next_rate = PricingConfiguration.objects.create(
            organization=self.organization, version=2,
            snf_rate=Decimal("6.00"), fat_rate=Decimal("8.00"), lactose_rate=Decimal("1.50"),
            effective_from=date(2026, 2, 1), effective_to=date(2026, 2, 28),
            is_approved=True, created_by=self.owner, approved_by=self.owner,
        )
        self.assertEqual(
            pricing_for_collection(organization=self.organization, branch=self.branch_a, collection_date=date(2026, 1, 31)),
            self.common,
        )
        self.assertEqual(
            pricing_for_collection(organization=self.organization, branch=self.branch_b, collection_date=date(2026, 2, 1)),
            next_rate,
        )

    def test_branch_override_does_not_change_other_branch_common_rate(self):
        override = PricingConfiguration.objects.create(
            organization=self.organization, branch=self.branch_a, version=3,
            snf_rate=Decimal("9.00"), fat_rate=Decimal("9.00"), lactose_rate=Decimal("2.00"),
            effective_from=date(2026, 1, 10), effective_to=date(2026, 1, 20),
            is_approved=True, created_by=self.owner, approved_by=self.owner,
        )
        self.assertEqual(
            pricing_for_collection(organization=self.organization, branch=self.branch_a, collection_date=date(2026, 1, 15)),
            override,
        )
        self.assertEqual(
            pricing_for_collection(organization=self.organization, branch=self.branch_b, collection_date=date(2026, 1, 15)),
            self.common,
        )

    def test_unapproved_common_rate_is_not_used(self):
        pending = PricingConfiguration.objects.create(
            organization=self.organization, version=2,
            snf_rate=Decimal("6.00"), fat_rate=Decimal("8.00"), lactose_rate=Decimal("1.50"),
            effective_from=date(2026, 2, 1), is_approved=False, created_by=self.owner,
        )
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            pricing_for_collection(organization=self.organization, branch=self.branch_a, collection_date=date(2026, 2, 2))

    def test_rate_values_are_decimal_and_zero_is_valid(self):
        pricing = SimpleNamespace(
            snf_rate=Decimal("0.0000"),
            fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("0.0000"),
        )
        result = calculate_milk_rate(snf="8.5", fat="4", lactose="4.5", pricing=pricing)
        self.assertEqual(result, Decimal("28.00"))
