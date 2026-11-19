from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import FileResponse
from django.http.request import QueryDict
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.data_exports.models import ExportJob
from apps.data_exports.queue import process_export_job, queue_export
from apps.data_exports.storage import private_storage
from apps.organizations.models import Branch, BranchAssignment, Membership, Organization
from apps.parties.models import Farmer

User = get_user_model()


class ExportDownloadAuthorizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="export-staff",
            email="export-staff@example.test",
            password="LongDemoPass!123",
        )
        self.organization = Organization.objects.create(
            owner=self.user, name="Export Dairy", slug="export-dairy"
        )
        self.membership = Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BRANCH_MANAGER,
        )
        self.branch_a = Branch.objects.create(
            organization=self.organization, code="A", name="Branch A"
        )
        self.branch_b = Branch.objects.create(
            organization=self.organization, code="B", name="Branch B"
        )
        BranchAssignment.objects.create(membership=self.membership, branch=self.branch_a)
        BranchAssignment.objects.create(membership=self.membership, branch=self.branch_b)
        self.client.force_login(self.user)

    def create_job(self, *, module="farmers", branch_scope=None, requester=None):
        job = ExportJob.objects.create(
            organization=self.organization,
            requested_by=requester or self.user,
            module=module,
            file_format="csv",
            status=ExportJob.Status.COMPLETED,
            file="private_exports/test-export.csv",
            filters={"branch_scope": branch_scope},
            expires_at=timezone.now() + timedelta(days=1),
        )
        return job

    def download(self, job):
        return self.client.get(
            reverse(
                "data_exports:download",
                kwargs={"organization_slug": self.organization.slug, "job_id": job.pk},
            )
        )

    def test_authorized_requester_can_download_export_for_current_branches(self):
        job = self.create_job(branch_scope=[str(self.branch_a.pk), str(self.branch_b.pk)])
        with patch.object(private_storage, "open", return_value=BytesIO(b"export")):
            response = self.download(job)

        self.assertIsInstance(response, FileResponse)
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_branch_manager_can_view_reports(self):
        response = self.client.get(
            reverse("data_exports:reports", kwargs={"organization_slug": self.organization.slug})
        )

        self.assertEqual(response.status_code, 200)

    def test_collection_operator_cannot_view_reports(self):
        self.membership.role = Membership.Role.COLLECTION_OPERATOR
        self.membership.save(update_fields=["role", "updated_at"])

        response = self.client.get(
            reverse("data_exports:reports", kwargs={"organization_slug": self.organization.slug})
        )

        self.assertEqual(response.status_code, 403)

    def test_download_is_denied_after_branch_assignments_are_reduced(self):
        job = self.create_job(branch_scope=[str(self.branch_a.pk), str(self.branch_b.pk)])
        self.membership.branch_assignments.filter(branch=self.branch_b).delete()

        response = self.download(job)

        self.assertEqual(response.status_code, 404)

    def test_download_is_denied_when_a_scoped_branch_is_inactive(self):
        job = self.create_job(branch_scope=[str(self.branch_a.pk)])
        self.branch_a.is_active = False
        self.branch_a.save(update_fields=["is_active"])

        response = self.download(job)

        self.assertEqual(response.status_code, 404)

    def test_download_is_denied_when_a_scoped_branch_is_deleted(self):
        job = self.create_job(branch_scope=[str(self.branch_a.pk)])
        self.branch_a.deleted_at = timezone.now()
        self.branch_a.save(update_fields=["deleted_at"])

        response = self.download(job)

        self.assertEqual(response.status_code, 404)

    def test_download_rechecks_current_module_permission(self):
        job = self.create_job(module="payments", branch_scope=[str(self.branch_a.pk)])
        self.membership.role = Membership.Role.COLLECTION_OPERATOR
        self.membership.save(update_fields=["role", "updated_at"])

        response = self.download(job)

        self.assertEqual(response.status_code, 404)

    def test_legacy_job_without_saved_scope_cannot_be_downloaded(self):
        job = self.create_job()
        job.filters = {}
        job.save(update_fields=["filters"])

        response = self.download(job)

        self.assertEqual(response.status_code, 404)

    def test_legacy_supplier_export_without_scope_is_not_processed(self):
        job = self.create_job(module="suppliers")
        job.status = ExportJob.Status.QUEUED
        job.file = ""
        job.filters = {}
        job.save(update_fields=["status", "file", "filters"])

        processed = process_export_job(job.pk)

        self.assertEqual(processed.status, ExportJob.Status.FAILED)
        self.assertFalse(processed.file)

    def test_background_export_uses_saved_tenant_and_current_branch_scope(self):
        Farmer.objects.create(
            organization=self.organization,
            branch=self.branch_a,
            code="A-1",
            full_name="Branch A Farmer",
        )
        Farmer.objects.create(
            organization=self.organization,
            branch=self.branch_b,
            code="B-1",
            full_name="Branch B Farmer",
        )
        other_organization = Organization.objects.create(
            owner=self.user, name="Other Export Dairy", slug="other-export-dairy"
        )
        other_branch = Branch.objects.create(
            organization=other_organization, code="X", name="Other Branch"
        )
        Farmer.objects.create(
            organization=other_organization,
            branch=other_branch,
            code="X-1",
            full_name="Other Tenant Farmer",
        )
        params = QueryDict("", mutable=True)
        job = queue_export(
            module="farmers",
            file_format="csv",
            organization=self.organization,
            membership=self.membership,
            actor=self.user,
            filters=params,
        )
        self.assertEqual(
            set(job.filters["branch_scope"]),
            {str(self.branch_a.pk), str(self.branch_b.pk)},
        )
        self.membership.branch_assignments.filter(branch=self.branch_b).delete()
        exported = []

        def capture_export(module, queryset, file_format, organization_name):
            exported.extend(queryset.values_list("organization_id", "branch_id"))
            return b"export", len(exported)

        with (
            patch("apps.data_exports.queue.build_export_file", side_effect=capture_export),
            patch.object(private_storage, "_save", side_effect=lambda name, content: name),
        ):
            processed = process_export_job(job.pk)

        self.assertEqual(processed.status, ExportJob.Status.COMPLETED)
        self.assertEqual(
            exported,
            [(self.organization.pk, self.branch_a.pk)],
        )
