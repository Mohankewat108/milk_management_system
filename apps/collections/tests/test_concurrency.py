from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase

from apps.collections.models import MilkCollection
from apps.collections.services import create_collection
from apps.organizations.models import Branch, Membership, Organization
from apps.parties.models import Farmer
from apps.pricing.models import PricingConfiguration

User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "Concurrency guarantees require PostgreSQL.")
class CollectionConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def setUp(self):
        self.user = User.objects.create_user(
            username="concurrent-collection",
            email="concurrent-collection@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.user, name="Concurrent Dairy", slug="concurrent-dairy"
        )
        self.branch = Branch.objects.create(
            organization=self.organization, code="MAIN", name="Main"
        )
        Membership.objects.create(
            user=self.user, organization=self.organization, role=Membership.Role.OWNER
        )
        self.farmer = Farmer.objects.create(
            organization=self.organization, branch=self.branch, code="F-1", full_name="Farmer"
        )
        PricingConfiguration.objects.create(
            organization=self.organization,
            version=1,
            snf_rate=Decimal("5.0000"),
            fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=date(2026, 1, 1),
            is_approved=True,
            created_by=self.user,
        )

    def test_simultaneous_collection_retries_create_one_record(self):
        barrier = Barrier(2)
        organization_id = self.organization.pk
        branch_id = self.branch.pk
        farmer_id = self.farmer.pk
        user_id = self.user.pk

        def submit():
            try:
                connections.close_all()
                organization = Organization.objects.get(pk=organization_id)
                branch = Branch.objects.get(pk=branch_id)
                farmer = Farmer.objects.get(pk=farmer_id)
                actor = User.objects.get(pk=user_id)
                barrier.wait(timeout=10)
                return create_collection(
                    organization=organization,
                    branch=branch,
                    actor=actor,
                    collected_at=datetime(2026, 11, 19, 6, tzinfo=UTC),
                    quantity_litres="2.500",
                    snf="8.0",
                    fat="4.0",
                    lactose="4.5",
                    farmer=farmer,
                    idempotency_key="simultaneous-collection",
                ).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: submit(), range(2)))

        self.assertEqual(results[0], results[1])
        self.assertEqual(MilkCollection.objects.count(), 1)
