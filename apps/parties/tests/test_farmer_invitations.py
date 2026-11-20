import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.organizations.models import Membership, Organization
from apps.parties.models import Farmer, FarmerInvitation

User = get_user_model()


class FarmerInvitationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="invitation-owner",
            email="invitation-owner@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.owner,
            name="Invitation Dairy",
            slug="invitation-dairy",
        )
        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        self.farmer = Farmer.objects.create(
            organization=self.organization,
            code="F-101",
            full_name="Invited Farmer",
            email="farmer@example.test",
            is_active=False,
        )
        self.client.force_login(self.owner)

    def _invitation_action_url(self, action):
        return reverse(
            f"parties:farmer_invitation_{action}",
            kwargs={
                "organization_slug": self.organization.slug,
                "farmer_id": self.farmer.pk,
            },
        )

    def _send_invitation(self):
        response = self.client.post(self._invitation_action_url("send"))
        self.assertEqual(response.status_code, 302)
        invitation = FarmerInvitation.objects.get(farmer=self.farmer)
        self.assertEqual(len(mail.outbox), 1)
        token = re.search(r"/farmer-invitations/[^/]+/([^/]+)/", mail.outbox[0].body)
        self.assertIsNotNone(token)
        return invitation, token.group(1)

    def test_send_invitation_stores_only_token_hash_and_audits_delivery(self):
        invitation, token = self._send_invitation()

        self.assertEqual(invitation.status, FarmerInvitation.Status.SENT)
        self.assertNotEqual(invitation.token_hash, token)
        self.assertEqual(len(invitation.token_hash), 64)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action="farmer.invitation.created",
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action="farmer.invitation.sent",
            ).exists()
        )

    def test_acceptance_activates_account_and_token_cannot_be_reused(self):
        invitation, token = self._send_invitation()
        invitation_url = reverse(
            "parties:farmer_invitation_accept",
            kwargs={"invitation_id": invitation.pk, "token": token},
        )

        response = self.client.get(invitation_url)
        self.assertEqual(response.status_code, 200)
        self.client.logout()
        response = self.client.post(
            invitation_url,
            {
                "new_password1": "FarmerPortal-Strong-2026",
                "new_password2": "FarmerPortal-Strong-2026",
            },
        )

        self.assertRedirects(response, reverse("farmer_portal:home"))
        self.farmer.refresh_from_db()
        invitation.refresh_from_db()
        farmer_user = User.objects.get(email="farmer@example.test")
        self.assertTrue(farmer_user.is_active)
        self.assertTrue(farmer_user.email_verified)
        self.assertEqual(self.farmer.user_id, farmer_user.pk)
        self.assertTrue(self.farmer.is_active)
        self.assertEqual(invitation.status, FarmerInvitation.Status.ACCEPTED)
        self.assertEqual(self.client.get(invitation_url).status_code, 410)

    def test_expired_invitation_is_marked_and_audited(self):
        invitation, token = self._send_invitation()
        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save(update_fields=["expires_at", "updated_at"])
        url = reverse(
            "parties:farmer_invitation_accept",
            kwargs={"invitation_id": invitation.pk, "token": token},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 410)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, FarmerInvitation.Status.EXPIRED)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action="farmer.invitation.expired",
            ).exists()
        )

    def test_revoked_invitation_cannot_be_accepted(self):
        invitation, token = self._send_invitation()
        response = self.client.post(self._invitation_action_url("revoke"))
        self.assertEqual(response.status_code, 302)
        url = reverse(
            "parties:farmer_invitation_accept",
            kwargs={"invitation_id": invitation.pk, "token": token},
        )

        self.assertEqual(self.client.get(url).status_code, 410)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, FarmerInvitation.Status.REVOKED)

    def test_invitation_email_failure_is_visible_and_audited(self):
        from unittest.mock import patch

        with patch("apps.parties.invitations.send_mail", side_effect=RuntimeError("mail down")):
            response = self.client.post(self._invitation_action_url("send"))

        self.assertEqual(response.status_code, 302)
        invitation = FarmerInvitation.objects.get(farmer=self.farmer)
        self.assertEqual(invitation.status, FarmerInvitation.Status.FAILED)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action="farmer.invitation.email_failed",
            ).exists()
        )

    def test_other_tenant_cannot_send_invitation(self):
        other_owner = User.objects.create_user(
            username="other-owner",
            email="other-owner@example.test",
            password="LongDemoPass!123",
        )
        Organization.objects.create(
            owner=other_owner,
            name="Other Dairy",
            slug="other-dairy",
        )
        self.client.force_login(other_owner)
        url = self._invitation_action_url("send")

        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertFalse(FarmerInvitation.objects.exists())
