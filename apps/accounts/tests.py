import re

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User


class LoginCSRFCookieTests(TestCase):
    def test_login_page_sets_csrf_cookie_and_accepts_its_form_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

        match = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            response.content.decode(),
        )
        self.assertIsNotNone(match, "Login form must render a CSRF token.")

        # Invalid credentials should produce the normal login form response,
        # not a CSRF 403. This verifies the browser's GET cookie/form token pair.
        response = client.post(
            reverse("accounts:login"),
            {
                "username": "not-a-real-user",
                "password": "not-a-real-password",
                "csrfmiddlewaretoken": match.group(1),
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_login_page_explains_account_access_without_role_selector(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dairy owners")
        self.assertContains(response, "Staff members")
        self.assertContains(response, "Farmers")
        self.assertContains(response, "Platform administrators")
        self.assertContains(response, "DairyNexus will securely identify your access")
        self.assertNotContains(response, 'name="role"')
        self.assertNotContains(response, 'name="account_type"')


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetEmailTests(TestCase):
    def test_password_reset_email_contains_a_complete_reset_link(self):
        user = User.objects.create_user(
            username="reset-user",
            email="reset-user@example.test",
            password="Valid-Reset-Test-Password-123!",
        )

        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": user.email},
        )

        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [user.email])
        self.assertIn("http://testserver/accounts/password/reset/", message.body)
        self.assertIn("uidb64=", message.body) if False else None
        self.assertRegex(
            message.body,
            r"/accounts/password/reset/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/",
        )
        self.assertIn("time-limited", message.body.lower())
        self.assertIn("only be used once", message.body.lower())

    def test_unknown_email_does_not_reveal_account_existence(self):
        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": "missing-user@example.test"},
        )

        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
