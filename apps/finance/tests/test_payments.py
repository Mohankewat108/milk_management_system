from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.finance.models import Payment
from apps.finance.services import record_payment
from apps.organizations.models import Branch, Membership, Organization
from apps.parties.models import Customer

User = get_user_model()


class PaymentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cashier", email="cashier@example.test", password="LongDemoPass!123"
        )
        self.org = Organization.objects.create(
            owner=self.user, name="Payments Dairy", slug="payments-dairy"
        )
        self.branch = Branch.objects.create(organization=self.org, code="MAIN", name="Main")
        Membership.objects.create(user=self.user, organization=self.org, role=Membership.Role.OWNER)
        self.customer = Customer.objects.create(
            organization=self.org, code="C001", full_name="Test Customer"
        )

    def test_record_payment_requires_active_branch_membership(self):
        outsider = User.objects.create_user(
            username="payment-outsider",
            email="payment-outsider@example.test",
            password="LongDemoPass!123",
        )
        with self.assertRaises(PermissionDenied):
            record_payment(
                organization=self.org,
                branch=self.branch,
                actor=outsider,
                direction=Payment.Direction.INCOMING,
                amount="10.00",
                method=Payment.Method.CASH,
                customer=self.customer,
            )
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_is_pending_until_explicitly_verified(self):
        payment = record_payment(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            direction=Payment.Direction.INCOMING,
            amount=Decimal("120.00"),
            method=Payment.Method.ONLINE,
            customer=self.customer,
        )
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertIsNone(payment.paid_at)

    def test_foreign_tenant_party_is_rejected(self):
        other = Organization.objects.create(
            owner=self.user, name="Other Dairy", slug="other-payments-dairy"
        )
        foreign_customer = Customer.objects.create(
            organization=other, code="C002", full_name="Foreign Customer"
        )
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            record_payment(
                organization=self.org,
                branch=self.branch,
                actor=self.user,
                direction=Payment.Direction.INCOMING,
                amount="10",
                method=Payment.Method.CASH,
                customer=foreign_customer,
            )

    def test_record_payment_rejects_suspended_or_inaccessible_context(self):
        from django.utils import timezone

        membership = Membership.objects.get(user=self.user, organization=self.org)
        other_org = Organization.objects.create(
            owner=self.user, name="Unrelated Payment Dairy", slug="unrelated-payment-dairy"
        )
        outsider = User.objects.create_user(
            username="payment-other-tenant",
            email="payment-other-tenant@example.test",
            password="LongDemoPass!123",
        )
        Membership.objects.create(user=outsider, organization=other_org, role=Membership.Role.OWNER)

        for scenario in (
            "foreign_tenant_membership",
            "suspended_membership",
            "suspended_organization",
            "inactive_branch",
            "soft_deleted_branch",
        ):
            with self.subTest(scenario=scenario):
                self.org.status = Organization.Status.ACTIVE
                self.org.save(update_fields=["status", "updated_at"])
                self.branch.is_active = True
                self.branch.deleted_at = None
                self.branch.save(update_fields=["is_active", "deleted_at", "updated_at"])
                membership.status = Membership.Status.ACTIVE
                membership.save(update_fields=["status", "updated_at"])
                actor = self.user

                if scenario == "foreign_tenant_membership":
                    actor = outsider
                elif scenario == "suspended_membership":
                    membership.status = Membership.Status.SUSPENDED
                    membership.save(update_fields=["status", "updated_at"])
                elif scenario == "suspended_organization":
                    self.org.status = Organization.Status.SUSPENDED
                    self.org.save(update_fields=["status", "updated_at"])
                elif scenario == "inactive_branch":
                    self.branch.is_active = False
                    self.branch.save(update_fields=["is_active", "updated_at"])
                elif scenario == "soft_deleted_branch":
                    self.branch.deleted_at = timezone.now()
                    self.branch.save(update_fields=["deleted_at", "updated_at"])

                expected_error = (
                    ValidationError if scenario == "inactive_branch" else PermissionDenied
                )
                with self.assertRaises(expected_error):
                    record_payment(
                        organization=self.org,
                        branch=self.branch,
                        actor=actor,
                        direction=Payment.Direction.INCOMING,
                        amount="10.00",
                        method=Payment.Method.CASH,
                        customer=self.customer,
                    )
                self.assertEqual(Payment.objects.count(), 0)


def test_record_payment_rejects_unassigned_branch(self):
    from apps.organizations.models import BranchAssignment

    other_branch = Branch.objects.create(organization=self.org, code="SECOND", name="Second")
    accountant = User.objects.create_user(
        username="payment-branch-accountant",
        email="payment-branch-accountant@example.test",
        password="LongDemoPass!123",
    )
    membership = Membership.objects.create(
        user=accountant,
        organization=self.org,
        role=Membership.Role.ACCOUNTANT,
    )
    BranchAssignment.objects.create(membership=membership, branch=self.branch)

    with self.assertRaises(PermissionDenied):
        record_payment(
            organization=self.org,
            branch=other_branch,
            actor=accountant,
            direction=Payment.Direction.INCOMING,
            amount="10.00",
            method=Payment.Method.CASH,
            customer=self.customer,
        )
    self.assertEqual(Payment.objects.count(), 0)
