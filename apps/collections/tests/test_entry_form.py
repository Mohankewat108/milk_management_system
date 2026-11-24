from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.collections.forms import CollectionEntryForm
from apps.organizations.models import Branch, BranchAssignment, Membership, Organization
from apps.parties.models import Customer, Farmer

User = get_user_model()


class CollectionEntryFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="collection-form-owner",
            email="collection-form-owner@example.test",
            password="StrongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.user, name="Form Dairy", slug="form-dairy"
        )
        self.branch_a = Branch.objects.create(
            organization=self.organization, code="A", name="Branch A"
        )
        self.branch_b = Branch.objects.create(
            organization=self.organization, code="B", name="Branch B"
        )
        self.owner_membership = Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        self.farmer_a = Farmer.objects.create(
            organization=self.organization,
            branch=self.branch_a,
            code="FA",
            full_name="Farmer A",
        )
        self.customer_a = Customer.objects.create(
            organization=self.organization,
            branch=self.branch_a,
            code="CA",
            full_name="Customer A",
        )
        self.farmer_unassigned = Farmer.objects.create(
            organization=self.organization,
            branch=None,
            code="F0",
            full_name="Unassigned Farmer",
        )

    def test_owner_can_select_all_active_organisation_branches_and_parties(self):
        form = CollectionEntryForm(organization=self.organization, membership=self.owner_membership)
        self.assertQuerySetEqual(
            form.fields["branch"].queryset.order_by("name"),
            [self.branch_a, self.branch_b],
        )
        self.assertIn(self.farmer_a, form.fields["farmer"].queryset)
        self.assertIn(self.farmer_unassigned, form.fields["farmer"].queryset)
        self.assertIn(self.customer_a, form.fields["customer"].queryset)

    def test_branch_operator_only_sees_assigned_branch_parties(self):
        operator = User.objects.create_user(
            username="collection-form-operator",
            email="collection-form-operator@example.test",
            password="StrongDemoPass!123",
        )
        membership = Membership.objects.create(
            user=operator,
            organization=self.organization,
            role=Membership.Role.COLLECTION_OPERATOR,
        )
        BranchAssignment.objects.create(membership=membership, branch=self.branch_a)

        form = CollectionEntryForm(organization=self.organization, membership=membership)
        self.assertQuerySetEqual(form.fields["branch"].queryset, [self.branch_a])
        self.assertQuerySetEqual(form.fields["farmer"].queryset, [self.farmer_a])
        self.assertQuerySetEqual(form.fields["customer"].queryset, [self.customer_a])

    def test_form_rejects_party_associated_with_another_branch(self):
        form = CollectionEntryForm(
            data={
                "idempotency_key": "branch-mismatch-form-key",
                "branch": str(self.branch_b.pk),
                "party_type": "farmer",
                "farmer": str(self.farmer_a.pk),
                "customer": "",
                "collected_at": "2026-11-24T06:00",
                "quantity_litres": "2.000",
                "snf": "8.0",
                "fat": "4.0",
                "lactose": "4.5",
                "lactometer_reading": "",
                "milk_temperature_c": "",
                "sample_reference": "",
                "quality_test_method": "",
                "notes": "",
            },
            organization=self.organization,
            membership=self.owner_membership,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)
        self.assertIn("different branch", str(form.errors["__all__"]).lower())

    def test_form_accepts_matching_farmer_branch(self):
        form = CollectionEntryForm(
            data={
                "idempotency_key": "matching-branch-form-key",
                "branch": str(self.branch_a.pk),
                "party_type": "farmer",
                "farmer": str(self.farmer_a.pk),
                "customer": "",
                "collected_at": "2026-11-24T06:00",
                "quantity_litres": "2.000",
                "snf": "8.0",
                "fat": "4.0",
                "lactose": "4.5",
                "lactometer_reading": "",
                "milk_temperature_c": "",
                "sample_reference": "",
                "quality_test_method": "",
                "notes": "",
            },
            organization=self.organization,
            membership=self.owner_membership,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["farmer"], self.farmer_a)
        self.assertIsNone(form.cleaned_data["customer"])

    def test_form_accepts_customer_collection(self):
        form = CollectionEntryForm(
            data={
                "idempotency_key": "customer-form-key",
                "branch": str(self.branch_a.pk),
                "party_type": "customer",
                "farmer": "",
                "customer": str(self.customer_a.pk),
                "collected_at": "2026-11-24T06:00",
                "quantity_litres": "2.000",
                "snf": "8.0",
                "fat": "4.0",
                "lactose": "4.5",
                "lactometer_reading": "",
                "milk_temperature_c": "",
                "sample_reference": "",
                "quality_test_method": "",
                "notes": "",
            },
            organization=self.organization,
            membership=self.owner_membership,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["customer"], self.customer_a)
        self.assertIsNone(form.cleaned_data["farmer"])
