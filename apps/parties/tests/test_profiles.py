from datetime import UTC, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.collections.models import MilkCollection
from apps.finance.models import Payment
from apps.organizations.models import Branch, BranchAssignment, Membership, Organization
from apps.parties.models import Customer, Farmer
from apps.pricing.models import PricingConfiguration

User = get_user_model()


class PartyProfileTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="profile-owner",
            email="profile-owner@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.owner,
            name="Profile Dairy",
            slug="profile-dairy",
            is_demo=True,
        )
        self.branch = Branch.objects.create(
            organization=self.organization,
            code="MAIN",
            name="Main Branch",
        )
        self.membership = Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            branch=self.branch,
            code="C001",
            full_name="Test Customer",
            phone="9800000000",
        )
        self.farmer = Farmer.objects.create(
            organization=self.organization,
            branch=self.branch,
            code="F001",
            full_name="Test Farmer",
        )
        self.pricing = PricingConfiguration.objects.create(
            organization=self.organization,
            version=1,
            snf_rate=Decimal("5.0000"),
            fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=datetime(2026, 1, 1).date(),
            is_approved=True,
            created_by=self.owner,
        )

    def _collection(self, party, status, reference, day):
        kwargs = {"customer": party} if isinstance(party, Customer) else {"farmer": party}
        return MilkCollection.objects.create(
            organization=self.organization,
            branch=self.branch,
            reference=reference,
            recorded_by=self.owner,
            collected_at=datetime(2026, 11, day, 6, 0, tzinfo=UTC),
            quantity_litres=Decimal("2.500"),
            snf=Decimal("8.000"),
            fat=Decimal("4.000"),
            lactose=Decimal("4.500"),
            milk_rate=Decimal("72.50"),
            total_amount=Decimal("181.25"),
            pricing=self.pricing,
            pricing_snapshot={"version": 1},
            status=status,
            **kwargs,
        )

    def test_customer_profile_sums_only_approved_collections(self):
        self._collection(self.customer, MilkCollection.Status.APPROVED, "C-APP", 18)
        self._collection(self.customer, MilkCollection.Status.SUBMITTED, "C-SUB", 17)
        self._collection(self.customer, MilkCollection.Status.REVERSED, "C-REV", 16)
        self.client.force_login(self.owner)
        url = reverse("parties:customer_detail", args=[self.organization.slug, self.customer.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["metrics"]["lifetime_litres"], Decimal("2.500"))
        self.assertEqual(response.context["metrics"]["lifetime_value"], Decimal("181.25"))
        self.assertEqual(response.context["status_summary"]["submitted"], 1)
        self.assertEqual(response.context["status_summary"]["reversed"], 1)

    def test_farmer_profile_is_separate_and_scoped(self):
        self._collection(self.farmer, MilkCollection.Status.APPROVED, "F-APP", 18)
        self.client.force_login(self.owner)
        url = reverse("parties:farmer_detail", args=[self.organization.slug, self.farmer.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["kind"], "farmer")
        self.assertEqual(response.context["metrics"]["lifetime_litres"], Decimal("2.500"))

    def test_profile_today_and_month_use_organization_timezone(self):
        # The fixture follows the active test clock, then checks the local-day
        # boundary using an instant shortly after midnight in Kathmandu.
        self.organization.timezone = "Asia/Kathmandu"
        self.organization.save(update_fields=["timezone", "updated_at"])
        collection = self._collection(
            self.farmer, MilkCollection.Status.APPROVED, "F-TZ", timezone.localdate().day
        )
        local_today = timezone.now().astimezone(timezone.get_fixed_timezone(345))
        local_collection_time = local_today.replace(hour=0, minute=30, second=0, microsecond=0)
        collection.collected_at = local_collection_time.astimezone(UTC)
        collection.save(update_fields=["collected_at"])
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("parties:farmer_detail", args=[self.organization.slug, self.farmer.pk])
        )
        self.assertEqual(response.context["metrics"]["today_litres"], Decimal("2.500"))
        self.assertEqual(response.context["metrics"]["month_litres"], Decimal("2.500"))

    def test_farmer_profile_aggregates_approved_milk_and_completed_payments(self):
        self._collection(self.farmer, MilkCollection.Status.APPROVED, "F-APPROVED", 18)
        self._collection(self.farmer, MilkCollection.Status.SUBMITTED, "F-SUBMITTED", 18)
        Payment.objects.create(
            organization=self.organization,
            branch=self.branch,
            reference="PAY-FARMER-COMPLETE",
            direction=Payment.Direction.OUTGOING,
            farmer=self.farmer,
            amount=Decimal("100.00"),
            currency=self.organization.currency,
            method=Payment.Method.CASH,
            status=Payment.Status.COMPLETED,
            paid_at=datetime(2026, 11, 18, 7, 0, tzinfo=UTC),
            recorded_by=self.owner,
        )
        Payment.objects.create(
            organization=self.organization,
            branch=self.branch,
            reference="PAY-FARMER-DELETED",
            direction=Payment.Direction.OUTGOING,
            farmer=self.farmer,
            amount=Decimal("900.00"),
            currency=self.organization.currency,
            method=Payment.Method.CASH,
            status=Payment.Status.COMPLETED,
            paid_at=datetime(2026, 11, 18, 7, 0, tzinfo=UTC),
            recorded_by=self.owner,
            deleted_at=datetime(2026, 11, 19, 7, 0, tzinfo=UTC),
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("parties:farmer_detail", args=[self.organization.slug, self.farmer.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["metrics"]["lifetime_litres"], Decimal("2.500"))
        self.assertEqual(response.context["metrics"]["average_litres"], Decimal("2.500"))
        self.assertEqual(response.context["metrics"]["average_fat"], Decimal("4.000"))
        self.assertEqual(response.context["metrics"]["average_snf"], Decimal("8.000"))
        self.assertEqual(response.context["metrics"]["average_lactose"], Decimal("4.500"))
        self.assertEqual(response.context["completed_payment_total"], Decimal("100.00"))
        self.assertEqual(response.context["period_completed_payment_total"], Decimal("100.00"))
        self.assertEqual(response.context["lifetime_unpaid_income"], Decimal("81.25"))
        self.assertEqual(response.context["period_unpaid_income"], Decimal("81.25"))
        self.assertEqual(response.context["payment_direction_label"], "Paid to farmer")
        self.assertEqual(response.context["payments"].paginator.count, 1)

    def test_foreign_tenant_party_uuid_is_not_resolvable(self):
        other = Organization.objects.create(
            owner=self.owner,
            name="Other Dairy",
            slug="other-dairy",
            is_demo=True,
        )
        foreign = Customer.objects.create(
            organization=other,
            code="C-FOREIGN",
            full_name="Foreign Customer",
        )
        foreign_farmer = Farmer.objects.create(
            organization=other,
            code="F-FOREIGN",
            full_name="Foreign Farmer",
        )
        self.client.force_login(self.owner)
        url = reverse("parties:customer_detail", args=[self.organization.slug, foreign.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        url = reverse("parties:farmer_detail", args=[self.organization.slug, foreign_farmer.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_foreign_tenant_collection_uuid_is_not_resolvable(self):
        other = Organization.objects.create(
            owner=self.owner,
            name="Other Collection Dairy",
            slug="other-collection-dairy",
            is_demo=True,
        )
        other_branch = Branch.objects.create(
            organization=other,
            code="OTHER",
            name="Other Branch",
        )
        foreign_farmer = Farmer.objects.create(
            organization=other,
            branch=other_branch,
            code="F-OTHER",
            full_name="Foreign Farmer",
        )
        other_pricing = PricingConfiguration.objects.create(
            organization=other,
            version=1,
            snf_rate=Decimal("5.0000"),
            fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=datetime(2026, 1, 1).date(),
            is_approved=True,
            created_by=self.owner,
        )
        collection = MilkCollection.objects.create(
            organization=other,
            branch=other_branch,
            reference="FOREIGN-COLLECTION",
            farmer=foreign_farmer,
            recorded_by=self.owner,
            collected_at=datetime(2026, 11, 18, 6, 0, tzinfo=UTC),
            quantity_litres=Decimal("1.000"),
            snf=Decimal("8.000"),
            fat=Decimal("4.000"),
            lactose=Decimal("4.500"),
            milk_rate=Decimal("72.50"),
            total_amount=Decimal("72.50"),
            pricing=other_pricing,
        )
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse(
                "collections:edit",
                kwargs={
                    "organization_slug": self.organization.slug,
                    "collection_id": collection.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_branch_restricted_user_cannot_open_other_branch_party(self):
        other_branch = Branch.objects.create(
            organization=self.organization,
            code="REMOTE",
            name="Remote Branch",
        )
        remote_customer = Customer.objects.create(
            organization=self.organization,
            branch=other_branch,
            code="C-REMOTE",
            full_name="Remote Customer",
        )
        staff = User.objects.create_user(
            username="branch-staff",
            email="branch-staff@example.test",
            password="LongDemoPass!123",
        )
        membership = Membership.objects.create(
            user=staff,
            organization=self.organization,
            role=Membership.Role.BRANCH_MANAGER,
            status=Membership.Status.ACTIVE,
        )
        BranchAssignment.objects.create(membership=membership, branch=self.branch)
        self.client.force_login(staff)
        url = reverse("parties:customer_detail", args=[self.organization.slug, remote_customer.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_farmer_list_search_and_owner_directory_profile_link(self):
        self.client.force_login(self.owner)
        url = reverse("parties:farmers", args=[self.organization.slug])
        response = self.client.get(url, {"q": "F001", "status": "active"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("parties:farmer_detail", args=[self.organization.slug, self.farmer.pk]),
        )

    def test_farmer_search_matches_partial_code_name_phone_email_address_bank_and_branch(self):
        self.farmer.full_name = "Ram Bahadur Kewat"
        self.farmer.phone = "9812345678"
        self.farmer.email = "ram.kewat@gmail.test"
        self.farmer.address = "Parasi Nepal"
        self.farmer.bank_account_name = "Ram Kewat"
        self.farmer.bank_account_number = "1234567890"
        self.farmer.bank_name = "Nepal Bank"
        self.farmer.save()
        self.client.force_login(self.owner)
        url = reverse("parties:farmers", args=[self.organization.slug])
        for term in ("F00", "bahadur", "123456", "kewat@gmail", "parasi", "1234567890", "nepal bank", "main branch"):
            with self.subTest(term=term):
                response = self.client.get(url, {"q": term})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context["page_obj"].object_list), [self.farmer])



    def test_search_supports_email_and_filters_inactive_customers(self):
        self.customer.email = "find-me@example.test"
        self.customer.is_active = False
        self.customer.save()
        self.client.force_login(self.owner)
        url = reverse("parties:customers", args=[self.organization.slug])
        response = self.client.get(url, {"q": "find-me@example.test", "status": "inactive"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [self.customer])

    def test_owner_can_edit_all_farmer_profile_fields_and_status(self):
        self.client.force_login(self.owner)
        url = reverse("parties:farmer_edit", args=[self.organization.slug, self.farmer.pk])
        response = self.client.post(url, {
            "branch": str(self.branch.pk),
            "code": "F001-UPDATED",
            "full_name": "Updated Farmer",
            "phone": "9812345678",
            "email": "updated-farmer@example.test",
            "address": "Updated address",
            "bank_account_name": "Updated Account",
            "bank_account_number": "123456789",
            "bank_name": "Updated Bank",
            "is_active": "",
        })
        self.assertEqual(response.status_code, 302)
        self.farmer.refresh_from_db()
        self.assertEqual(self.farmer.code, "F001-UPDATED")
        self.assertEqual(self.farmer.full_name, "Updated Farmer")
        self.assertEqual(self.farmer.phone, "9812345678")
        self.assertEqual(self.farmer.email, "updated-farmer@example.test")
        self.assertEqual(self.farmer.address, "Updated address")
        self.assertEqual(self.farmer.bank_account_name, "Updated Account")
        self.assertEqual(self.farmer.bank_account_number, "123456789")
        self.assertEqual(self.farmer.bank_name, "Updated Bank")
        self.assertFalse(self.farmer.is_active)

    def test_owner_can_edit_customer_profile(self):
        self.client.force_login(self.owner)
        url = reverse("parties:customer_edit", args=[self.organization.slug, self.customer.pk])
        response = self.client.post(
            url,
            {
                "branch": str(self.branch.pk),
                "code": "C001",
                "full_name": "Corrected Customer",
                "phone": "9811111111",
                "email": "corrected@example.test",
                "address": "Updated address",
                "city": "Parasi",
                "village": "",
                "ward": "4",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, "Corrected Customer")

    def test_soft_deleted_customer_is_hidden_and_can_be_restored(self):
        self.client.force_login(self.owner)
        trash_url = reverse(
            "parties:customer_trash", args=[self.organization.slug, self.customer.pk]
        )
        response = self.client.post(trash_url)
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertIsNotNone(self.customer.deleted_at)
        detail_url = reverse(
            "parties:customer_detail", args=[self.organization.slug, self.customer.pk]
        )
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        directory_url = reverse("parties:customers", args=[self.organization.slug])
        self.assertNotContains(self.client.get(directory_url), "Test Customer")
        restore_url = reverse(
            "parties:party_restore",
            args=[
                self.organization.slug,
                "customer",
                self.customer.pk,
            ],
        )
        response = self.client.post(restore_url)
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.deleted_at)
