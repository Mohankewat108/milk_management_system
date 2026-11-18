import re
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.organizations.models import Branch, Membership, Organization
from apps.parties.models import Customer
from apps.platform_admin.models import FarmOwnerInvitation


User = get_user_model()


class PlatformMultiFarmTests(TestCase):
    def setUp(self):
        self.platform_owner = User.objects.create_superuser(
            username="platform-root",
            email="platform@example.test",
            password="VeryStrongPlatformPass!2026",
        )
        self.farm_owner = User.objects.create_user(
            username="farm-owner",
            email="farm.owner@example.test",
            password="VeryStrongFarmPass!2026",
        )

    def farm_form_data(self, farm_name, email=None):
        return {
            "owner_first_name": "Farm",
            "owner_last_name": "Owner",
            "owner_email": email or self.farm_owner.email,
            "name": farm_name,
            "legal_name": "",
            "registration_number": "",
            "business_type": "Dairy farm",
            "email": "",
            "phone": "",
            "country": "Nepal",
            "currency": "NPR",
            "timezone": "Asia/Kathmandu",
            "address": "Parasi, Nepal",
        }

    def test_platform_owner_can_invite_same_existing_user_to_multiple_farms(self):
        self.client.force_login(self.platform_owner)
        url = reverse("platform:organization_create")
        for farm_name in ("Himalayan Dairy", "Green Valley Milk"):
            response = self.client.post(url, self.farm_form_data(farm_name))
            self.assertRedirects(response, reverse("platform:dashboard"))

        farms = Organization.objects.filter(owner=self.farm_owner)
        self.assertEqual(farms.count(), 2)
        self.assertEqual(
            Membership.objects.filter(
                user=self.farm_owner,
                organization__in=farms,
                role=Membership.Role.OWNER,
                status=Membership.Status.INVITED,
            ).count(),
            2,
        )
        self.assertEqual(Branch.objects.filter(organization__in=farms, code="MAIN").count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_new_owner_accepts_invitation_and_sets_first_password(self):
        self.client.force_login(self.platform_owner)
        response = self.client.post(
            reverse("platform:organization_create"),
            self.farm_form_data("New Owner Dairy", "new.owner@example.test"),
        )
        self.assertRedirects(response, reverse("platform:dashboard"))

        user = User.objects.get(email="new.owner@example.test")
        organization = Organization.objects.get(name="New Owner Dairy")
        membership = Membership.objects.get(user=user, organization=organization)
        invitation = FarmOwnerInvitation.objects.get(user=user, organization=organization)
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(membership.status, Membership.Status.INVITED)
        self.assertEqual(len(mail.outbox), 1)

        invitation_path = urlparse(re.search(r"http://testserver(\S+)", mail.outbox[0].body).group(0)).path
        response = self.client.get(invitation_path)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(invitation_path, {
            "new_password1": "A-Strong-Owner-Password-2026!",
            "new_password2": "A-Strong-Owner-Password-2026!",
        })
        self.assertRedirects(response, reverse("business:workspace"))

        user.refresh_from_db()
        membership.refresh_from_db()
        invitation.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.email_verified)
        self.assertTrue(user.has_usable_password())
        self.assertEqual(membership.status, Membership.Status.ACTIVE)
        self.assertIsNotNone(invitation.accepted_at)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

        replay = self.client.get(invitation_path)
        self.assertEqual(replay.status_code, 410)

    def test_active_existing_owner_must_sign_in_before_accepting(self):
        self.client.force_login(self.platform_owner)
        self.client.post(
            reverse("platform:organization_create"),
            self.farm_form_data("Existing Owner Dairy"),
        )
        invitation = FarmOwnerInvitation.objects.get(organization__name="Existing Owner Dairy")
        body = mail.outbox[0].body
        invitation_path = urlparse(re.search(r"http://testserver(\S+)", body).group(0)).path

        self.client.logout()
        response = self.client.get(invitation_path)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

        self.client.force_login(self.farm_owner)
        response = self.client.get(invitation_path)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(invitation_path)
        self.assertRedirects(response, reverse("business:workspace"))
        self.assertEqual(
            Membership.objects.get(
                user=self.farm_owner, organization=invitation.organization
            ).status,
            Membership.Status.ACTIVE,
        )

    def test_other_logged_in_user_cannot_accept_invitation(self):
        self.client.force_login(self.platform_owner)
        self.client.post(
            reverse("platform:organization_create"),
            self.farm_form_data("Private Invite Dairy", "new.invitee@example.test"),
        )
        invitation = FarmOwnerInvitation.objects.get(organization__name="Private Invite Dairy")
        body = mail.outbox[0].body
        invitation_path = urlparse(re.search(r"http://testserver(\S+)", body).group(0)).path
        self.client.force_login(self.farm_owner)
        response = self.client.get(invitation_path)
        self.assertEqual(response.status_code, 403)

    def test_non_platform_user_cannot_create_farms_from_platform(self):
        self.client.force_login(self.farm_owner)
        response = self.client.get(reverse("platform:organization_create"))
        self.assertEqual(response.status_code, 302)

    def test_customers_are_separate_records_per_farm(self):
        first = Organization.objects.create(
            owner=self.farm_owner, name="First Dairy", slug="first-dairy"
        )
        second = Organization.objects.create(
            owner=self.farm_owner, name="Second Dairy", slug="second-dairy"
        )
        Customer.objects.create(organization=first, code="C001", full_name="Customer One")
        Customer.objects.create(organization=first, code="C002", full_name="Customer Two")
        Customer.objects.create(organization=second, code="C001", full_name="Customer Three")
        self.assertEqual(first.customers.count(), 2)
        self.assertEqual(second.customers.count(), 1)
        self.assertNotEqual(first.pk, second.pk)

    def test_platform_owner_can_suspend_farm_with_reason_and_audit(self):
        organization = Organization.objects.create(
            owner=self.farm_owner, name="Audit Dairy", slug="audit-dairy"
        )
        self.client.force_login(self.platform_owner)
        response = self.client.post(
            reverse("platform:organization_set_status", kwargs={"organization_id": organization.pk}),
            {"status": Organization.Status.SUSPENDED, "reason": "Outstanding subscription invoice"},
        )
        self.assertRedirects(response, reverse("platform:dashboard"))
        organization.refresh_from_db()
        self.assertEqual(organization.status, Organization.Status.SUSPENDED)
        from apps.audit.models import AuditEvent
        self.assertTrue(AuditEvent.objects.filter(
            organization=organization,
            action="platform.organization.status_changed",
        ).exists())

    def test_platform_owner_status_change_requires_a_reason(self):
        organization = Organization.objects.create(
            owner=self.farm_owner, name="Reason Dairy", slug="reason-dairy"
        )
        self.client.force_login(self.platform_owner)
        self.client.post(
            reverse("platform:organization_set_status", kwargs={"organization_id": organization.pk}),
            {"status": Organization.Status.SUSPENDED, "reason": ""},
        )
        organization.refresh_from_db()
        self.assertEqual(organization.status, Organization.Status.TRIAL)


    def test_expired_invitation_cannot_be_accepted(self):
        from datetime import timedelta
        from django.utils import timezone

        self.client.force_login(self.platform_owner)
        self.client.post(
            reverse("platform:organization_create"),
            self.farm_form_data("Expired Invite Dairy", "expired.owner@example.test"),
        )
        invitation = FarmOwnerInvitation.objects.get(organization__name="Expired Invite Dairy")
        body = mail.outbox[0].body
        invitation_path = urlparse(re.search(r"http://testserver(\\S+)", body).group(0)).path
        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save(update_fields=["expires_at", "updated_at"])
        response = self.client.get(invitation_path)
        self.assertEqual(response.status_code, 410)

    def test_invitation_token_is_stored_as_a_hash_not_plaintext(self):
        import re
        from urllib.parse import urlparse

        self.client.force_login(self.platform_owner)
        self.client.post(
            reverse("platform:organization_create"),
            self.farm_form_data("Hashed Token Dairy", "hashed.owner@example.test"),
        )
        invitation = FarmOwnerInvitation.objects.get(organization__name="Hashed Token Dairy")
        invitation_path = urlparse(re.search(r"http://testserver(\\S+)", mail.outbox[0].body).group(0)).path
        raw_token = invitation_path.rstrip("/").split("/")[-1]
        self.assertNotEqual(invitation.token_hash, raw_token)
        self.assertEqual(len(invitation.token_hash), 64)
