from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Branch, Membership, Organisation


class AuthenticationTenantTests(TestCase):
    def setUp(self):
        self.org_a = Organisation.objects.create(name='Dairy A', slug='dairy-a', status='active')
        self.branch_a = Branch.objects.create(organisation=self.org_a, name='Main')
        self.org_b = Organisation.objects.create(name='Dairy B', slug='dairy-b', status='active')
        self.branch_b = Branch.objects.create(organisation=self.org_b, name='Main')
        User = get_user_model()
        self.user_a = User.objects.create_user(username='owner-a', password='strong-pass-123', email='a@example.com')
        self.user_b = User.objects.create_user(username='owner-b', password='strong-pass-123', email='b@example.com')
        Membership.objects.create(organisation=self.org_a, user=self.user_a, role=Membership.Role.DAIRY_OWNER)
        Membership.objects.create(organisation=self.org_b, user=self.user_b, role=Membership.Role.DAIRY_OWNER)

    def test_owner_login_and_dashboard(self):
        self.client.login(username='owner-a', password='strong-pass-123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dairy A')

    def test_customer_is_not_visible_to_other_organisation(self):
        from operations.models import Customer
        Customer.objects.create(organisation=self.org_a, branch=self.branch_a, name='A Customer', phone_number='111')
        Customer.objects.create(organisation=self.org_b, branch=self.branch_b, name='B Customer', phone_number='222')
        self.client.login(username='owner-a', password='strong-pass-123')
        response = self.client.get(reverse('customer_list'))
        self.assertContains(response, 'A Customer')
        self.assertNotContains(response, 'B Customer')

    def test_registration_creates_owner_membership_and_branch(self):
        response = self.client.post(reverse('register'), {
            'username': 'newowner',
            'email': 'newowner@example.com',
            'phone_number': '',
            'first_name': '',
            'last_name': '',
            'password1': 'strong-pass-123',
            'password2': 'strong-pass-123',
            'organisation_name': 'New Dairy',
            'organisation_slug': 'new-dairy',
        })
        self.assertEqual(response.status_code, 302)
        org = Organisation.objects.get(slug='new-dairy')
        self.assertTrue(Branch.objects.filter(organisation=org, name='Main Branch').exists())
        self.assertTrue(Membership.objects.filter(organisation=org, role=Membership.Role.DAIRY_OWNER).exists())
