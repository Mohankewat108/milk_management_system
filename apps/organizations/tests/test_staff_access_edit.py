from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.organizations.models import Branch, BranchAssignment, Membership, Organization

User = get_user_model()


class StaffAccessEditTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="access-owner",
            email="access-owner@example.test",
            password="LongDemoPass!123",
        )
        self.staff = User.objects.create_user(
            username="access-staff",
            email="access-staff@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.owner, name="Access Dairy", slug="access-dairy"
        )
        Membership.objects.create(
            user=self.owner, organization=self.organization, role=Membership.Role.OWNER
        )
        self.membership = Membership.objects.create(
            user=self.staff,
            organization=self.organization,
            role=Membership.Role.COLLECTION_OPERATOR,
        )
        self.branch_a = Branch.objects.create(
            organization=self.organization, code="A", name="Branch A"
        )
        self.branch_b = Branch.objects.create(
            organization=self.organization, code="B", name="Branch B"
        )
        BranchAssignment.objects.create(membership=self.membership, branch=self.branch_a)

    def test_owner_can_change_staff_role_and_branch_assignments(self):
        self.client.force_login(self.owner)
        url = reverse(
            "business:staff_edit",
            kwargs={
                "organization_slug": self.organization.slug,
                "membership_id": self.membership.pk,
            },
        )
        response = self.client.post(
            url,
            {
                "role": Membership.Role.QUALITY_OFFICER,
                "branches": [str(self.branch_b.pk)],
            },
        )
        self.assertRedirects(
            response,
            reverse("business:staff", kwargs={"organization_slug": self.organization.slug}),
        )
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.role, Membership.Role.QUALITY_OFFICER)
        self.assertEqual(
            list(self.membership.branch_assignments.values_list("branch_id", flat=True)),
            [self.branch_b.pk],
        )

    def test_staff_cannot_change_own_or_other_staff_permissions(self):
        self.client.force_login(self.staff)
        url = reverse(
            "business:staff_edit",
            kwargs={
                "organization_slug": self.organization.slug,
                "membership_id": self.membership.pk,
            },
        )
        response = self.client.post(
            url,
            {
                "role": Membership.Role.ADMIN,
                "branches": [str(self.branch_b.pk)],
            },
        )
        self.assertEqual(response.status_code, 404)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.role, Membership.Role.COLLECTION_OPERATOR)
        self.assertTrue(
            self.membership.branch_assignments.filter(branch=self.branch_a).exists()
        )

    def test_staff_access_form_rejects_branch_from_another_organisation(self):
        other = Organization.objects.create(
            owner=self.owner, name="Other Access Dairy", slug="other-access-dairy"
        )
        foreign_branch = Branch.objects.create(
            organization=other, code="X", name="Foreign Branch"
        )
        self.client.force_login(self.owner)
        url = reverse(
            "business:staff_edit",
            kwargs={
                "organization_slug": self.organization.slug,
                "membership_id": self.membership.pk,
            },
        )
        response = self.client.post(
            url,
            {
                "role": Membership.Role.ACCOUNTANT,
                "branches": [str(foreign_branch.pk)],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.role, Membership.Role.COLLECTION_OPERATOR)
