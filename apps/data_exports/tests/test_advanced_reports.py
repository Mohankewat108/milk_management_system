from datetime import UTC, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.collections.models import MilkCollection
from apps.data_exports.models import ExportJob
from apps.organizations.models import Branch, BranchAssignment, Membership, Organization
from apps.parties.models import Customer, Farmer
from apps.pricing.models import PricingConfiguration

User = get_user_model()


class AdvancedReportAnalyticsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bi-owner", email="bi-owner@example.test", password="LongDemoPass!123"
        )
        self.org = Organization.objects.create(owner=self.user, name="BI Dairy", slug="bi-dairy")
        self.membership = Membership.objects.create(
            user=self.user, organization=self.org, role=Membership.Role.OWNER
        )
        self.branch_a = Branch.objects.create(organization=self.org, code="A", name="Branch A")
        self.branch_b = Branch.objects.create(organization=self.org, code="B", name="Branch B")
        self.farmer_a = Farmer.objects.create(
            organization=self.org, branch=self.branch_a, code="FA", full_name="Farmer A"
        )
        self.farmer_b = Farmer.objects.create(
            organization=self.org, branch=self.branch_b, code="FB", full_name="Farmer B"
        )
        self.customer = Customer.objects.create(
            organization=self.org, branch=self.branch_a, code="CA", full_name="Customer A"
        )
        self.pricing = PricingConfiguration.objects.create(
            organization=self.org,
            version=1,
            snf_rate=Decimal("1.0000"),
            fat_rate=Decimal("1.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=datetime(2026, 1, 1).date(),
            is_approved=True,
            created_by=self.user,
        )
        self.client.force_login(self.user)

    def create_collection(
        self,
        *,
        reference,
        branch,
        party,
        quantity,
        fat,
        status=MilkCollection.Status.APPROVED,
        day=20,
        rate="10.00",
    ):
        return MilkCollection.objects.create(
            organization=self.org,
            branch=branch,
            reference=reference,
            farmer=party if isinstance(party, Farmer) else None,
            customer=party if isinstance(party, Customer) else None,
            recorded_by=self.user,
            collected_at=datetime(2026, 11, day, 5, 0, tzinfo=UTC),
            quantity_litres=Decimal(quantity),
            snf=Decimal("8.000"),
            fat=Decimal(fat),
            lactose=Decimal("4.500"),
            milk_rate=Decimal(rate),
            total_amount=(Decimal(quantity) * Decimal(rate)).quantize(Decimal("0.01")),
            pricing=self.pricing,
            pricing_snapshot={},
            status=status,
        )

    def report(self, query=""):
        return self.client.get(
            reverse("data_exports:reports", kwargs={"organization_slug": self.org.slug}) + query
        )

    def test_weighted_price_and_quality_and_customer_sales_are_separate(self):
        self.create_collection(
            reference="F-1",
            branch=self.branch_a,
            party=self.farmer_a,
            quantity="10",
            fat="4",
            rate="10",
        )
        self.create_collection(
            reference="F-2",
            branch=self.branch_a,
            party=self.farmer_a,
            quantity="30",
            fat="6",
            rate="20",
        )
        self.create_collection(
            reference="C-1",
            branch=self.branch_a,
            party=self.customer,
            quantity="5",
            fat="9",
            rate="25",
        )
        self.create_collection(
            reference="S-1",
            branch=self.branch_a,
            party=self.farmer_a,
            quantity="100",
            fat="3",
            status=MilkCollection.Status.SUBMITTED,
        )
        response = self.report()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["milk_litres"], Decimal("40"))
        self.assertEqual(response.context["milk_value"], Decimal("700.00"))
        self.assertEqual(response.context["average_price"], Decimal("17.5"))
        self.assertEqual(response.context["average_fat"], Decimal("5"))
        self.assertAlmostEqual(float(response.context["weighted_fat"]), 5.5)
        self.assertEqual(response.context["customer_litres"], Decimal("5"))
        self.assertEqual(response.context["customer_milk_value"], Decimal("125.00"))
        self.assertEqual(response.context["collection_count"], 2)

    def test_branch_filter_only_includes_permitted_selected_branch(self):
        self.create_collection(
            reference="A-1", branch=self.branch_a, party=self.farmer_a, quantity="3", fat="4"
        )
        self.create_collection(
            reference="B-1", branch=self.branch_b, party=self.farmer_b, quantity="8", fat="5"
        )
        response = self.report(f"?branch={self.branch_a.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["milk_litres"], Decimal("3"))
        self.assertEqual(len(response.context["branch_rows"]), 1)
        self.assertEqual(response.context["branch_rows"][0]["branch_id"], self.branch_a.pk)

    def test_farmer_filter_excludes_other_farmer_and_customer_collections(self):
        self.create_collection(
            reference="A-1", branch=self.branch_a, party=self.farmer_a, quantity="3", fat="4"
        )
        self.create_collection(
            reference="B-1", branch=self.branch_b, party=self.farmer_b, quantity="8", fat="5"
        )
        self.create_collection(
            reference="C-1", branch=self.branch_a, party=self.customer, quantity="6", fat="8"
        )
        response = self.report(f"?farmer={self.farmer_a.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["milk_litres"], Decimal("3"))
        self.assertEqual(response.context["farmers_supplied"], 1)
        self.assertEqual(response.context["customer_litres"], Decimal("0"))

    def test_customer_filter_reports_only_customer_linked_milk(self):
        self.create_collection(
            reference="A-1", branch=self.branch_a, party=self.farmer_a, quantity="3", fat="4"
        )
        self.create_collection(
            reference="C-1", branch=self.branch_a, party=self.customer, quantity="6", fat="8"
        )
        response = self.report(f"?customer={self.customer.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["milk_litres"], Decimal("0"))
        self.assertEqual(response.context["customer_litres"], Decimal("6"))

    def test_month_preset_calculates_month_date_range(self):
        self.create_collection(
            reference="A-1",
            branch=self.branch_a,
            party=self.farmer_a,
            quantity="3",
            fat="4",
            day=20,
        )
        response = self.report("?period=month&month=2026-11")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["date_from"], "2026-11-01")
        self.assertEqual(response.context["date_to"], "2026-11-30")
        self.assertEqual(response.context["milk_litres"], Decimal("3"))

    def test_status_filter_can_report_submitted_without_counting_as_approved_milk(self):
        self.create_collection(
            reference="S-1",
            branch=self.branch_a,
            party=self.farmer_a,
            quantity="7",
            fat="4",
            status=MilkCollection.Status.SUBMITTED,
        )
        response = self.report("?status=submitted")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["collection_count"], 0)
        self.assertEqual(response.context["milk_litres"], Decimal("0"))
        self.assertEqual(response.context["submitted_count"], 1)

    def test_foreign_branch_id_is_ignored_not_leaked(self):
        other_org = Organization.objects.create(
            owner=self.user, name="Other BI Dairy", slug="other-bi-dairy"
        )
        foreign_branch = Branch.objects.create(
            organization=other_org, code="X", name="Foreign Branch"
        )
        self.create_collection(
            reference="A-1", branch=self.branch_a, party=self.farmer_a, quantity="2", fat="4"
        )
        response = self.report(f"?branch={foreign_branch.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["milk_litres"], Decimal("0"))
        self.assertEqual(response.context["branch_rows"], [])


class AdvancedReportExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bi-export", email="bi-export@example.test", password="LongDemoPass!123"
        )
        self.org = Organization.objects.create(owner=self.user, name="BI Export", slug="bi-export")
        self.membership = Membership.objects.create(
            user=self.user, organization=self.org, role=Membership.Role.BRANCH_MANAGER
        )
        self.branch_a = Branch.objects.create(organization=self.org, code="EA", name="Export A")
        self.branch_b = Branch.objects.create(organization=self.org, code="EB", name="Export B")
        BranchAssignment.objects.create(membership=self.membership, branch=self.branch_a)
        BranchAssignment.objects.create(membership=self.membership, branch=self.branch_b)
        self.farmer = Farmer.objects.create(
            organization=self.org, branch=self.branch_a, code="EFA", full_name="Export Farmer A"
        )
        self.customer = Customer.objects.create(
            organization=self.org, branch=self.branch_a, code="ECA", full_name="Export Customer A"
        )
        self.client.force_login(self.user)

    def test_report_export_job_snapshots_multiple_selected_branches_and_filters(self):
        from django.http.request import QueryDict

        from apps.data_exports.queue import queue_export

        filters = QueryDict(
            f"branch={self.branch_a.pk}&branch={self.branch_b.pk}&from=2026-11-01"
            f"&to=2026-11-30&period=month&month=2026-11&farmer={self.farmer.pk}",
            mutable=True,
        )
        job = queue_export(
            module="reports",
            file_format="xlsx",
            organization=self.org,
            membership=self.membership,
            actor=self.user,
            filters=filters,
        )
        self.assertEqual(job.status, ExportJob.Status.QUEUED)
        self.assertEqual(
            set(job.filters["branch_scope"]), {str(self.branch_a.pk), str(self.branch_b.pk)}
        )
        self.assertEqual(
            set(job.filters["branches"]),
            {str(self.branch_a.pk), str(self.branch_b.pk)},
        )
        self.assertEqual(job.filters["farmer"], str(self.farmer.pk))
        self.assertEqual(job.filters["month"], "2026-11")

    def test_report_export_rejects_unassigned_branch(self):
        from django.http.request import QueryDict

        from apps.data_exports.queue import queue_export

        other_org = Organization.objects.create(
            owner=self.user, name="Foreign BI Export", slug="foreign-bi-export"
        )
        foreign_branch = Branch.objects.create(organization=other_org, code="FX", name="Foreign")
        filters = QueryDict(f"branch={foreign_branch.pk}", mutable=True)
        with self.assertRaises(PermissionDenied):
            queue_export(
                module="reports",
                file_format="csv",
                organization=self.org,
                membership=self.membership,
                actor=self.user,
                filters=filters,
            )

    def test_report_export_worker_creates_private_excel_csv_and_pdf(self):
        from datetime import UTC, datetime
        from decimal import Decimal
        from unittest.mock import patch

        from django.http.request import QueryDict

        from apps.collections.models import MilkCollection
        from apps.data_exports.queue import process_export_job, queue_export
        from apps.pricing.models import PricingConfiguration

        pricing = PricingConfiguration.objects.create(
            organization=self.org,
            version=1,
            snf_rate=Decimal("1.0000"),
            fat_rate=Decimal("1.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=datetime(2026, 1, 1).date(),
            is_approved=True,
            created_by=self.user,
        )
        MilkCollection.objects.create(
            organization=self.org,
            branch=self.branch_a,
            reference="REPORT-EXPORT-001",
            farmer=self.farmer,
            recorded_by=self.user,
            collected_at=datetime(2026, 11, 20, 5, 0, tzinfo=UTC),
            quantity_litres=Decimal("12.000"),
            snf=Decimal("8.000"),
            fat=Decimal("4.000"),
            lactose=Decimal("4.500"),
            milk_rate=Decimal("20.00"),
            total_amount=Decimal("240.00"),
            pricing=pricing,
            pricing_snapshot={},
            status=MilkCollection.Status.APPROVED,
        )
        for file_format in ("xlsx", "csv", "pdf"):
            job = queue_export(
                module="reports",
                file_format=file_format,
                organization=self.org,
                membership=self.membership,
                actor=self.user,
                filters=QueryDict(f"branch={self.branch_a.pk}&from=2026-11-01&to=2026-11-30"),
            )
            with patch("apps.data_exports.queue.send_mail", return_value=1):
                processed = process_export_job(job.pk)
            self.assertEqual(processed.status, ExportJob.Status.COMPLETED, processed.error_message)
            self.assertEqual(processed.record_count, 1)
            self.assertTrue(processed.file.name.startswith("private_exports/"))
            with processed.file.open("rb") as stream:
                payload = stream.read()
            if file_format == "csv":
                self.assertTrue(payload.startswith(bytes((239, 187, 191))))
                self.assertIn(b"REPORT-EXPORT-001", payload)
            elif file_format == "xlsx":
                self.assertTrue(payload.startswith(b"PK"))
            else:
                self.assertTrue(payload.startswith(b"%PDF"))
            processed.file.delete(save=False)

    def test_report_export_download_rechecks_permissions(self):
        from datetime import UTC, datetime
        from decimal import Decimal
        from io import BytesIO
        from unittest.mock import patch

        from django.http.request import QueryDict
        from django.urls import reverse

        from apps.collections.models import MilkCollection
        from apps.data_exports.queue import process_export_job, queue_export
        from apps.data_exports.storage import private_storage
        from apps.pricing.models import PricingConfiguration

        pricing = PricingConfiguration.objects.create(
            organization=self.org,
            version=1,
            snf_rate=Decimal("1.0000"),
            fat_rate=Decimal("1.0000"),
            lactose_rate=Decimal("1.0000"),
            effective_from=datetime(2026, 1, 1).date(),
            is_approved=True,
            created_by=self.user,
        )
        MilkCollection.objects.create(
            organization=self.org,
            branch=self.branch_a,
            reference="REPORT-EXPORT-002",
            farmer=self.farmer,
            recorded_by=self.user,
            collected_at=datetime(2026, 11, 20, 5, 0, tzinfo=UTC),
            quantity_litres=Decimal("4.000"),
            snf=Decimal("8.000"),
            fat=Decimal("4.000"),
            lactose=Decimal("4.500"),
            milk_rate=Decimal("20.00"),
            total_amount=Decimal("80.00"),
            pricing=pricing,
            pricing_snapshot={},
            status=MilkCollection.Status.APPROVED,
        )
        job = queue_export(
            module="reports",
            file_format="csv",
            organization=self.org,
            membership=self.membership,
            actor=self.user,
            filters=QueryDict(f"branch={self.branch_a.pk}"),
        )
        with patch("apps.data_exports.queue.send_mail", return_value=1):
            job = process_export_job(job.pk)
        url = reverse(
            "data_exports:download",
            kwargs={"organization_slug": self.org.slug, "job_id": job.pk},
        )
        stream = BytesIO(b"private report")
        with patch.object(private_storage, "open", return_value=stream):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.membership.branch_assignments.filter(branch=self.branch_a).delete()
        with patch.object(private_storage, "open", return_value=stream):
            self.assertEqual(self.client.get(url).status_code, 404)
        stream.close()
        job.file.delete(save=False)
