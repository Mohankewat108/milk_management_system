from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.finance.models import Expense
from apps.finance.services import approve_expense, record_expense
from apps.organizations.models import Branch, Organization

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
