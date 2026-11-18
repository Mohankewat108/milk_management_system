from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from organizations.models import Branch, Membership, Organisation
from operations.models import Customer, MilkCollection, PricingConfiguration


class Command(BaseCommand):
    help = 'Create a reproducible local DairyNexus demonstration workspace.'

    def handle(self, *args, **options):
        User = get_user_model()
        owner, created = User.objects.get_or_create(
            username='demo-owner',
            defaults={
                'email': 'demo-owner@example.com',
                'is_active': True,
            },
        )
        if created:
            owner.set_password('DemoPass123!')
            owner.save()

        org, _ = Organisation.objects.get_or_create(
            slug='demo-dairy',
            defaults={
                'name': 'Demo Dairy Cooperative',
                'status': 'active',
            },
        )
        Membership.objects.get_or_create(
            organisation=org,
            user=owner,
            defaults={'role': Membership.Role.DAIRY_OWNER},
        )
        branch, _ = Branch.objects.get_or_create(
            organisation=org,
            name='Main Branch',
        )
        PricingConfiguration.objects.get_or_create(
            organisation=org,
            branch=branch,
            effective_from=timezone.localdate() - timedelta(days=365),
            defaults={
                'snf_rate': Decimal('2.5000'),
                'fat_rate': Decimal('3.2500'),
                'lacto_rate': Decimal('1.2500'),
            },
        )

        customers = []
        for index in range(1, 41):
            customer, _ = Customer.objects.get_or_create(
                organisation=org,
                phone_number=f'DEMO-{index:03d}',
                defaults={
                    'branch': branch,
                    'name': f'Demo Customer {index:03d}',
                    'email': f'customer{index:03d}@example.com',
                    'city': 'Demo City',
                    'village': f'Demo Village {((index - 1) % 8) + 1}',
                },
            )
            customers.append(customer)

        pricing = PricingConfiguration.objects.filter(organisation=org, branch=branch).earliest('effective_from')
        today = timezone.localdate()
        created_count = 0
        for index in range(120):
            customer = customers[index % len(customers)]
            milk_liters = Decimal('8') + Decimal(index % 17) / Decimal('2')
            snf = Decimal('8') + Decimal(index % 5) / Decimal('10')
            fat = Decimal('3') + Decimal(index % 7) / Decimal('10')
            lacto = Decimal('4') + Decimal(index % 4) / Decimal('10')
            rate = snf * pricing.snf_rate + fat * pricing.fat_rate + lacto * pricing.lacto_rate
            collection_date = today - timedelta(days=index % 30)
            collection, was_created = MilkCollection.objects.get_or_create(
                organisation=org,
                branch=branch,
                customer=customer,
                recorded_by=owner,
                collection_date=collection_date,
                defaults={
                    'milk_liters': milk_liters,
                    'snf': snf,
                    'fat': fat,
                    'lacto': lacto,
                    'milk_rate': rate,
                    'total_amount': (milk_liters * rate).quantize(Decimal('0.01')),
                },
            )
            created_count += int(was_created)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded demo dairy with {len(customers)} customers and {created_count} collections '
            '(login: demo-owner / DemoPass123!).'
        ))
