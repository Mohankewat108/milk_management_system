from types import SimpleNamespace
from unittest.mock import Mock

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase

from apps.data_exports.services import build_csv, export_queryset


class ExportServiceTests(SimpleTestCase):
    def test_csv_has_utf8_bom_headers_and_unicode_values(self):
        farmer = SimpleNamespace(
            pk="farmer-id", code="F-001", full_name="कृष्ण केवट", phone="9800000000",
            email="farmer@example.com", address="रामग्राम", branch=SimpleNamespace(name="मुख्य शाखा"),
            is_active=True, created_at=__import__("datetime").datetime(2026, 1, 2, 10, 30),
            user_id=None,
        )
        queryset = Mock()
        queryset.iterator.return_value = iter([farmer])

        content, count = build_csv("farmers", queryset)

        self.assertTrue(content.startswith("\ufeff"))
        self.assertIn("कृष्ण केवट", content)
        self.assertIn("रामग्राम", content)
        self.assertIn("Code", content)
        self.assertEqual(count, 1)

    def test_csv_escapes_formula_like_untrusted_text(self):
        farmer = SimpleNamespace(
            pk="farmer-id", code="=HYPERLINK(\"https://bad.example\")", full_name="+cmd",
            phone="", email="", address="@SUM(A1:A2)", branch=None,
            is_active=True, created_at=__import__("datetime").datetime(2026, 1, 2),
            user_id=None,
        )
        queryset = Mock()
        queryset.iterator.return_value = iter([farmer])

        content, count = build_csv("farmers", queryset)

        self.assertIn("'=HYPERLINK", content)
        self.assertIn("'+cmd", content)
        self.assertIn("'@SUM", content)
        self.assertEqual(count, 1)

    def test_instant_export_limit_is_enforced(self):
        farmer = SimpleNamespace(
            pk="farmer-id", code="F", full_name="Farmer", phone="", email="", address="",
            branch=None, is_active=True, created_at=__import__("datetime").datetime(2026, 1, 2),
            user_id=None,
        )
        queryset = Mock()
        queryset.iterator.return_value = iter([farmer] * 20001)

        with self.assertRaises(ValidationError):
            build_csv("farmers", queryset)

    def test_role_without_module_permission_is_rejected(self):
        membership = SimpleNamespace(role="collection_operator")

        with self.assertRaises(PermissionDenied):
            export_queryset(
                module="payments",
                organization=SimpleNamespace(),
                membership=membership,
                params=SimpleNamespace(),
            )


class ExportFormatTests(SimpleTestCase):
    def setUp(self):
        self.farmer = SimpleNamespace(
            pk="farmer-id", code="F-001", full_name="Example Farmer", phone="9800000000",
            email="farmer@example.com", address="Parasi", branch=SimpleNamespace(name="Main"),
            is_active=True, created_at=__import__("datetime").datetime(2026, 1, 2, 10, 30),
            user_id=None,
        )
        self.queryset = Mock()
        self.queryset.iterator.return_value = iter([self.farmer])

    def test_excel_export_is_valid_xlsx(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from apps.data_exports.formats import build_xlsx

        payload, count = build_xlsx("farmers", self.queryset)
        workbook = load_workbook(BytesIO(payload), read_only=True)
        self.assertEqual(workbook.active["A1"].value, "ID")
        self.assertEqual(workbook.active["C2"].value, "Example Farmer")
        self.assertEqual(count, 1)

    def test_pdf_export_has_pdf_signature(self):
        from apps.data_exports.formats import build_pdf

        payload, count = build_pdf("farmers", self.queryset, "Test Dairy")
        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertEqual(count, 1)
