import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.collections.models import MilkCollection
from apps.collections.services import create_collection
from apps.finance.models import Payment
from apps.inventory.models import InventoryItem, StockMovement
from apps.organizations.models import Branch, BranchAssignment, Membership, Organization
from apps.parties.models import Customer, Farmer
from apps.platform_admin.models import Subscription, SubscriptionPlan
from apps.pricing.models import PricingConfiguration

User = get_user_model()


class Command(BaseCommand):
    help = "Create a reproducible 108-record DairyNexus demonstration dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear", action="store_true",
            help="Remove only previously seeded demo business records before reseeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            self.clear_demo_records()
        password = settings.DEMO_PASSWORD
        if not password:
            self.stdout.write(self.style.WARNING(
                "DJANGO_DEMO_PASSWORD is empty; demo users will have unusable passwords."
            ))
        self.get_user(
            "demo-platform-admin", "demo-platform@example.test", "Platform", "Admin",
            password, superuser=True,
        )
        plan, _ = SubscriptionPlan.objects.get_or_create(
            code="demo-standard",
            defaults={
                "name": "Demo Standard", "description": "Seeded demonstration plan",
                "monthly_price": Decimal("1200.00"), "annual_price": Decimal("12000.00"),
                "max_branches": 5, "max_staff": 25, "max_customers": 1000,
                "features": {"milk_collection": True, "reports": True},
            },
        )
        today = timezone.localdate()
        rng = random.Random(20261118)
        all_customers = []
        all_farmers = []
        org_branches = []

        for org_no in range(1, 4):
            owner = self.get_user(
                f"demo-owner-{org_no}", f"owner{org_no}@example.test",
                f"Demo", f"Owner {org_no}", password,
            )
            org, _ = Organization.objects.get_or_create(
                slug=f"demo-dairy-{org_no}",
                defaults={
                    "owner": owner, "name": f"Demo Dairy Cooperative {org_no}",
                    "legal_name": f"Demo Dairy Cooperative {org_no} Ltd",
                    "email": f"contact{org_no}@example.test", "phone": f"+977-98000000{org_no}",
                    "country": "Nepal", "currency": "NPR", "timezone": "Asia/Kathmandu",
                    "status": Organization.Status.ACTIVE, "is_demo": True,
                },
            )
            if not org.is_demo:
                raise CommandError(
                    f"Refusing to seed into {org.slug!r}: the slug already belongs to "
                    "an organisation not explicitly marked as demo data."
                )
            org.status = Organization.Status.ACTIVE
            org.save(update_fields=["status", "updated_at"])
            owner_membership, _ = Membership.objects.get_or_create(
                user=owner, organization=org,
                defaults={"role": Membership.Role.OWNER, "status": Membership.Status.ACTIVE,
                          "joined_at": timezone.now()},
            )
            first_branch, _ = Branch.objects.get_or_create(
                organization=org, code="MAIN",
                defaults={"name": "Main Collection Centre", "address": "Ward 4, Bharatpur"},
            )
            second_branch, _ = Branch.objects.get_or_create(
                organization=org, code="RURAL-02",
                defaults={"name": "Rural Collection Centre", "address": "Ward 7, Bharatpur"},
            )
            branches = [first_branch, second_branch]
            org_branches.append((org, branches))

            staff_roles = [
                Membership.Role.BRANCH_MANAGER,
                Membership.Role.COLLECTION_OPERATOR,
                Membership.Role.ACCOUNTANT,
            ]
            for staff_no, role in enumerate(staff_roles, start=1):
                staff = self.get_user(
                    f"demo-staff-{org_no}-{staff_no}",
                    f"staff{org_no}-{staff_no}@example.test",
                    "Demo", f"Staff {org_no}-{staff_no}", password,
                )
                membership, _ = Membership.objects.get_or_create(
                    user=staff, organization=org,
                    defaults={"role": role, "status": Membership.Status.ACTIVE,
                              "joined_at": timezone.now()},
                )
                assignment, _ = BranchAssignment.objects.get_or_create(
                    membership=membership, branch=branches[(staff_no - 1) % 2],
                )
                if role == Membership.Role.BRANCH_MANAGER:
                    branches[0].manager = staff
                    branches[0].save(update_fields=["manager", "updated_at"])

            farmers = []
            for i in range(1, 6):
                farmer, _ = Farmer.objects.get_or_create(
                    organization=org, code=f"F{org_no:02d}{i:03d}",
                    defaults={
                        "branch": branches[(i - 1) % 2],
                        "full_name": f"Demo Farmer {org_no}-{i}",
                        "phone": f"+977-981{org_no}{i:02d}0000",
                        "email": f"farmer{org_no}-{i}@example.test",
                        "address": f"Ward {i}, Bharatpur",
                    },
                )
                farmers.append(farmer)
                all_farmers.append(farmer)

            customers = []
            count = 7 if org_no < 3 else 6
            for i in range(1, count + 1):
                customer, _ = Customer.objects.get_or_create(
                    organization=org, code=f"C{org_no:02d}{i:03d}",
                    defaults={
                        "branch": branches[(i - 1) % 2],
                        "full_name": f"Demo Milk Customer {org_no}-{i}",
                        "phone": f"+977-982{org_no}{i:02d}0000",
                        "email": f"customer{org_no}-{i}@example.test",
                        "city": "Bharatpur", "village": "Demo Village", "ward": str(i),
                    },
                )
                customers.append(customer)
                all_customers.append(customer)
            if customers:
                portal_user = self.get_user(
                    f"demo-customer-{org_no}", f"portal{org_no}@example.test",
                    "Demo", f"Customer {org_no}", password,
                )
                if customers[0].user_id is None:
                    customers[0].user = portal_user
                    customers[0].save(update_fields=["user", "updated_at"])

            global_price, _ = PricingConfiguration.objects.get_or_create(
                organization=org, version=1,
                defaults={
                    "branch": None, "snf_rate": Decimal("5.2500"),
                    "fat_rate": Decimal("7.1000"), "lactose_rate": Decimal("1.2500"),
                    "effective_from": today - timedelta(days=365), "is_approved": True,
                    "created_by": owner,
                },
            )
            branch_price, _ = PricingConfiguration.objects.get_or_create(
                organization=org, version=2,
                defaults={
                    "branch": branches[1], "snf_rate": Decimal("5.4000"),
                    "fat_rate": Decimal("7.2500"), "lactose_rate": Decimal("1.3000"),
                    "effective_from": today - timedelta(days=90), "is_approved": True,
                    "created_by": owner,
                },
            )
            Subscription.objects.get_or_create(
                organization=org, plan=plan, starts_at=today,
                defaults={"status": Subscription.Status.TRIAL,
                          "ends_at": today + timedelta(days=30), "auto_renew": False},
            )

            created = MilkCollection.objects.filter(
                organization=org, reference__startswith=f"DEMO-{org_no}-"
            ).count()
            for i in range(created + 1, 11):
                branch = branches[(i - 1) % 2]
                farmer = farmers[(i - 1) % len(farmers)] if i % 2 else None
                customer = customers[(i - 1) % len(customers)] if i % 2 == 0 else None
                when = timezone.make_aware(
                    timezone.datetime.combine(
                        today - timedelta(days=(i - 1) * 2),
                        timezone.datetime.min.time().replace(hour=6 + i % 3),
                    )
                )
                # Use service validation and server-side price calculation.
                entry = create_collection(
                    organization=org, branch=branch, actor=owner, collected_at=when,
                    quantity_litres=Decimal(str(rng.randint(12, 40))),
                    snf=Decimal("8.50") + Decimal(str(i % 5)) / Decimal("10"),
                    fat=Decimal("3.80") + Decimal(str(i % 4)) / Decimal("10"),
                    lactose=Decimal("4.60") + Decimal(str(i % 3)) / Decimal("10"),
                    farmer=farmer, customer=customer,
                    notes=f"Seeded demonstration collection {org_no}-{i}",
                )
                entry.reference = f"DEMO-{org_no}-{i:03d}"
                entry.save(update_fields=["reference"])

            AuditEvent.objects.get_or_create(
                organization=org, actor=owner, action="demo.seeded",
                target_type="Organization", target_id=str(org.pk),
            )

        # Ten reproducible finance records across the three organisations.
        payment_no = 1
        for org, branches in org_branches:
            for local_no in range(1, 4):
                customer = Customer.objects.filter(organization=org).order_by("code")[(local_no - 1) % Customer.objects.filter(organization=org).count()]
                farmer = Farmer.objects.filter(organization=org).order_by("code")[(local_no - 1) % Farmer.objects.filter(organization=org).count()]
                for party_type, party in (("customer", customer), ("farmer", farmer)):
                    if payment_no > 10:
                        break
                    Payment.objects.get_or_create(
                        organization=org, reference=f"DEMO-PAY-{payment_no:03d}",
                        defaults={
                            "branch": branches[(payment_no - 1) % 2],
                            "direction": Payment.Direction.INCOMING if party_type == "customer" else Payment.Direction.OUTGOING,
                            "customer": party if party_type == "customer" else None,
                            "farmer": party if party_type == "farmer" else None,
                            "amount": Decimal("1500.00") + Decimal(payment_no * 125),
                            "currency": org.currency,
                            "method": Payment.Method.CASH if payment_no % 2 else Payment.Method.BANK,
                            "status": Payment.Status.COMPLETED if payment_no % 3 else Payment.Status.PENDING,
                            "paid_at": timezone.now() if payment_no % 3 else None,
                            "recorded_by": org.owner,
                            "notes": "Seeded demonstration payment",
                        },
                    )
                    payment_no += 1

        for item_no in range(1, 6):
            org, branches = org_branches[(item_no - 1) % len(org_branches)]
            InventoryItem.objects.get_or_create(
                organization=org, code=f"DEMO-ITEM-{item_no:02d}",
                defaults={
                    "branch": branches[(item_no - 1) % 2],
                    "name": ["Milk can", "Sanitiser", "Testing reagent", "Filter cloth", "Packaging roll"][item_no - 1],
                    "unit": "piece", "current_stock": Decimal("15.000"),
                    "reorder_level": Decimal("5.000"), "purchase_price": Decimal("250.00"),
                },
            )

        self.stdout.write(self.style.SUCCESS(
            "DairyNexus demo data is ready: 3 organisations, 6 branches, 12 business users "
            "(3 owners + 9 staff), 15 farmers, 20 customers, 30 collections, "
            "6 pricing versions, 10 payments and 5 inventory items (108 core records)."
        ))
        self.stdout.write("Demo account usernames use the demo-platform-admin, demo-owner-N, "
                          "demo-staff-N-M and demo-customer-N patterns.")
        self.stdout.write("Set DJANGO_DEMO_PASSWORD before seeding to enable demo logins.")

    def get_user(self, username, email, first_name, last_name, password, superuser=False):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email, "first_name": first_name, "last_name": last_name,
                "is_staff": superuser, "is_superuser": superuser, "is_active": True,
            },
        )
        if created:
            if password:
                user.set_password(password)
            else:
                user.set_unusable_password()
            user.save()
        elif superuser and (not user.is_staff or not user.is_superuser):
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser"])
        return user

    def clear_demo_records(self):
        organization_ids = list(Organization.objects.filter(is_demo=True).values_list("id", flat=True))
        if not organization_ids:
            self.stdout.write("No previously seeded demo organisations found.")
            return
        AuditEvent.objects.filter(organization_id__in=organization_ids).delete()
        StockMovement.objects.filter(organization_id__in=organization_ids).delete()
        Payment.objects.filter(organization_id__in=organization_ids).delete()
        MilkCollection.objects.filter(organization_id__in=organization_ids).delete()
        Subscription.objects.filter(organization_id__in=organization_ids).delete()
        PricingConfiguration.objects.filter(organization_id__in=organization_ids).delete()
        Farmer.objects.filter(organization_id__in=organization_ids).delete()
        Customer.objects.filter(organization_id__in=organization_ids).delete()
        InventoryItem.objects.filter(organization_id__in=organization_ids).delete()
        Membership.objects.filter(organization_id__in=organization_ids).delete()
        Branch.objects.filter(organization_id__in=organization_ids).delete()
        Organization.objects.filter(id__in=organization_ids).delete()
        self.stdout.write(self.style.WARNING(
            f"Cleared {len(organization_ids)} demo organisations and their demo business records only."
        ))
