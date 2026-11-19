from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.finance.models import Expense
from apps.finance.services import approve_expense, record_expense
from apps.organizations.models import Branch, Membership, Organization

User = get_user_model()


class ExpenseWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="accountant", email="accountant@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.user, name="Expense Dairy", slug="expense-dairy"
        )
        self.branch = Branch.objects.create(
            organization=self.organization, code="MAIN", name="Main"
        )
        Membership.objects.create(
            user=self.user, organization=self.organization, role=Membership.Role.OWNER
        )

    def test_expense_requires_explicit_approval(self):
        expense = record_expense(
            organization=self.organization, branch=self.branch, actor=self.user,
            category="Utilities", description="Electricity",
            amount="1200.00", expense_date=date(2026, 11, 18),
            method="cash", supplier_name="Power company",
        )
        self.assertEqual(expense.status, Expense.Status.PENDING)
        self.assertIsNone(expense.approved_at)

        approved = approve_expense(
            expense_id=expense.pk, organization=self.organization, actor=self.user
        )
        self.assertEqual(approved.status, Expense.Status.APPROVED)
        self.assertEqual(approved.approved_by, self.user)
        self.assertIsNotNone(approved.approved_at)

    def test_record_expense_requires_active_branch_membership(self):
        outsider = User.objects.create_user(
            username="expense-outsider", email="expense-outsider@example.test",
            password="LongDemoPass!123",
        )
        with self.assertRaises(PermissionDenied):
            record_expense(
                organization=self.organization, branch=self.branch, actor=outsider,
                category="Utilities", description="Unauthorised",
                amount="10.00", expense_date=date(2026, 11, 18), method="cash",
            )
        self.assertEqual(Expense.objects.count(), 0)

    def test_negative_expense_is_rejected(self):
        with self.assertRaises(ValidationError):
            record_expense(
                organization=self.organization, branch=self.branch, actor=self.user,
                category="Utilities", description="Invalid",
                amount=Decimal("-1"), expense_date=date(2026, 11, 18), method="cash",
            )

    def test_expense_branch_must_belong_to_organisation(self):
        other = Organization.objects.create(
            owner=self.user, name="Other Expense Dairy", slug="other-expense-dairy"
        )
        other_branch = Branch.objects.create(
            organization=other, code="MAIN", name="Other main"
        )
        with self.assertRaises(ValidationError):
            record_expense(
                organization=self.organization, branch=other_branch, actor=self.user,
                category="Utilities", description="Cross tenant",
                amount="100", expense_date=date(2026, 11, 18), method="cash",
            )

    def test_accountant_cannot_approve_expense_in_unassigned_branch(self):
        from django.core.exceptions import PermissionDenied
        from apps.organizations.models import BranchAssignment

        second_branch = Branch.objects.create(
            organization=self.organization, code="SECOND", name="Second"
        )
        accountant = User.objects.create_user(
            username="branch-accountant", email="branch-accountant@example.test",
            password="LongDemoPass!123",
        )
        membership = Membership.objects.create(
            user=accountant, organization=self.organization,
            role=Membership.Role.ACCOUNTANT,
        )
        BranchAssignment.objects.create(membership=membership, branch=self.branch)
        expense = record_expense(
            organization=self.organization, branch=second_branch, actor=self.user,
            category="Utilities", description="Second branch electricity",
            amount="50.00", expense_date=date(2026, 11, 18), method="cash",
        )
        with self.assertRaises(PermissionDenied):
            approve_expense(
                expense_id=expense.pk, organization=self.organization, actor=accountant
            )
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PENDING)

    def test_record_expense_rejects_suspended_or_inaccessible_context(self):
        from django.utils import timezone
        from apps.organizations.models import Membership

        membership = Membership.objects.get(user=self.user, organization=self.organization)
        other_org = Organization.objects.create(
            owner=self.user, name="Unrelated Expense Dairy", slug="unrelated-expense-dairy"
        )
        outsider = User.objects.create_user(
            username="expense-other-tenant", email="expense-other-tenant@example.test",
            password="LongDemoPass!123",
        )
        Membership.objects.create(
            user=outsider, organization=other_org, role=Membership.Role.OWNER
        )

        for scenario in ("foreign_tenant_membership", "suspended_membership",
                         "suspended_organization", "inactive_branch", "soft_deleted_branch"):
            with self.subTest(scenario=scenario):
                self.organization.status = Organization.Status.ACTIVE
                self.organization.save(update_fields=["status", "updated_at"])
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
                    self.organization.status = Organization.Status.SUSPENDED
                    self.organization.save(update_fields=["status", "updated_at"])
                elif scenario == "inactive_branch":
                    self.branch.is_active = False
                    self.branch.save(update_fields=["is_active", "updated_at"])
                elif scenario == "soft_deleted_branch":
                    self.branch.deleted_at = timezone.now()
                    self.branch.save(update_fields=["deleted_at", "updated_at"])

                expected_error = ValidationError if scenario == "inactive_branch" else PermissionDenied
                with self.assertRaises(expected_error):
                    record_expense(
                        organization=self.organization, branch=self.branch, actor=actor,
                        category="Utilities", description="Denied write",
                        amount="10.00", expense_date=date(2026, 11, 18), method="cash",
                    )
                self.assertEqual(Expense.objects.count(), 0)

