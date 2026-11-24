from datetime import UTC, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.collections.models import MilkCollection
from apps.collections.services import create_collection
from apps.organizations.models import Branch, Membership, Organization
from apps.parties.models import Farmer
from apps.pricing.models import PricingConfiguration

User = get_user_model()


class CollectionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="operator", email="operator@example.test", password="LongDemoPass!123"
        )
        self.org = Organization.objects.create(
            owner=self.user, name="Dairy A", slug="dairy-a", is_demo=True
        )
        self.branch = Branch.objects.create(organization=self.org, code="MAIN", name="Main")
        Membership.objects.create(user=self.user, organization=self.org, role=Membership.Role.OWNER)
        self.farmer = Farmer.objects.create(
            organization=self.org, branch=self.branch, code="F001", full_name="Test Farmer"
        )
        self.pricing = PricingConfiguration.objects.create(
            organization=self.org,
            version=1,
            snf_rate=Decimal("5.0000"),
            fat_rate=Decimal("7.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=datetime(2026, 1, 1).date(),
            is_approved=True,
            created_by=self.user,
        )

    def test_collection_creation_requires_active_tenant_membership(self):
        outsider = User.objects.create_user(
            username="outsider", email="outsider@example.test", password="LongDemoPass!123"
        )
        with self.assertRaises(PermissionDenied):
            create_collection(
                organization=self.org,
                branch=self.branch,
                actor=outsider,
                collected_at=datetime(2026, 11, 18, 6, 0, tzinfo=UTC),
                quantity_litres="1.000",
                snf="8.0",
                fat="4.0",
                lactose="4.5",
                farmer=self.farmer,
            )
        self.assertEqual(MilkCollection.objects.count(), 0)

    def test_collection_uses_pricing_snapshot_and_decimal_total(self):
        entry = create_collection(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            collected_at=datetime(2026, 11, 18, 6, 0, tzinfo=UTC),
            quantity_litres="2.500",
            snf="8.0",
            fat="4.0",
            lactose="4.5",
            farmer=self.farmer,
        )
        self.assertEqual(entry.status, MilkCollection.Status.SUBMITTED)
        self.assertEqual(entry.milk_rate, Decimal("72.50"))
        self.assertEqual(entry.total_amount, Decimal("181.25"))
        self.assertEqual(entry.pricing_snapshot["version"], 1)

    def test_collection_submission_key_returns_the_original_record(self):
        data = {
            "organization": self.org,
            "branch": self.branch,
            "actor": self.user,
            "collected_at": datetime(2026, 11, 18, 6, 0, tzinfo=UTC),
            "quantity_litres": "2.500",
            "snf": "8.0",
            "fat": "4.0",
            "lactose": "4.5",
            "farmer": self.farmer,
            "idempotency_key": "collection-request-001",
        }
        first = create_collection(**data)
        retry = create_collection(**data)
        self.assertEqual(first.pk, retry.pk)
        self.assertEqual(MilkCollection.objects.count(), 1)

        with self.assertRaises(ValidationError):
            create_collection(**{**data, "quantity_litres": "3.000"})
        self.assertEqual(MilkCollection.objects.count(), 1)

    def test_soft_deleted_party_cannot_receive_new_collection(self):
        from django.utils import timezone

        self.farmer.deleted_at = timezone.now()
        self.farmer.save(update_fields=["deleted_at", "updated_at"])
        with self.assertRaises(ValidationError):
            create_collection(
                organization=self.org,
                branch=self.branch,
                actor=self.user,
                collected_at=datetime(2026, 11, 18, 6, 0, tzinfo=UTC),
                quantity_litres="1",
                snf="8",
                fat="4",
                lactose="4",
                farmer=self.farmer,
            )
        self.assertEqual(MilkCollection.objects.count(), 0)

    def test_party_from_another_organisation_is_rejected(self):
        other = Organization.objects.create(
            owner=self.user, name="Dairy B", slug="dairy-b", is_demo=True
        )
        foreign_farmer = Farmer.objects.create(
            organization=other, code="F002", full_name="Foreign Farmer"
        )
        with self.assertRaises(ValidationError):
            create_collection(
                organization=self.org,
                branch=self.branch,
                actor=self.user,
                collected_at=datetime(2026, 11, 18, 6, 0, tzinfo=UTC),
                quantity_litres="1",
                snf="8",
                fat="4",
                lactose="4",
                farmer=foreign_farmer,
            )

    def test_party_assigned_to_another_branch_is_rejected_by_service(self):
        other_branch = Branch.objects.create(
            organization=self.org, code="OTHER", name="Other Branch"
        )
        other_farmer = Farmer.objects.create(
            organization=self.org,
            branch=other_branch,
            code="F-OTHER",
            full_name="Other Branch Farmer",
        )

        with self.assertRaises(ValidationError):
            create_collection(
                organization=self.org,
                branch=self.branch,
                actor=self.user,
                collected_at=datetime(2026, 11, 18, 6, 0, tzinfo=UTC),
                quantity_litres="1.000",
                snf="8.0",
                fat="4.0",
                lactose="4.5",
                farmer=other_farmer,
            )

    def test_lactometer_and_rate_components_are_saved_in_snapshot(self):
        entry = create_collection(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            collected_at=datetime(2026, 11, 18, 7, 0, tzinfo=UTC),
            quantity_litres="2.000",
            snf="8.0",
            fat="4.0",
            lactose="4.5",
            farmer=self.farmer,
            lactometer_reading="29.5",
            milk_temperature_c="5.50",
            sample_reference="SAMPLE-001",
            quality_test_method="Digital analyser",
        )
        self.assertEqual(entry.lactometer_reading, Decimal("29.500"))
        self.assertEqual(entry.milk_temperature_c, Decimal("5.50"))
        self.assertEqual(entry.tested_by, self.user)
        self.assertEqual(entry.pricing_snapshot["snf_component"], "40.00")
        self.assertEqual(entry.pricing_snapshot["fat_component"], "28.00")
        self.assertEqual(entry.pricing_snapshot["lactose_component"], "4.50")
        self.assertEqual(entry.pricing_snapshot["effective_from"], "2026-01-01")

    def test_rate_selection_uses_dairy_local_date_near_midnight(self):
        self.org.timezone = "Asia/Kathmandu"
        self.org.save(update_fields=["timezone", "updated_at"])
        entry = create_collection(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            # 18 Nov 23:30 in Kathmandu; still 18 Nov in UTC in this fixture.
            collected_at=datetime(2026, 11, 18, 18, 0, tzinfo=UTC),
            quantity_litres="1.000",
            snf="8.0",
            fat="4.0",
            lactose="4.5",
            farmer=self.farmer,
        )
        self.assertEqual(entry.pricing_id, self.pricing.id)

    def test_collection_edit_page_is_scoped_and_audited(self):
        from django.urls import reverse

        from apps.audit.models import AuditEvent

        entry = create_collection(
            organization=self.org,
            branch=self.branch,
            actor=self.user,
            collected_at=datetime(2026, 11, 18, 6, 0, tzinfo=UTC),
            quantity_litres="2.000",
            snf="8.0",
            fat="4.0",
            lactose="4.5",
            farmer=self.farmer,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "collections:edit",
                kwargs={
                    "organization_slug": self.org.slug,
                    "collection_id": entry.pk,
                },
            )
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse(
                "collections:edit",
                kwargs={
                    "organization_slug": self.org.slug,
                    "collection_id": entry.pk,
                },
            ),
            {
                "quantity_litres": "3.000",
                "snf": "8.0",
                "fat": "4.0",
                "lactose": "4.5",
                "lactometer_reading": "",
                "milk_temperature_c": "",
                "sample_reference": "",
                "quality_test_method": "",
                "notes": "Corrected quantity",
            },
        )
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.quantity_litres, Decimal("3.000"))
        self.assertEqual(entry.total_amount, Decimal("217.50"))
        self.assertEqual(
            AuditEvent.objects.filter(
                action="milk_collection.updated", target_id=str(entry.pk)
            ).count(),
            1,
        )

    def test_collection_creation_rejects_suspended_or_inaccessible_context(self):
        from django.utils import timezone

        membership = Membership.objects.get(user=self.user, organization=self.org)
        other_org = Organization.objects.create(
            owner=self.user, name="Unrelated Dairy", slug="unrelated-dairy", is_demo=True
        )
        outsider = User.objects.create_user(
            username="other-tenant-user",
            email="other-tenant@example.test",
            password="LongDemoPass!123",
        )
        Membership.objects.create(user=outsider, organization=other_org, role=Membership.Role.OWNER)

        for scenario in (
            "foreign_tenant_membership",
            "suspended_membership",
            "suspended_organization",
            "inactive_branch",
            "soft_deleted_branch",
        ):
            with self.subTest(scenario=scenario):
                self.org.status = Organization.Status.ACTIVE
                self.org.save(update_fields=["status", "updated_at"])
                self.branch.is_active = True
                self.branch.deleted_at = None
                self.branch.save(update_fields=["is_active", "deleted_at", "updated_at"])
                membership.status = Membership.Status.ACTIVE
                membership.save(update_fields=["status", "updated_at"])
                actor = self.user

                if scenario == "foreign_tenant_membership":
                    actor = outsider
                elif scenario == "suspended_membership":
                    membership.status = Membership.Status.SUSPENDED
                    membership.save(update_fields=["status", "updated_at"])
                elif scenario == "suspended_organization":
                    self.org.status = Organization.Status.SUSPENDED
                    self.org.save(update_fields=["status", "updated_at"])
                elif scenario == "inactive_branch":
                    self.branch.is_active = False
                    self.branch.save(update_fields=["is_active", "updated_at"])
                elif scenario == "soft_deleted_branch":
                    self.branch.deleted_at = timezone.now()
                    self.branch.save(update_fields=["deleted_at", "updated_at"])

                expected_error = (
                    ValidationError if scenario == "inactive_branch" else PermissionDenied
                )
                with self.assertRaises(expected_error):
                    create_collection(
                        organization=self.org,
                        branch=self.branch,
                        actor=actor,
                        collected_at=datetime(2026, 11, 18, 6, 0, tzinfo=UTC),
                        quantity_litres="1.000",
                        snf="8.0",
                        fat="4.0",
                        lactose="4.5",
                        farmer=self.farmer,
                    )
                self.assertEqual(MilkCollection.objects.count(), 0)

    def test_collection_creation_rejects_unassigned_branch(self):
        from apps.organizations.models import BranchAssignment

        other_branch = Branch.objects.create(organization=self.org, code="SECOND", name="Second")
        operator = User.objects.create_user(
            username="branch-collection-operator",
            email="branch-collection-operator@example.test",
            password="LongDemoPass!123",
        )
        membership = Membership.objects.create(
            user=operator,
            organization=self.org,
            role=Membership.Role.COLLECTION_OPERATOR,
        )
        BranchAssignment.objects.create(membership=membership, branch=self.branch)

        with self.assertRaises(PermissionDenied):
            create_collection(
                organization=self.org,
                branch=other_branch,
                actor=operator,
                collected_at=datetime(2026, 11, 18, 6, 0, tzinfo=UTC),
                quantity_litres="1.000",
                snf="8.0",
                fat="4.0",
                lactose="4.5",
                farmer=self.farmer,
            )
        self.assertEqual(MilkCollection.objects.count(), 0)
