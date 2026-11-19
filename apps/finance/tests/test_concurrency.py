from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from apps.finance.models import Payment
from apps.finance.services import record_payment
from apps.inventory.models import InventoryItem
from apps.inventory.services import move_stock
from apps.organizations.models import Branch, Membership, Organization
from apps.parties.models import Customer

User = get_user_model()


@skipUnless(
    connection.vendor == "postgresql",
    "Concurrency guarantees require PostgreSQL.",
)
class FinancialAndInventoryConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def setUp(self):
        self.user = User.objects.create_user(
            username="concurrent-finance",
            email="concurrent-finance@example.test",
            password="LongDemoPass!123",
        )

        self.organization = Organization.objects.create(
            owner=self.user,
            name="Concurrent Payments",
            slug="concurrent-payments",
        )

        self.branch = Branch.objects.create(
            organization=self.organization,
            code="MAIN",
            name="Main",
        )

        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )

        self.customer = Customer.objects.create(
            organization=self.organization,
            code="C-1",
            full_name="Customer",
        )

        self.item = InventoryItem.objects.create(
            organization=self.organization,
            branch=self.branch,
            code="I-1",
            name="Feed",
            current_stock=Decimal("0.000"),
        )

    def test_simultaneous_payment_retries_create_one_record(self):
        barrier = Barrier(2)

        organization_id = self.organization.pk
        branch_id = self.branch.pk
        customer_id = self.customer.pk
        user_id = self.user.pk

        def submit():
            close_old_connections()

            try:
                organization = Organization.objects.get(
                    pk=organization_id
                )
                branch = Branch.objects.get(pk=branch_id)
                customer = Customer.objects.get(pk=customer_id)
                actor = User.objects.get(pk=user_id)

                # Synchronize both worker threads before submitting.
                barrier.wait(timeout=10)

                payment = record_payment(
                    organization=organization,
                    branch=branch,
                    actor=actor,
                    direction=Payment.Direction.INCOMING,
                    amount="12.00",
                    method=Payment.Method.CASH,
                    customer=customer,
                    idempotency_key="simultaneous-payment",
                )

                return payment.pk

            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(lambda _: submit(), range(2))
            )

        # Both requests must return the same payment.
        self.assertEqual(results[0], results[1])

        # Only one payment should be created.
        self.assertEqual(Payment.objects.count(), 1)

    def test_simultaneous_inventory_movements_are_not_lost(self):
        barrier = Barrier(2)

        organization_id = self.organization.pk
        item_id = self.item.pk
        user_id = self.user.pk

        def submit():
            close_old_connections()

            try:
                organization = Organization.objects.get(
                    pk=organization_id
                )
                actor = User.objects.get(pk=user_id)

                # Synchronize both worker threads before stock movement.
                barrier.wait(timeout=10)

                movement = move_stock(
                    item_id=item_id,
                    organization=organization,
                    actor=actor,
                    kind="purchase",
                    quantity="1.000",
                    reason="Concurrent stock receipt",
                )

                return movement.pk

            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(lambda _: submit(), range(2))
            )

        self.item.refresh_from_db()

        # Both inventory movements must be recorded independently.
        self.assertEqual(len(set(results)), 2)

        # Neither concurrent stock update should be lost.
        self.assertEqual(
            self.item.current_stock,
            Decimal("2.000"),
        )
