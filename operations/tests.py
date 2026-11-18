from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Branch, Membership, Organisation
from .models import Customer, MilkCollection, PricingConfiguration


class MilkCollectionWorkflowTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name='Test Dairy', slug='test-dairy', status='active')
        self.branch = Branch.objects.create(organisation=self.org, name='Main')
        self.user = get_user_model().objects.create_user(
            username='owner',
            password='strong-pass-123',
            email='owner@example.com',
        )
        Membership.objects.create(
            organisation=self.org,
            user=self.user,
            role=Membership.Role.DAIRY_OWNER,
        )
        self.customer = Customer.objects.create(
            organisation=self.org,
            branch=self.branch,
            name='Test Customer',
            phone_number='12345',
        )
        PricingConfiguration.objects.create(
            organisation=self.org,
            branch=self.branch,
            snf_rate=Decimal('2.0000'),
            fat_rate=Decimal('3.0000'),
            lacto_rate=Decimal('1.0000'),
            effective_from=date(2026, 1, 1),
        )
        self.client.login(username='owner', password='strong-pass-123')

    def test_collection_calculates_decimal_amount(self):
        response = self.client.post(reverse('collection_create'), {
            'branch': str(self.branch.id),
            'customer': str(self.customer.id),
            'milk_liters': '10.500',
            'snf': '8',
            'fat': '4',
            'lacto': '5',
            'collection_date': '2026-01-15',
        })
        self.assertEqual(response.status_code, 302)
        collection = MilkCollection.objects.get(customer=self.customer)
        self.assertEqual(collection.milk_rate, Decimal('33.0000'))
        self.assertEqual(collection.total_amount, Decimal('346.50'))

    def test_customer_portal_only_shows_linked_customer(self):
        User = get_user_model()
        customer_user = User.objects.create_user(
            username='customer-user',
            password='strong-pass-123',
            email='customer-user@example.com',
        )
        self.customer.user = customer_user
        self.customer.save(update_fields=['user'])
        self.client.login(username='customer-user', password='strong-pass-123')
        response = self.client.get(reverse('customer_portal'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Customer')

    def test_collection_csv_excludes_other_organisation(self):
        other_org = Organisation.objects.create(name='Other Dairy', slug='other-dairy', status='active')
        other_branch = Branch.objects.create(organisation=other_org, name='Other Branch')
        other_customer = Customer.objects.create(
            organisation=other_org,
            branch=other_branch,
            name='Confidential Other Customer',
            phone_number='999',
        )
        MilkCollection.objects.create(
            organisation=other_org,
            branch=other_branch,
            customer=other_customer,
            recorded_by=self.user,
            milk_liters=Decimal('5'),
            snf=Decimal('8'),
            fat=Decimal('4'),
            lacto=Decimal('5'),
            milk_rate=Decimal('33'),
            total_amount=Decimal('165'),
            collection_date=date(2026, 1, 15),
        )
        self.client.login(username='owner', password='strong-pass-123')
        response = self.client.get(reverse('collections_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Confidential Other Customer')
