from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.finance.models import Payment
from apps.finance.services import record_payment
from apps.organizations.models import Branch, Organization
from apps.parties.models import Customer

User = get_user_model()


class PaymentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cashier", email="cashier@example.test", password="LongDemoPass!123"
        )
        self.org = Organization.objects.create(owner=self.user, name="Payments Dairy", slug="payments-dairy")
        self.branch = Branch.objects.create(organization=self.org, code="MAIN", name="Main")
        self.customer = Customer.objects.create(
            organization=self.org, code="C001", full_name="Test Customer"
        )

    def test_payment_is_pending_until_explicitly_verified(self):
        payment = record_payment(
            organization=self.org, branch=self.branch, actor=self.user,
            direction=Payment.Direction.INCOMING, amount=Decimal("120.00"),
            method=Payment.Method.ONLINE, customer=self.customer,
        )
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertIsNone(payment.paid_at)

    def test_foreign_tenant_party_is_rejected(self):
        other = Organization.objects.create(owner=self.user, name="Other Dairy", slug="other-payments-dairy")
        foreign_customer = Customer.objects.create(
            organization=other, code="C002", full_name="Foreign Customer"
        )
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            record_payment(
                organization=self.org, branch=self.branch, actor=self.user,
                direction=Payment.Direction.INCOMING, amount="10",
                method=Payment.Method.CASH, customer=foreign_customer,
            )
