import re

from django.test import Client, TestCase
from django.urls import reverse


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
