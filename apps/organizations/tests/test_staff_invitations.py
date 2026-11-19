import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import Membership, Organization, StaffInvitation

User = get_user_model()


class StaffInvitationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="invitation-owner",
            email="owner@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.owner, name="Invitation Dairy", slug="invitation-dairy"
        )
        Membership.objects.create(
            user=self.owner, organization=self.organization, role=Membership.Role.OWNER
        )

    def create_invitation(self, email):
        token = secrets.token_urlsafe(32)
        invitation = StaffInvitation.objects.create(
            organization=self.organization,
            invited_by=self.owner,
            email=email,
            role=Membership.Role.ACCOUNTANT,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        return invitation, token

    def invitation_url(self, invitation, token):
        return reverse(
            "accounts:staff_invitation_accept",
            kwargs={"invitation_id": invitation.pk, "token": token},
        )

    def test_existing_inactive_user_cannot_be_reactivated_by_invitation(self):
        existing_password = "ExistingPassword!123"
        user = User.objects.create_user(
            username="inactive-staff",
            email="inactive-staff@example.test",
            password=existing_password,
            is_active=False,
        )
        other_organization = Organization.objects.create(
            owner=self.owner, name="Other Dairy", slug="other-dairy"
        )
        existing_membership = Membership.objects.create(
            user=user, organization=other_organization, role=Membership.Role.ACCOUNTANT
        )
        invitation, token = self.create_invitation(user.email)

        response = self.client.post(
            self.invitation_url(invitation, token),
            {"new_password1": "AnotherLongPass!123", "new_password2": "AnotherLongPass!123"},
        )

        user.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password(existing_password))
        self.assertTrue(Membership.objects.filter(pk=existing_membership.pk).exists())
        self.assertFalse(
            Membership.objects.filter(organization=self.organization, user=user).exists()
        )
        self.assertIsNone(invitation.accepted_at)

    def test_invitation_cannot_reactivate_an_inactive_superuser(self):
        user = User.objects.create_superuser(
            username="inactive-superuser",
            email="inactive-superuser@example.test",
            password="LongDemoPass!123",
        )
        User.objects.filter(pk=user.pk).update(is_active=False)
        invitation, token = self.create_invitation(user.email)

        response = self.client.get(self.invitation_url(invitation, token))

        user.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertTrue(user.is_superuser)
        self.assertFalse(user.is_active)
        self.assertFalse(
            Membership.objects.filter(organization=self.organization, user=user).exists()
        )

    def test_new_user_can_accept_invitation_and_receive_membership(self):
        email = "new-staff@example.test"
        invitation, token = self.create_invitation(email)
        url = self.invitation_url(invitation, token)

        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 200)
        self.assertFalse(User.objects.filter(email=email).exists())

        response = self.client.post(
            url,
            {"new_password1": "AnotherLongPass!123", "new_password2": "AnotherLongPass!123"},
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email=email)
        self.assertTrue(user.is_active)
        self.assertTrue(user.email_verified)
        self.assertTrue(
            Membership.objects.filter(
                user=user,
                organization=self.organization,
                role=Membership.Role.ACCOUNTANT,
                status=Membership.Status.ACTIVE,
            ).exists()
        )
